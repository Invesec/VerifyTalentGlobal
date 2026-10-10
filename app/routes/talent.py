from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import select

from ..extensions import db
from ..job_data import MATCH_STATUS_LABELS
from ..models import Job, Match, Notification, TalentApplication, TalentID
from ..security import login_required
from ..talent_data import AVAILABILITY, CATEGORIES, talent_progress
from ..validators import validate_profile
from ..services.audit import log_action
from ..services.qr import qr_svg
from ..talent_data import FIELD_GROUPS, PROFESSION_TO_GROUP, STATUS_LABELS

bp = Blueprint("talent", __name__, url_prefix="/talent")

ONBOARDING = ("APPROVED", "PAYMENT_PENDING")


def _application():
    # Always filtered by the logged-in user, so a talent can never see another talent's data.
    return db.session.scalar(select(TalentApplication).filter_by(user_id=g.user.id))


@bp.get("/dashboard")
@login_required("TALENT")
def dashboard():
    application = _application()
    details = []
    group = PROFESSION_TO_GROUP.get(application.profession)
    if group:
        labels = dict(FIELD_GROUPS[group][2])
        details = [(labels.get(k, k), v) for k, v in (application.details or {}).items()]
    notifications = db.session.scalars(select(Notification).where(Notification.user_id == g.user.id)
                                       .order_by(Notification.created_at.desc()).limit(5)).all()
    steps, current = talent_progress(application.status)
    return render_template("talent/dashboard.html", title="Your dashboard | VerifyTalent Global", steps=steps, current=current,
                           application=application, details=details, notifications=notifications,
                           status_label=STATUS_LABELS.get(application.status, application.status),
                           onboarding=application.status in ONBOARDING)


@bp.get("/onboarding")
@login_required("TALENT")
def onboarding():
    application = _application()
    if application.status not in ONBOARDING:
        flash("Onboarding opens after your application is approved.", "info")
        return redirect(url_for("talent.dashboard"))
    return render_template("talent/onboarding.html", title="Complete your onboarding | VerifyTalent Global",
                           application=application)


@bp.get("/id-card")
@login_required("TALENT")
def id_card():
    application = _application()
    card = db.session.scalar(select(TalentID).where(TalentID.application_id == application.id))
    if card is None or card.status != "ACTIVE":
        flash("Your ID card is not available yet.", "info")
        return redirect(url_for("talent.dashboard"))
    verify_url = url_for("verify.talent", talent_id=card.talent_id, _external=True)
    initials = "".join(part[0] for part in g.user.full_name.split()[:2]).upper()
    return render_template("talent/id_card.html", title="Your ID card | VerifyTalent Global", card=card,
                           application=application, verify_url=verify_url, qr=qr_svg(verify_url), initials=initials)


VISIBLE_MATCH_STATUSES = ("SHORTLISTED", "PRESENTED", "INTERVIEWING", "PLACED")


@bp.get("/opportunities")
@login_required("TALENT")
def opportunities():
    application = _application()
    rows = db.session.execute(select(Match, Job).join(Job, Match.job_id == Job.id)
                              .where(Match.talent_application_id == application.id, Match.status.in_(VISIBLE_MATCH_STATUSES))
                              .order_by(Match.id.desc())).all()
    return render_template("talent/opportunities.html", title="Opportunities | VerifyTalent Global", rows=rows,
                           labels=MATCH_STATUS_LABELS)


@bp.post("/opportunities/<int:match_pk>/respond")
@login_required("TALENT")
def respond(match_pk):
    application = _application()
    # Only the talent's own matches can be answered.
    match = db.session.scalar(select(Match).where(Match.id == match_pk, Match.talent_application_id == application.id))
    answer = request.form.get("response", "")
    if match is None:
        abort(404)
    if answer not in ("INTERESTED", "DECLINED") or match.status not in ("SHORTLISTED", "PRESENTED"):
        flash("This opportunity can no longer be answered.", "error")
    else:
        match.talent_response = answer
        log_action("match.talent_response", actor=g.user, target_type="job", target_id=match.job.job_id, meta={"response": answer})
        db.session.commit()
        flash("Thank you. We have recorded that you are " + ("interested." if answer == "INTERESTED" else "not interested."), "success")
    return redirect(url_for("talent.opportunities"))


PROFILE_FIELDS = ("country", "phone", "years_experience", "skills", "education", "certifications", "portfolio_url",
                  "availability", "expected_rate", "languages", "bio")


@bp.route("/profile", methods=["GET", "POST"])
@login_required("TALENT")
def profile_edit():
    application = _application()
    locked = bool(application.talent_id)  # the profession is printed on the ID card, so it is fixed once issued
    group = PROFESSION_TO_GROUP.get(application.profession)
    ctx = dict(title="Edit your profile | VerifyTalent Global", application=application, locked=locked,
               categories=CATEGORIES, groups=FIELD_GROUPS, group_map=PROFESSION_TO_GROUP, availability=AVAILABILITY)
    if request.method == "GET":
        form = {k: ("" if getattr(application, k) is None else str(getattr(application, k))) for k in PROFILE_FIELDS}
        form["profession"] = application.profession
        for key, value in (application.details or {}).items():
            form[f"{group}__{key}"] = value
        return render_template("talent/profile_edit.html", form=form, errors={}, active_group=group, **ctx)

    posted = request.form.copy()
    if locked:
        posted["profession"] = application.profession
    clean, errors = validate_profile(posted)
    if errors:
        return render_template("talent/profile_edit.html", form=posted, errors=errors,
                               active_group=PROFESSION_TO_GROUP.get(posted.get("profession")), **ctx), 400
    required = ("years_experience", "country", "skills", "availability", "languages")
    for field in PROFILE_FIELDS:
        value = clean[field]
        setattr(application, field, value if field in required else (value or None))  # empty optional fields become NULL
    application.details = clean["details"]
    if not locked:
        application.profession, application.category = clean["profession"], clean["category"]
    log_action("talent.profile_updated", actor=g.user, target_type="talent_application", target_id=application.application_id)
    db.session.commit()
    flash("Your profile has been updated.", "success")
    return redirect(url_for("talent.dashboard"))
