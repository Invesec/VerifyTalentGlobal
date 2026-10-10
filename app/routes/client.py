from datetime import date, datetime, timezone

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import select

from ..client_data import AGREEMENT_STATUS_LABELS, CLIENT_STATUS_LABELS, client_progress
from ..extensions import db
from ..job_data import CONTRACT_TYPES, CURRENCIES, JOB_STATUS_LABELS, MATCH_STATUS_LABELS, SCORE_NOTE, WORK_MODES
from ..models import Agreement, Client, ClientApplication, Job, Match, TalentApplication
from ..security import login_required
from ..services.audit import log_action, notify
from ..talent_data import CATEGORIES
from ..validators import validate_job

bp = Blueprint("client", __name__, url_prefix="/client")


def _application():
    # Always filtered by the logged-in user, so a company can never see another company's data.
    capp = db.session.scalar(select(ClientApplication).filter_by(user_id=g.user.id))
    if capp is None:
        abort(404)
    return capp


def _agreements(capp):
    return db.session.scalars(select(Agreement).where(Agreement.client_application_id == capp.id)
                              .order_by(Agreement.id.desc())).all()


@bp.get("/dashboard")
@login_required("CLIENT")
def dashboard():
    capp = _application()
    client = db.session.scalar(select(Client).where(Client.application_id == capp.id))
    agreements = _agreements(capp)
    jobs = db.session.scalars(select(Job).where(Job.client_application_id == capp.id)).all() if client else []
    steps, current = client_progress(capp.status, has_jobs=any(j.status != "DRAFT" for j in jobs))
    return render_template("client/dashboard.html", jobs=jobs, job_labels=JOB_STATUS_LABELS, steps=steps, current=current, title="Your dashboard | VerifyTalent Global", capp=capp,
                           client=client, agreement=agreements[0] if agreements else None,
                           status_label=CLIENT_STATUS_LABELS.get(capp.status, capp.status),
                           agreement_labels=AGREEMENT_STATUS_LABELS)


@bp.get("/company")
@login_required("CLIENT")
def company():
    return render_template("client/company.html", title="Company profile | VerifyTalent Global", capp=_application())


@bp.get("/agreements")
@login_required("CLIENT")
def agreements():
    capp = _application()
    items = _agreements(capp)
    latest = items[0] if items else None
    if latest and latest.status == "SENT":  # opening the page marks it as viewed
        latest.status, latest.viewed_at = "VIEWED", datetime.now(timezone.utc)
        log_action("agreement.viewed", actor=g.user, target_type="agreement", target_id=latest.agreement_id)
        db.session.commit()
    return render_template("client/agreements.html", title="Agreements | VerifyTalent Global", capp=capp,
                           items=items, labels=AGREEMENT_STATUS_LABELS, today=date.today())


def _own_open_agreement(capp, agreement_pk):
    agreement = db.session.scalar(select(Agreement).where(Agreement.id == agreement_pk,
                                                          Agreement.client_application_id == capp.id))
    if agreement is None:
        abort(404)  # also covers another company's agreement
    return agreement


@bp.post("/agreements/<int:agreement_pk>/accept")
@login_required("CLIENT")
def accept(agreement_pk):
    capp = _application()
    agreement = _own_open_agreement(capp, agreement_pk)
    name = (request.form.get("signed_name") or "").strip()
    if agreement.status not in ("SENT", "VIEWED"):
        flash("This agreement can no longer be accepted.", "error")
    elif agreement.expires_at and agreement.expires_at < date.today():
        flash("This agreement has expired. Please contact VerifyTalent Global.", "error")
    elif len(name) < 2 or len(name) > 100 or request.form.get("accept") != "yes":
        flash("Type your full name and tick the box to accept.", "error")
    else:
        agreement.status, agreement.accepted_at = "ACCEPTED", datetime.now(timezone.utc)
        agreement.accepted_by_name = name
        if capp.status in ("AGREEMENT_SENT", "AGREEMENT_PENDING", "APPROVED"):
            capp.status = "AGREEMENT_ACCEPTED"
        log_action("agreement.accepted", actor=g.user, target_type="agreement", target_id=agreement.agreement_id,
                   meta={"signed_name": name, "company": capp.application_id})
        db.session.commit()
        flash("Agreement accepted. Our team will now activate your account.", "success")
    return redirect(url_for("client.agreements"))


@bp.post("/agreements/<int:agreement_pk>/decline")
@login_required("CLIENT")
def decline(agreement_pk):
    capp = _application()
    agreement = _own_open_agreement(capp, agreement_pk)
    if agreement.status in ("SENT", "VIEWED"):
        agreement.status = "DECLINED"
        log_action("agreement.declined", actor=g.user, target_type="agreement", target_id=agreement.agreement_id)
        db.session.commit()
        flash("You declined the agreement. Our team will be in touch.", "info")
    else:
        flash("This agreement can no longer be declined.", "error")
    return redirect(url_for("client.agreements"))


# ---------------- Job requests (Milestone 5) ----------------
PRESENTED_STATUSES = ("PRESENTED", "INTERVIEWING", "PLACED")


def _require_active(capp):
    client = db.session.scalar(select(Client).where(Client.application_id == capp.id))
    if capp.status != "ACTIVE" or client is None or client.membership_status != "ACTIVE":
        flash("Job requests open once your account is active.", "info")
        return None
    return client


def _own_job(capp, job_pk):
    job = db.session.scalar(select(Job).where(Job.id == job_pk, Job.client_application_id == capp.id))
    if job is None:
        abort(404)  # also covers another company's job
    return job


def _job_form_context(**extra):
    return dict(categories=CATEGORIES, work_modes=WORK_MODES, contract_types=CONTRACT_TYPES, currencies=CURRENCIES, **extra)


@bp.get("/jobs")
@login_required("CLIENT")
def jobs():
    capp = _application()
    if _require_active(capp) is None:
        return redirect(url_for("client.dashboard"))
    items = db.session.scalars(select(Job).where(Job.client_application_id == capp.id).order_by(Job.id.desc())).all()
    return render_template("client/jobs.html", title="Job requests | VerifyTalent Global", capp=capp, items=items,
                           labels=JOB_STATUS_LABELS)


def _save_job(capp, job, clean, submit):
    for field, value in clean.items():
        setattr(job, field, value or None if field in ("qualifications", "certifications", "location", "timezone",
                "contract_duration", "budget", "additional_requirements", "currency") else value)
    if submit:
        job.status, job.submitted_at = "SUBMITTED", datetime.now(timezone.utc)
    elif job.status is None:
        job.status = "DRAFT"


@bp.route("/jobs/new", methods=["GET", "POST"])
@login_required("CLIENT")
def job_new():
    capp = _application()
    if _require_active(capp) is None:
        return redirect(url_for("client.dashboard"))
    title = "New job request | VerifyTalent Global"
    if request.method == "GET":
        return render_template("client/job_form.html", title=title, capp=capp, form={}, errors={}, editing=None, **_job_form_context())
    clean, errors = validate_job(request.form)
    if errors:
        return render_template("client/job_form.html", title=title, capp=capp, form=request.form, errors=errors,
                               editing=None, **_job_form_context()), 400
    submit = request.form.get("action") == "submit"
    job = Job(client_application_id=capp.id, title=clean["title"], category=clean["category"], profession=clean["profession"],
              required_skills=clean["required_skills"], contract_type=clean["contract_type"], work_mode=clean["work_mode"],
              description=clean["description"], status="DRAFT")
    db.session.add(job)
    db.session.flush()
    job.job_id = f"VTG-JOB-{job.id:06d}"  # generated on the server
    _save_job(capp, job, clean, submit)
    log_action("job.submitted" if submit else "job.created", actor=g.user, target_type="job", target_id=job.job_id,
               meta={"company": capp.application_id})
    db.session.commit()
    flash(f"Job request {job.job_id} " + ("submitted to VerifyTalent Global." if submit else "saved as a draft."), "success")
    return redirect(url_for("client.job_detail", job_pk=job.id))


@bp.route("/jobs/<int:job_pk>/edit", methods=["GET", "POST"])
@login_required("CLIENT")
def job_edit(job_pk):
    capp = _application()
    if _require_active(capp) is None:
        return redirect(url_for("client.dashboard"))
    job = _own_job(capp, job_pk)
    if job.status != "DRAFT":
        flash("Only drafts can be edited. Contact VerifyTalent Global to change a submitted request.", "info")
        return redirect(url_for("client.job_detail", job_pk=job.id))
    title = f"Edit {job.job_id} | VerifyTalent Global"
    if request.method == "GET":
        form = {k: ("" if getattr(job, k) is None else str(getattr(job, k))) for k in
                ("title", "profession", "workers_needed", "min_experience_years", "required_skills", "qualifications",
                 "certifications", "location", "timezone", "work_mode", "contract_type", "contract_duration", "budget",
                 "currency", "description", "additional_requirements")}
        form["start_date"] = job.start_date.isoformat() if job.start_date else ""
        return render_template("client/job_form.html", title=title, capp=capp, form=form, errors={}, editing=job, **_job_form_context())
    clean, errors = validate_job(request.form)
    if errors:
        return render_template("client/job_form.html", title=title, capp=capp, form=request.form, errors=errors,
                               editing=job, **_job_form_context()), 400
    submit = request.form.get("action") == "submit"
    _save_job(capp, job, clean, submit)
    log_action("job.submitted" if submit else "job.updated", actor=g.user, target_type="job", target_id=job.job_id)
    db.session.commit()
    flash("Job request " + ("submitted to VerifyTalent Global." if submit else "draft saved."), "success")
    return redirect(url_for("client.job_detail", job_pk=job.id))


@bp.get("/jobs/<int:job_pk>")
@login_required("CLIENT")
def job_detail(job_pk):
    capp = _application()
    job = _own_job(capp, job_pk)
    rows = db.session.execute(
        select(Match, TalentApplication).join(TalentApplication, Match.talent_application_id == TalentApplication.id)
        .where(Match.job_id == job.id, Match.status.in_(PRESENTED_STATUSES)).order_by(Match.score.desc())).all()
    return render_template("client/job_detail.html", title=f"{job.job_id} | VerifyTalent Global", capp=capp, job=job,
                           rows=rows, labels=JOB_STATUS_LABELS, match_labels=MATCH_STATUS_LABELS, score_note=SCORE_NOTE)


@bp.post("/jobs/<int:job_pk>/submit")
@login_required("CLIENT")
def job_submit(job_pk):
    capp = _application()
    job = _own_job(capp, job_pk)
    if job.status == "DRAFT" and _require_active(capp) is not None:
        job.status, job.submitted_at = "SUBMITTED", datetime.now(timezone.utc)
        log_action("job.submitted", actor=g.user, target_type="job", target_id=job.job_id)
        db.session.commit()
        flash("Job request submitted to VerifyTalent Global.", "success")
    return redirect(url_for("client.job_detail", job_pk=job.id))


@bp.post("/jobs/<int:job_pk>/close")
@login_required("CLIENT")
def job_close(job_pk):
    capp = _application()
    job = _own_job(capp, job_pk)
    if job.status not in ("FILLED", "CLOSED"):
        job.status = "CLOSED"
        log_action("job.closed", actor=g.user, target_type="job", target_id=job.job_id)
        db.session.commit()
        flash("Job request closed.", "success")
    return redirect(url_for("client.job_detail", job_pk=job.id))


@bp.post("/jobs/<int:job_pk>/matches/<int:match_pk>/interview")
@login_required("CLIENT")
def request_interview(job_pk, match_pk):
    capp = _application()
    job = _own_job(capp, job_pk)
    match = db.session.scalar(select(Match).where(Match.id == match_pk, Match.job_id == job.id))
    if match is None:
        abort(404)
    if match.status == "PRESENTED" and match.client_decision != "INTERVIEW_REQUESTED":
        match.client_decision = "INTERVIEW_REQUESTED"
        log_action("match.interview_requested", actor=g.user, target_type="job", target_id=job.job_id,
                   meta={"talent_id": match.talent.talent_id})
        db.session.commit()
        flash("Interview requested. Our team will arrange it with the talent.", "success")
    return redirect(url_for("client.job_detail", job_pk=job.id))
