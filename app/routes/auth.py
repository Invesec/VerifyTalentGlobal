import re
from datetime import datetime, timezone

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash

from ..extensions import db
from ..models import ClientApplication, TalentApplication, User
from ..security import hash_password, login_required, rate_limit, safe_next
from ..services.audit import log_action
from ..services import verification
from ..services.email import (send_application_received, send_client_received, send_password_reset,
                              send_verification_code)
from ..services.tokens import make_reset_token, read_reset_token
from ..client_data import COMPANY_SIZES
from ..talent_data import AVAILABILITY, CATEGORIES, FIELD_GROUPS, PROFESSION_TO_GROUP
from ..validators import validate_client_registration, validate_new_password, validate_registration

bp = Blueprint("auth", __name__)

def home_for(user):
    return {"ADMIN": "admin.dashboard", "TALENT": "talent.dashboard", "CLIENT": "client.dashboard"}.get(user.role, "main.home")


# Used so that unknown emails take the same time as wrong passwords.
_DUMMY_HASH = hash_password("not-a-real-password")


def _start_session(user):
    session.clear()  # new session on login prevents session fixation
    session["user_id"] = user.id
    session.permanent = True


def _begin_verification(user):
    """Sends the first code. Returns True when the user must now verify their email."""
    if not verification.required(current_app.config):
        return False
    code = verification.issue_code(user)
    log_action("email.verification_sent", actor=user, target_type="user", target_id=user.id)
    db.session.commit()
    if code:
        send_verification_code(user, code)
    return True


@bp.route("/register", methods=["GET", "POST"])
@rate_limit("register", 20, 3600)
def register():
    if g.user:
        return redirect(url_for(home_for(g.user)))
    context = dict(categories=CATEGORIES, groups=FIELD_GROUPS, group_map=PROFESSION_TO_GROUP,
                   availability=AVAILABILITY, title="Join the talent network | VerifyTalent Global")
    if request.method == "GET":
        return render_template("auth/register.html", form={}, errors={}, **context)

    clean, errors = validate_registration(request.form)
    if errors:
        return render_template("auth/register.html", form=request.form, errors=errors, **context), 400

    user = User(email=clean["email"], full_name=clean["full_name"], role="TALENT",
                password_hash=hash_password(clean["password"]))
    application = TalentApplication(
        user=user, category=clean["category"], profession=clean["profession"], country=clean["country"],
        phone=clean["phone"] or None, years_experience=clean["years_experience"], skills=clean["skills"],
        education=clean["education"] or None, certifications=clean["certifications"] or None,
        portfolio_url=clean["portfolio_url"] or None, availability=clean["availability"],
        expected_rate=clean["expected_rate"] or None, languages=clean["languages"],
        bio=clean["bio"] or None, details=clean["details"],
        status="NEW", verification_status="UNVERIFIED", payment_status="NOT_REQUIRED",
    )
    try:
        db.session.add(application)
        db.session.flush()  # assigns the database id
        application.application_id = f"VTG-APP-{application.id:06d}"  # generated on the server, never from the form
        log_action("user.registered", actor=user, target_type="user", target_id=user.id)
        log_action("talent.application_created", actor=user, target_type="talent_application",
                   target_id=application.application_id, meta={"profession": clean["profession"]})
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        errors["email"] = "An account with this email already exists. Log in instead."
        return render_template("auth/register.html", form=request.form, errors=errors, **context), 400

    send_application_received(user, application)  # logs instead of crashing if Brevo is unavailable
    _start_session(user)
    flash(f"Application received. Your Application ID is {application.application_id}.", "success")
    if _begin_verification(user):
        return redirect(url_for("auth.verify_email"))
    return redirect(url_for("talent.dashboard"))


@bp.route("/register/company", methods=["GET", "POST"])
@rate_limit("register_company", 20, 3600)
def register_company():
    if g.user:
        return redirect(url_for(home_for(g.user)))
    title = "Hire talent: register your company | VerifyTalent Global"
    if request.method == "GET":
        return render_template("auth/register_company.html", form={}, errors={}, sizes=COMPANY_SIZES, title=title)

    clean, errors = validate_client_registration(request.form)
    if errors:
        return render_template("auth/register_company.html", form=request.form, errors=errors, sizes=COMPANY_SIZES, title=title), 400

    user = User(email=clean["business_email"], full_name=clean["contact_name"], role="CLIENT",
                password_hash=hash_password(clean["password"]))
    capp = ClientApplication(
        user=user, company_name=clean["company_name"], website=clean["website"] or None, industry=clean["industry"],
        country=clean["country"], company_size=clean["company_size"], contact_name=clean["contact_name"],
        job_title=clean["job_title"], business_email=clean["business_email"], phone=clean["phone"] or None,
        linkedin_url=clean["linkedin_url"] or None, description=clean["description"] or None,
        recruitment_needs=clean["recruitment_needs"], status="NEW",
    )
    try:
        db.session.add(capp)
        db.session.flush()
        capp.application_id = f"VTG-APP-CLIENT-{capp.id:06d}"  # no Client ID yet: that comes at activation
        log_action("user.registered", actor=user, target_type="user", target_id=user.id)
        log_action("client.application_created", actor=user, target_type="client_application",
                   target_id=capp.application_id, meta={"company": clean["company_name"]})
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        errors["business_email"] = "An account with this email already exists. Log in instead."
        return render_template("auth/register_company.html", form=request.form, errors=errors, sizes=COMPANY_SIZES, title=title), 400

    send_client_received(user, capp)
    _start_session(user)
    flash(f"Application received. Your Application ID is {capp.application_id}.", "success")
    if _begin_verification(user):
        return redirect(url_for("auth.verify_email"))
    return redirect(url_for("client.dashboard"))


@bp.route("/login", methods=["GET", "POST"])
@rate_limit("login", 10, 900)
def login():
    if g.user:
        return redirect(url_for(home_for(g.user)))
    if request.method == "GET":
        return render_template("auth/login.html", title="Log in | VerifyTalent Global", email="", error=None)

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    user = db.session.scalar(db.select(User).filter_by(email=email))
    valid = check_password_hash(user.password_hash if user else _DUMMY_HASH, password)
    if not (user and valid and user.is_active):
        log_action("auth.login_failed", meta={"email": email[:254]})
        db.session.commit()
        return render_template("auth/login.html", title="Log in | VerifyTalent Global", email=email,
                               error="The email or password is incorrect."), 401

    user.last_login_at = datetime.now(timezone.utc)
    log_action("auth.login", actor=user, target_type="user", target_id=user.id)
    db.session.commit()
    _start_session(user)
    return redirect(safe_next(request.args.get("next"), home_for(user)))


@bp.post("/logout")
def logout():
    if g.user:
        log_action("auth.logout", actor=g.user, target_type="user", target_id=g.user.id)
        db.session.commit()
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.home"))


@bp.route("/forgot-password", methods=["GET", "POST"])
@rate_limit("forgot", 10, 3600)
def forgot_password():
    title = "Forgot your password? | VerifyTalent Global"
    if request.method == "GET":
        return render_template("auth/forgot.html", title=title, sent=False)
    email = (request.form.get("email") or "").strip().lower()[:254]
    user = db.session.scalar(select(User).filter_by(email=email)) if email else None
    if user and user.is_active:
        link = url_for("auth.reset_password", token=make_reset_token(user), _external=True)
        log_action("auth.password_reset_requested", actor=user, target_type="user", target_id=user.id)
        db.session.commit()
        sent = send_password_reset(user, link)
        if not sent and not current_app.config["IS_PROD"]:
            current_app.logger.info("DEV ONLY reset link for %s: %s", email, link)  # never logged in production
    # The same answer whether or not the account exists, so nobody can probe for registered emails.
    return render_template("auth/forgot.html", title=title, sent=True)


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
@rate_limit("reset", 10, 3600)
def reset_password(token):
    title = "Choose a new password | VerifyTalent Global"
    user = read_reset_token(token)
    if user is None:
        return render_template("auth/reset.html", title=title, valid=False, errors={}, form={}), 400
    if request.method == "GET":
        return render_template("auth/reset.html", title=title, valid=True, errors={}, form={})
    errors = validate_new_password(request.form.get("password") or "", request.form.get("confirm_password") or "", user.email)
    if errors:
        return render_template("auth/reset.html", title=title, valid=True, errors=errors, form={}), 400
    user.password_hash = hash_password(request.form["password"])  # the old link stops working now
    log_action("auth.password_reset", actor=user, target_type="user", target_id=user.id)
    verification.mark_verified(user)  # they received the link at this address
    db.session.commit()
    session.clear()
    flash("Your password has been changed. Please log in.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/verify-email", methods=["GET", "POST"])
@login_required()
@rate_limit("verify_email", 30, 3600)
def verify_email():
    user, now = g.user, datetime.now(timezone.utc)
    if (user.role not in verification.VERIFIED_ROLES or not verification.required(current_app.config)
            or verification.is_verified(user)):
        session["ev"] = True
        return redirect(url_for(home_for(user)))
    record = verification.get_record(user)
    error = None
    if request.method == "POST":
        code = re.sub(r"\D", "", request.form.get("code") or "")
        result = verification.evaluate_code(record, code, current_app.config["SECRET_KEY"], user.id, now)
        if result == "ok":
            verification.mark_verified(user, now)
            log_action("email.verified", actor=user, target_type="user", target_id=user.id)
            db.session.commit()
            session["ev"] = True
            flash("Your email address is verified. Thank you.", "success")
            return redirect(url_for(home_for(user)))
        if result == "wrong":
            record.attempts += 1
            db.session.commit()
            left = max(verification.MAX_ATTEMPTS - record.attempts, 0)
            error = f"That code is not correct. {left} attempt{'s' if left != 1 else ''} left." if left else \
                "Too many wrong attempts. Please request a new code."
        elif result == "expired":
            error = "That code has expired. Please request a new one."
        elif result == "locked":
            error = "Too many wrong attempts. Please request a new code."
        else:
            error = "Request a code first."
    return render_template("auth/verify_email.html", title="Verify your email | VerifyTalent Global", error=error,
                           masked=verification.mask_email(user.email), has_code=bool(record and record.code_hash),
                           cooldown=verification.cooldown_remaining(record, now)), (400 if error else 200)


@bp.post("/verify-email/resend")
@login_required()
@rate_limit("resend_code", 10, 3600)
def verify_email_resend():
    user = g.user
    if user.role in verification.VERIFIED_ROLES and verification.required(current_app.config) \
            and not verification.is_verified(user):
        code = verification.issue_code(user)
        if code is None:
            flash("A code was sent a moment ago. Please wait a minute before asking for another.", "info")
        else:
            log_action("email.verification_sent", actor=user, target_type="user", target_id=user.id)
            db.session.commit()
            sent = send_verification_code(user, code)
            flash("We sent you a new code." if sent else "Your code was created. If you do not receive an email, contact support.", "success")
    return redirect(url_for("auth.verify_email"))
