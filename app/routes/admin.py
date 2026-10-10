from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import Blueprint, Response, abort, current_app, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func, or_, select

from ..extensions import db
from ..models import AuditLog, ClientApplication, Job, TalentApplication, TalentID, User
from ..services import demo, verification
from ..services.backup import build_backup_zip
from ..services import email as mail
from ..services.audit import log_action, notify
from ..talent_data import CATEGORIES, STATUS_LABELS

bp = Blueprint("admin", __name__, url_prefix="/admin")

PRE_STATUSES = ["NEW", "SCREENING", "ASSESSMENT", "INTERVIEW", "VERIFICATION", "REJECTED"]
POST_STATUSES = ["AVAILABLE", "MATCHED", "INTERVIEWING", "PLACED", "UNAVAILABLE"]  # once a Talent ID exists
ONBOARDING = ("APPROVED", "PAYMENT_PENDING")
CURRENCIES = ["USD", "NGN", "EUR", "GBP", "USDT"]
METHODS = ["Bank transfer", "Crypto", "Mobile money", "Cash deposit", "Other"]
PAYMENT_LABELS = {"NOT_REQUIRED": "Not required", "PENDING": "Pending", "SUBMITTED": "Submitted",
                  "VERIFIED": "Verified", "REJECTED": "Rejected"}
PER_PAGE = 25


@bp.before_request
def require_admin():
    """Every /admin page requires a logged-in ADMIN."""
    if g.user is None:
        flash("Please log in to continue.", "info")
        return redirect(url_for("auth.login", next=request.path))
    if g.user.role != "ADMIN":
        abort(403)


def _row(app_pk, lock=False):
    stmt = select(TalentApplication).where(TalentApplication.id == app_pk)
    if lock:
        stmt = stmt.with_for_update()  # blocks a second admin confirming the same payment at once
    row = db.session.scalar(stmt)
    if row is None:
        abort(404)
    return row


def _back(row):
    return redirect(url_for("admin.talent_detail", app_pk=row.id))


def _audit(action, row, meta=None):
    log_action(action, actor=g.user, target_type="talent_application", target_id=row.application_id, meta=meta)


@bp.get("")
def dashboard():
    counts = dict(db.session.execute(select(TalentApplication.status, func.count()).group_by(TalentApplication.status)).all())
    awaiting_payment = db.session.scalar(select(func.count()).select_from(TalentApplication)
                                         .where(TalentApplication.payment_status.in_(["PENDING", "SUBMITTED"])))
    client_counts = dict(db.session.execute(select(ClientApplication.status, func.count()).group_by(ClientApplication.status)).all())
    job_counts = dict(db.session.execute(select(Job.status, func.count()).group_by(Job.status)).all())
    demo_count = db.session.scalar(select(func.count()).select_from(User).where(User.email.like(f"%{mail.DEMO_DOMAIN}")))
    recent = db.session.execute(select(TalentApplication, User).join(User, TalentApplication.user_id == User.id)
                                .order_by(TalentApplication.created_at.desc()).limit(5)).all()
    return render_template("admin/dashboard.html", title="Admin | VerifyTalent Global", counts=counts,
                           total=sum(counts.values()), awaiting_payment=awaiting_payment or 0,
                           demo_count=demo_count or 0, client_counts=client_counts, job_counts=job_counts, recent=recent, labels=STATUS_LABELS)


@bp.get("/talent")
def talent_list():
    q = (request.args.get("q") or "").strip()[:80]
    status = request.args.get("status", "")
    payment = request.args.get("payment", "")
    page = max(int(request.args.get("page", "1")) if request.args.get("page", "1").isdigit() else 1, 1)
    stmt = select(TalentApplication, User).join(User, TalentApplication.user_id == User.id)
    if q:
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        stmt = stmt.where(or_(User.full_name.ilike(like, escape="\\"), User.email.ilike(like, escape="\\"),
                              TalentApplication.application_id.ilike(like, escape="\\"),
                              TalentApplication.talent_id.ilike(like, escape="\\"),
                              TalentApplication.profession.ilike(like, escape="\\")))
    if status in STATUS_LABELS:
        stmt = stmt.where(TalentApplication.status == status)
    if payment in PAYMENT_LABELS:
        stmt = stmt.where(TalentApplication.payment_status == payment)
    rows = db.session.execute(stmt.order_by(TalentApplication.created_at.desc())
                              .limit(PER_PAGE + 1).offset((page - 1) * PER_PAGE)).all()
    return render_template("admin/talent_list.html", title="Talent | Admin", rows=rows[:PER_PAGE],
                           has_next=len(rows) > PER_PAGE, page=page, q=q, status=status, payment=payment,
                           labels=STATUS_LABELS, payment_labels=PAYMENT_LABELS, demo_domain=mail.DEMO_DOMAIN)


@bp.get("/talent/<int:app_pk>")
def talent_detail(app_pk):
    row = _row(app_pk)
    card = db.session.scalar(select(TalentID).where(TalentID.application_id == row.id))
    logs = db.session.scalars(select(AuditLog).where(AuditLog.target_id == row.application_id)
                              .order_by(AuditLog.created_at.desc()).limit(15)).all()
    return render_template("admin/talent_detail.html", title=f"{row.application_id} | Admin", row=row, user=row.user,
                           card=card, logs=logs, labels=STATUS_LABELS, payment_labels=PAYMENT_LABELS,
                           statuses=POST_STATUSES if row.talent_id else PRE_STATUSES, currencies=CURRENCIES,
                           methods=METHODS, onboarding=row.status in ONBOARDING, demo_domain=mail.DEMO_DOMAIN,
                           email_verified=verification.is_verified(row.user), verify_on=verification.required(current_app.config))


@bp.post("/talent/<int:app_pk>/status")
def change_status(app_pk):
    row = _row(app_pk)
    new = request.form.get("status", "")
    if new not in (POST_STATUSES if row.talent_id else PRE_STATUSES):
        flash("That status cannot be set here.", "error")
        return _back(row)
    if new == row.status:
        flash("The talent already has that status.", "info")
        return _back(row)
    old, row.status = row.status, new
    message = (request.form.get("message") or "").strip()[:1000]
    _audit("admin.status_changed", row, {"from": old, "to": new})
    notify(row.user_id, "Application update", f"Your application status is now: {STATUS_LABELS[new]}.")
    db.session.commit()
    emailed = False
    if request.form.get("send_email") == "yes" and not row.talent_id:
        emailed = mail.send_status_email(new, row.user, message)
    flash(f"Status changed to {STATUS_LABELS[new]}." + (" Email sent." if emailed else ""), "success")
    return _back(row)


@bp.post("/talent/<int:app_pk>/approve")
def approve(app_pk):
    row = _row(app_pk)
    if row.talent_id or row.status in ONBOARDING:
        flash("This talent is already approved.", "info")
        return _back(row)
    row.status, row.payment_status = "APPROVED", "PENDING"
    row.payment_amount, row.payment_currency = Decimal("60.00"), "USD"
    _audit("admin.approved", row)
    notify(row.user_id, "Application approved", "You passed our initial review. Open Onboarding on your dashboard for the next step.")
    db.session.commit()
    emailed = mail.send_approved(row.user, row, (request.form.get("message") or "").strip()[:1000])
    flash("Application approved." + (" Email sent." if emailed else ""), "success")
    return _back(row)


@bp.post("/talent/<int:app_pk>/send-instructions")
def send_instructions(app_pk):
    row = _row(app_pk)
    if row.status not in ONBOARDING:
        flash("Approve the talent first.", "error")
        return _back(row)
    row.status = "PAYMENT_PENDING"
    if row.payment_status == "NOT_REQUIRED":
        row.payment_status = "PENDING"
    _audit("admin.onboarding_instructions_sent", row)
    db.session.commit()
    emailed = mail.send_onboarding(row.user, row)
    flash("Onboarding instructions " + ("emailed." if emailed else "recorded (email not sent: Brevo not configured, or a demo account)."), "success")
    return _back(row)


@bp.post("/talent/<int:app_pk>/notes")
def save_notes(app_pk):
    row = _row(app_pk)
    row.admin_notes = (request.form.get("admin_notes") or "").strip()[:4000] or None
    _audit("admin.notes_updated", row)
    db.session.commit()
    flash("Notes saved.", "success")
    return _back(row)


def _payment_form(form, strict):
    """Returns (values, error). Strict is used when confirming a payment."""
    reference = (form.get("reference") or "").strip()[:120]
    method = (form.get("method") or "").strip()
    currency = (form.get("currency") or "USD").strip()
    try:
        amount = Decimal((form.get("amount") or "60").strip()).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None, "Enter the amount as a number, for example 60.00."
    if not Decimal("0") < amount <= Decimal("100000"):
        return None, "The amount must be greater than 0."
    if currency not in CURRENCIES:
        return None, "Choose a currency."
    if method and method not in METHODS:
        return None, "Choose a payment method."
    if strict and (len(reference) < 3 or not method):
        return None, "A payment reference (at least 3 characters) and a payment method are required to confirm."
    return dict(reference=reference or None, method=method or None, currency=currency, amount=amount), None


@bp.post("/talent/<int:app_pk>/payment/<action>")
def payment_action(app_pk, action):
    if action not in ("submitted", "confirm", "reject"):
        abort(404)
    row = _row(app_pk, lock=(action == "confirm"))
    if row.status not in ONBOARDING or row.talent_id or row.payment_status == "VERIFIED":
        flash("Payment can only be recorded for an approved talent who has not been verified yet.", "error")
        return _back(row)
    values, error = _payment_form(request.form, strict=(action == "confirm"))
    if error:
        flash(error, "error")
        return _back(row)
    note = (request.form.get("payment_note") or "").strip()[:500]

    if action == "submitted":
        row.payment_status, row.payment_submitted_at = "SUBMITTED", datetime.now(timezone.utc)
        row.payment_reference, row.payment_method = values["reference"], values["method"]
        row.payment_amount, row.payment_currency = values["amount"], values["currency"]
        _audit("payment.submitted", row, {"reference": values["reference"]})
        db.session.commit()
        flash("Payment marked as submitted. It is not verified yet.", "success")
        return _back(row)

    if action == "reject":
        row.payment_status = "REJECTED"
        _audit("payment.rejected", row, {"reason": note})
        notify(row.user_id, "Payment not verified",
               "We could not verify your payment. Contact the VerifyTalent Global administrator and quote your Application ID.")
        db.session.commit()
        flash("Payment rejected. The talent has been notified in their dashboard.", "success")
        return _back(row)

    # ---- Confirm payment: everything below succeeds together or not at all ----
    try:
        now = datetime.now(timezone.utc)
        row.payment_status = "VERIFIED"
        row.payment_reference, row.payment_method = values["reference"], values["method"]
        row.payment_amount, row.payment_currency = values["amount"], values["currency"]
        row.payment_verified_at, row.payment_verified_by = now, g.user.id
        row.status, row.verification_status = "VERIFIED_TALENT", "VERIFIED"
        card = TalentID(application_id=row.id, issued_by=g.user.id, issued_at=now, status="ACTIVE")
        db.session.add(card)
        db.session.flush()
        card.talent_id = f"VTG-TL-{card.id:06d}"  # generated on the server
        row.talent_id = card.talent_id
        if note:
            row.admin_notes = ((row.admin_notes or "") + f"\n[{now:%Y-%m-%d}] Payment: {note}").strip()
        _audit("payment.verified", row, {"reference": values["reference"], "amount": str(values["amount"]), "currency": values["currency"]})
        _audit("talent_id.issued", row, {"talent_id": card.talent_id})
        _audit("talent.verified", row)
        notify(row.user_id, "Payment confirmed", "Your onboarding payment has been confirmed.")
        notify(row.user_id, "ID card ready", f"Your Talent ID is {card.talent_id}. Open ID Card on your dashboard.")
        db.session.commit()
    except Exception:
        db.session.rollback()  # nothing is left half-done
        flash("Something went wrong and nothing was changed. Please try again.", "error")
        return _back(row)

    mail.send_payment_confirmed(row.user, row)
    mail.send_id_ready(row.user, row)
    flash(f"Payment confirmed. Talent ID {row.talent_id} issued.", "success")
    return _back(row)


@bp.post("/talent/<int:app_pk>/suspend")
def suspend(app_pk):
    row = _row(app_pk)
    row.user.is_active, row.status = False, "UNAVAILABLE"
    card = db.session.scalar(select(TalentID).where(TalentID.application_id == row.id))
    if card:
        card.status = "SUSPENDED"
    _audit("admin.suspended", row)
    db.session.commit()
    flash("Talent suspended. They can no longer log in and their ID shows as not valid.", "success")
    return _back(row)


@bp.post("/talent/<int:app_pk>/reinstate")
def reinstate(app_pk):
    row = _row(app_pk)
    row.user.is_active = True
    card = db.session.scalar(select(TalentID).where(TalentID.application_id == row.id))
    if card and card.status == "SUSPENDED":
        card.status = "ACTIVE"
    _audit("admin.reinstated", row)
    db.session.commit()
    flash("Talent reinstated. Set their status below if it needs changing.", "success")
    return _back(row)


@bp.get("/payments")
def payments():
    rows = db.session.execute(select(TalentApplication, User).join(User, TalentApplication.user_id == User.id)
                              .where(TalentApplication.payment_status.in_(["PENDING", "SUBMITTED", "REJECTED"]))
                              .order_by(TalentApplication.updated_at.desc()).limit(100)).all()
    return render_template("admin/payments.html", title="Payments | Admin", rows=rows,
                           labels=STATUS_LABELS, payment_labels=PAYMENT_LABELS)


@bp.get("/audit")
def audit():
    logs = db.session.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100)).all()
    return render_template("admin/audit.html", title="Audit log | Admin", logs=logs)


@bp.post("/demo/seed")
def demo_seed():
    flash(f"Added {demo.seed_demo()} demo talents.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.post("/demo/reset")
def demo_reset():
    if request.form.get("confirm") != "yes":
        abort(400)
    removed = demo.reset_demo()
    log_action("demo.reset", actor=g.user, meta={"accounts": removed})
    db.session.commit()
    flash(f"Removed {removed} demo accounts and everything attached to them.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.post("/users/<int:user_id>/verify-email")
def verify_user_email(user_id):
    """For when a person cannot receive the code. Recorded in the audit log."""
    user = db.session.get(User, user_id)
    if user is None or user.role not in verification.VERIFIED_ROLES:
        abort(404)
    verification.mark_verified(user)
    log_action("admin.email_verified_manually", actor=g.user, target_type="user", target_id=user.id, meta={"email": user.email})
    db.session.commit()
    flash(f"{user.email} marked as verified.", "success")
    from ..security import safe_next
    return redirect(safe_next(request.form.get("back"), "admin.dashboard"))


@bp.get("/backup")
def backup():
    return render_template("admin/backup.html", title="Backup | Admin")


@bp.post("/backup/download")
def backup_download():
    data, filename = build_backup_zip()
    log_action("admin.backup_downloaded", actor=g.user, meta={"file": filename})
    db.session.commit()
    return Response(data, mimetype="application/zip", headers={
        "Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})
