from datetime import datetime, timezone

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import or_, select

from ..client_data import AGREEMENT_STATUS_LABELS, AGREEMENT_TYPES, CLIENT_STATUS_LABELS
from ..extensions import db
from ..models import Agreement, AuditLog, Client, ClientApplication, User
from flask import current_app

from ..services import email as mail
from ..services import verification
from ..services.audit import log_action, notify
from ..validators import validate_agreement
from .admin import require_admin

bp = Blueprint("admin_clients", __name__, url_prefix="/admin")
bp.before_request(require_admin)  # every page here needs a logged-in ADMIN

PRE_STATUSES = ["NEW", "UNDER_REVIEW", "REJECTED"]
POST_STATUSES = ["ACTIVE", "SUSPENDED", "EXPIRED"]  # once a Client ID exists
AGREEMENT_ADMIN_STATUSES = ["PENDING", "SENT", "VIEWED", "ACCEPTED", "DECLINED", "EXPIRED"]
PER_PAGE = 25


def _row(pk, lock=False):
    stmt = select(ClientApplication).where(ClientApplication.id == pk)
    if lock:
        stmt = stmt.with_for_update()
    row = db.session.scalar(stmt)
    if row is None:
        abort(404)
    return row


def _latest_agreement(capp):
    return db.session.scalar(select(Agreement).where(Agreement.client_application_id == capp.id)
                             .order_by(Agreement.id.desc()).limit(1))


def _client(capp):
    return db.session.scalar(select(Client).where(Client.application_id == capp.id))


def _back(capp):
    return redirect(url_for("admin_clients.client_detail", pk=capp.id))


def _audit(action, capp, meta=None):
    log_action(action, actor=g.user, target_type="client_application", target_id=capp.application_id, meta=meta)


@bp.get("/clients")
def client_list():
    q = (request.args.get("q") or "").strip()[:80]
    status = request.args.get("status", "")
    page_raw = request.args.get("page", "1")
    page = max(int(page_raw) if page_raw.isdigit() else 1, 1)
    stmt = select(ClientApplication)
    if q:
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        stmt = stmt.where(or_(ClientApplication.company_name.ilike(like, escape="\\"),
                              ClientApplication.application_id.ilike(like, escape="\\"),
                              ClientApplication.business_email.ilike(like, escape="\\")))
    if status in CLIENT_STATUS_LABELS:
        stmt = stmt.where(ClientApplication.status == status)
    rows = db.session.scalars(stmt.order_by(ClientApplication.created_at.desc())
                              .limit(PER_PAGE + 1).offset((page - 1) * PER_PAGE)).all()
    return render_template("admin/clients_list.html", title="Companies | Admin", rows=rows[:PER_PAGE],
                           has_next=len(rows) > PER_PAGE, page=page, q=q, status=status,
                           labels=CLIENT_STATUS_LABELS, demo_domain=mail.DEMO_DOMAIN)


@bp.get("/clients/<int:pk>")
def client_detail(pk):
    capp = _row(pk)
    client = _client(capp)
    agreement = _latest_agreement(capp)
    logs = db.session.scalars(select(AuditLog).where(AuditLog.target_id.in_(
        [capp.application_id] + ([agreement.agreement_id] if agreement else [])))
        .order_by(AuditLog.created_at.desc()).limit(15)).all()
    return render_template("admin/client_detail.html", title=f"{capp.company_name} | Admin", capp=capp, client=client,
                           agreement=agreement, logs=logs, labels=CLIENT_STATUS_LABELS,
                           agreement_labels=AGREEMENT_STATUS_LABELS, agreement_types=AGREEMENT_TYPES,
                           statuses=POST_STATUSES if client else PRE_STATUSES,
                           agreement_statuses=AGREEMENT_ADMIN_STATUSES, demo_domain=mail.DEMO_DOMAIN,
                           email_verified=verification.is_verified(capp.user), verify_on=verification.required(current_app.config),
                           can_prepare=capp.status in ("APPROVED", "AGREEMENT_PENDING", "AGREEMENT_SENT"),
                           can_activate=capp.status == "AGREEMENT_ACCEPTED" and client is None
                           and agreement is not None and agreement.status == "ACCEPTED")


@bp.post("/clients/<int:pk>/status")
def change_status(pk):
    capp = _row(pk)
    client = _client(capp)
    new = request.form.get("status", "")
    if new not in (POST_STATUSES if client else PRE_STATUSES):
        flash("That status cannot be set here.", "error")
        return _back(capp)
    if new == capp.status:
        flash("The company already has that status.", "info")
        return _back(capp)
    old, capp.status = capp.status, new
    if client:
        client.membership_status = {"ACTIVE": "ACTIVE", "SUSPENDED": "SUSPENDED", "EXPIRED": "EXPIRED"}[new]
    _audit("admin.client_status_changed", capp, {"from": old, "to": new})
    notify(capp.user_id, "Account update", f"Your account status is now: {CLIENT_STATUS_LABELS[new]}.")
    db.session.commit()
    flash(f"Status changed to {CLIENT_STATUS_LABELS[new]}.", "success")
    return _back(capp)


@bp.post("/clients/<int:pk>/approve")
def approve(pk):
    capp = _row(pk)
    if capp.status not in ("NEW", "UNDER_REVIEW", "REJECTED"):
        flash("This company is already approved.", "info")
        return _back(capp)
    capp.status = "APPROVED"
    _audit("admin.client_approved", capp)
    notify(capp.user_id, "Application approved", "Your company application was approved. We will send your agreement next.")
    db.session.commit()
    emailed = mail.send_client_approved(capp.user, capp, (request.form.get("message") or "").strip()[:1000])
    flash("Company approved." + (" Email sent." if emailed else ""), "success")
    return _back(capp)


@bp.post("/clients/<int:pk>/notes")
def save_notes(pk):
    capp = _row(pk)
    capp.admin_notes = (request.form.get("admin_notes") or "").strip()[:4000] or None
    _audit("admin.client_notes_updated", capp)
    db.session.commit()
    flash("Notes saved.", "success")
    return _back(capp)


@bp.post("/clients/<int:pk>/agreement/<action>")
def save_agreement(pk, action):
    """action 'pending' saves a draft record; 'send' sends it to the client."""
    if action not in ("pending", "send"):
        abort(404)
    capp = _row(pk)
    if capp.status not in ("APPROVED", "AGREEMENT_PENDING", "AGREEMENT_SENT"):
        flash("Approve the company before preparing an agreement.", "error")
        return _back(capp)
    clean, errors = validate_agreement(request.form, require_document=(action == "send"))
    if errors:
        flash(" ".join(errors.values()), "error")
        return _back(capp)
    agreement = _latest_agreement(capp)
    if agreement and agreement.status == "ACCEPTED":
        flash("The latest agreement is already accepted.", "error")
        return _back(capp)
    if agreement is None or agreement.status == "EXPIRED":
        agreement = Agreement(client_application_id=capp.id, agreement_type=clean["agreement_type"], status="PENDING")
        db.session.add(agreement)
        db.session.flush()
        agreement.agreement_id = f"VTG-CON-{agreement.id:06d}"  # generated on the server
    agreement.agreement_type = clean["agreement_type"]
    agreement.document_reference = clean["document_reference"] or None
    agreement.expires_at = clean["expires_at"]
    agreement.notes = clean["notes"] or None
    if action == "send":
        agreement.status, agreement.sent_at, agreement.viewed_at = "SENT", datetime.now(timezone.utc), None
        capp.status = "AGREEMENT_SENT"
        notify(capp.user_id, "Agreement ready", "Your client agreement is ready. Open Agreements to review it.")
    else:
        agreement.status = "PENDING"
        capp.status = "AGREEMENT_PENDING"
    log_action(f"agreement.{'sent' if action == 'send' else 'saved'}", actor=g.user, target_type="agreement",
               target_id=agreement.agreement_id, meta={"company": capp.application_id})
    db.session.commit()
    emailed = mail.send_agreement_sent(capp.user, capp, agreement) if action == "send" else False
    flash("Agreement sent to the client." + (" Email sent." if emailed else "") if action == "send" else "Agreement saved as pending.", "success")
    return _back(capp)


@bp.post("/clients/<int:pk>/agreement-status")
def agreement_status(pk):
    capp = _row(pk)
    agreement = _latest_agreement(capp)
    new = request.form.get("agreement_status", "")
    if agreement is None or new not in AGREEMENT_ADMIN_STATUSES or new == agreement.status:
        flash("Nothing to change.", "info")
        return _back(capp)
    old, agreement.status = agreement.status, new
    if new == "ACCEPTED":  # for example a signed copy returned outside the portal
        agreement.accepted_at = datetime.now(timezone.utc)
        agreement.accepted_by_name = f"Recorded by admin ({g.user.email})"
        if capp.status in ("APPROVED", "AGREEMENT_PENDING", "AGREEMENT_SENT"):
            capp.status = "AGREEMENT_ACCEPTED"
    log_action("agreement.status_changed", actor=g.user, target_type="agreement", target_id=agreement.agreement_id,
               meta={"from": old, "to": new})
    db.session.commit()
    flash(f"Agreement status changed to {AGREEMENT_STATUS_LABELS[new]}.", "success")
    return _back(capp)


@bp.post("/clients/<int:pk>/activate")
def activate(pk):
    capp = _row(pk, lock=True)  # lock so two admins cannot activate the same company twice
    agreement = _latest_agreement(capp)
    if (capp.status != "AGREEMENT_ACCEPTED" or _client(capp) is not None
            or agreement is None or agreement.status != "ACCEPTED"):
        flash("A client can only be activated when it is approved and its agreement is accepted.", "error")
        return _back(capp)
    try:
        client = Client(application_id=capp.id, membership_status="ACTIVE", activated_by=g.user.id,
                        activated_at=datetime.now(timezone.utc), membership_expires_at=agreement.expires_at)
        db.session.add(client)
        db.session.flush()
        client.client_id = f"VTG-CL-{client.id:06d}"  # generated on the server, only now
        capp.status = "ACTIVE"
        _audit("client.activated", capp, {"client_id": client.client_id, "agreement": agreement.agreement_id})
        notify(capp.user_id, "Account active", f"Your account is active. Your Client ID is {client.client_id}.")
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Something went wrong and nothing was changed. Please try again.", "error")
        return _back(capp)
    mail.send_client_activated(capp.user, capp, client, agreement)
    flash(f"Client activated. Client ID {client.client_id} issued.", "success")
    return _back(capp)


@bp.get("/agreements")
def agreements():
    rows = db.session.execute(select(Agreement, ClientApplication)
                              .join(ClientApplication, Agreement.client_application_id == ClientApplication.id)
                              .order_by(Agreement.id.desc()).limit(100)).all()
    return render_template("admin/agreements.html", title="Agreements | Admin", rows=rows,
                           labels=AGREEMENT_STATUS_LABELS)
