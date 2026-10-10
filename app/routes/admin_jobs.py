from datetime import datetime, timezone

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func, or_, select

from ..extensions import db
from ..job_data import JOB_STATUS_LABELS, MATCH_STATUS_LABELS, SCORE_NOTE
from ..models import AuditLog, ClientApplication, Job, Match, TalentApplication, User
from ..services import email as mail
from ..services.audit import log_action, notify
from ..services.matching import ELIGIBLE_STATUSES, run_matching
from ..validators import parse_interview_time
from .admin import require_admin

bp = Blueprint("admin_jobs", __name__, url_prefix="/admin")
bp.before_request(require_admin)  # every page here needs a logged-in ADMIN

ADMIN_JOB_STATUSES = ["REVIEWING", "MATCHING", "SHORTLISTED", "INTERVIEWING", "FILLED", "CLOSED"]
PER_PAGE = 25


def _job(pk):
    job = db.session.scalar(select(Job).where(Job.id == pk, Job.status != "DRAFT"))  # client drafts stay private
    if job is None:
        abort(404)
    return job


def _back(job):
    return redirect(url_for("admin_jobs.job_detail", pk=job.id))


def _audit(action, job, meta=None):
    log_action(action, actor=g.user, target_type="job", target_id=job.job_id, meta=meta)


@bp.get("/jobs")
def job_list():
    q = (request.args.get("q") or "").strip()[:80]
    status = request.args.get("status", "")
    page_raw = request.args.get("page", "1")
    page = max(int(page_raw) if page_raw.isdigit() else 1, 1)
    stmt = select(Job, ClientApplication).join(ClientApplication, Job.client_application_id == ClientApplication.id).where(Job.status != "DRAFT")
    if q:
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        stmt = stmt.where(or_(Job.title.ilike(like, escape="\\"), Job.job_id.ilike(like, escape="\\"),
                              ClientApplication.company_name.ilike(like, escape="\\")))
    if status in JOB_STATUS_LABELS and status != "DRAFT":
        stmt = stmt.where(Job.status == status)
    rows = db.session.execute(stmt.order_by(Job.id.desc()).limit(PER_PAGE + 1).offset((page - 1) * PER_PAGE)).all()
    return render_template("admin/jobs_list.html", title="Jobs | Admin", rows=rows[:PER_PAGE], has_next=len(rows) > PER_PAGE,
                           page=page, q=q, status=status, labels=JOB_STATUS_LABELS)


@bp.get("/jobs/<int:pk>")
def job_detail(pk):
    job = _job(pk)
    matches = db.session.execute(
        select(Match, TalentApplication, User).join(TalentApplication, Match.talent_application_id == TalentApplication.id)
        .join(User, TalentApplication.user_id == User.id).where(Match.job_id == job.id)
        .order_by(Match.score.desc())).all()
    recruiters = db.session.scalars(select(User).where(User.role.in_(["ADMIN", "RECRUITER"]), User.is_active.is_(True))).all()
    logs = db.session.scalars(select(AuditLog).where(AuditLog.target_id == job.job_id)
                              .order_by(AuditLog.created_at.desc()).limit(15)).all()
    placed = sum(1 for m, _t, _u in matches if m.status == "PLACED")
    return render_template("admin/job_detail.html", title=f"{job.job_id} | Admin", job=job, company=job.client,
                           matches=matches, recruiters=recruiters, logs=logs, placed=placed, labels=JOB_STATUS_LABELS,
                           match_labels=MATCH_STATUS_LABELS, statuses=ADMIN_JOB_STATUSES, score_note=SCORE_NOTE)


@bp.post("/jobs/<int:pk>/status")
def change_status(pk):
    job = _job(pk)
    new = request.form.get("status", "")
    if new not in ADMIN_JOB_STATUSES or new == job.status:
        flash("Nothing to change.", "info")
        return _back(job)
    old, job.status = job.status, new
    _audit("admin.job_status_changed", job, {"from": old, "to": new})
    notify(job.client.user_id, "Job request update", f"{job.job_id} ({job.title}) is now: {JOB_STATUS_LABELS[new]}.")
    db.session.commit()
    flash(f"Status changed to {JOB_STATUS_LABELS[new]}.", "success")
    return _back(job)


@bp.post("/jobs/<int:pk>/assign")
def assign(pk):
    job = _job(pk)
    raw = request.form.get("recruiter", "")
    user = db.session.scalar(select(User).where(User.id == int(raw), User.role.in_(["ADMIN", "RECRUITER"]))) if raw.isdigit() else None
    job.assigned_recruiter = user.id if user else None
    _audit("admin.job_recruiter_assigned", job, {"recruiter": user.email if user else None})
    db.session.commit()
    flash("Recruiter updated.", "success")
    return _back(job)


@bp.post("/jobs/<int:pk>/notes")
def save_notes(pk):
    job = _job(pk)
    job.admin_notes = (request.form.get("admin_notes") or "").strip()[:4000] or None
    _audit("admin.job_notes_updated", job)
    db.session.commit()
    flash("Notes saved.", "success")
    return _back(job)


@bp.post("/jobs/<int:pk>/match")
def match_candidates(pk):
    job = _job(pk)
    if job.status in ("FILLED", "CLOSED"):
        flash("This job request is closed.", "error")
        return _back(job)
    changed = run_matching(job)
    if job.status in ("SUBMITTED", "REVIEWING"):
        job.status = "MATCHING"
    _audit("job.matching_run", job, {"matches_added_or_updated": changed})
    db.session.commit()
    flash(f"Matching finished: {changed} candidate(s) added or updated. Review them before presenting to the client.", "success")
    return _back(job)


# ---- one match at a time ----
def _release_talent(talent):
    """Return a talent to Available when they have no other active match."""
    if talent.status in ("MATCHED", "INTERVIEWING"):
        active = db.session.scalar(select(func.count()).select_from(Match).where(
            Match.talent_application_id == talent.id, Match.status.in_(("SHORTLISTED", "PRESENTED", "INTERVIEWING"))))
        if not active:
            talent.status = "AVAILABLE"


@bp.post("/matches/<int:pk>/<action>")
def match_action(pk, action):
    if action not in ("shortlist", "present", "interview", "place", "reject"):
        abort(404)
    match = db.session.scalar(select(Match).where(Match.id == pk).with_for_update())
    if match is None:
        abort(404)
    job, talent = match.job, match.talent
    if job.status == "DRAFT":
        abort(404)
    user = talent.user
    meta = {"talent_id": talent.talent_id, "score": match.score}
    match.reviewed_by = g.user.id

    if action == "shortlist":
        if match.status != "SUGGESTED":
            flash("Only suggested matches can be shortlisted.", "error")
            return _back(job)
        match.status = "SHORTLISTED"
        if talent.status in ("VERIFIED_TALENT", "AVAILABLE"):
            talent.status = "MATCHED"
        notify(talent.user_id, "New job opportunity", f"You have been shortlisted for: {job.title}. Open Opportunities to respond.")
        message = "Shortlisted."
        after = lambda: mail.send_job_opportunity(user, job)

    elif action == "present":
        if match.status != "SHORTLISTED":
            flash("Shortlist the candidate before presenting them.", "error")
            return _back(job)
        if match.talent_response == "DECLINED":
            flash("This talent declined the opportunity, so they cannot be presented.", "error")
            return _back(job)
        match.status = "PRESENTED"
        if job.status in ("SUBMITTED", "REVIEWING", "MATCHING"):
            job.status = "SHORTLISTED"
        notify(job.client.user_id, "Candidate presented", f"A candidate has been presented for {job.job_id} ({job.title}).")
        message, after = "Presented to the client.", None

    elif action == "interview":
        when = parse_interview_time(request.form.get("interview_at"))
        details = (request.form.get("interview_details") or "").strip()[:1000]
        if match.status != "PRESENTED":
            flash("Present the candidate to the client before scheduling an interview.", "error")
            return _back(job)
        if when is None or len(details) < 3:
            flash("Enter a future date and time (UTC), and the interview details such as a meeting link.", "error")
            return _back(job)
        match.status, match.interview_at, match.interview_details = "INTERVIEWING", when, details
        job.status = "INTERVIEWING" if job.status not in ("FILLED", "CLOSED") else job.status
        if talent.status in ("VERIFIED_TALENT", "AVAILABLE", "MATCHED"):
            talent.status = "INTERVIEWING"
        notify(talent.user_id, "Interview invitation", f"Interview for {job.title}: {when:%d %b %Y %H:%M} UTC.")
        notify(job.client.user_id, "Interview scheduled", f"An interview for {job.job_id} is set for {when:%d %b %Y %H:%M} UTC.")
        message = "Interview scheduled."
        after = lambda: mail.send_interview_invitation(user, job, match)

    elif action == "place":
        if match.status != "INTERVIEWING":
            flash("Only a candidate in the interview stage can be marked as placed.", "error")
            return _back(job)
        match.status, talent.status = "PLACED", "PLACED"
        placed = db.session.scalar(select(func.count()).select_from(Match).where(Match.job_id == job.id, Match.status == "PLACED"))
        if placed >= job.workers_needed:
            job.status = "FILLED"
        notify(talent.user_id, "Placement confirmed", f"Your placement for {job.title} has been confirmed.")
        notify(job.client.user_id, "Placement confirmed", f"A placement for {job.job_id} has been confirmed.")
        message = "Marked as placed." + (" The job request is now filled." if job.status == "FILLED" else "")
        after = lambda: mail.send_placement(user, job, job.client.company_name)

    else:  # reject
        if match.status in ("PLACED", "REJECTED"):
            flash("This match is already closed.", "error")
            return _back(job)
        match.status = "REJECTED"
        _release_talent(talent)
        message, after = "Match closed.", None

    log_action(f"match.{action}", actor=g.user, target_type="job", target_id=job.job_id, meta=meta)
    db.session.commit()
    emailed = after() if after else False
    flash(message + (" Email sent." if emailed else ""), "success")
    return _back(job)
