from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash

from sqlalchemy import select

from ..extensions import db
from ..models import Notification
from ..security import hash_password, login_required, rate_limit
from ..services.audit import log_action
from ..validators import validate_new_password

bp = Blueprint("account", __name__, url_prefix="/account")


@bp.route("/password", methods=["GET", "POST"])
@login_required()
@rate_limit("change_password", 10, 3600)
def password():
    title = "Account settings | VerifyTalent Global"
    if request.method == "GET":
        return render_template("account/password.html", title=title, errors={}, form={})
    errors = validate_new_password(request.form.get("password") or "", request.form.get("confirm_password") or "", g.user.email)
    if not check_password_hash(g.user.password_hash, request.form.get("current_password") or ""):
        errors["current_password"] = "Your current password is not correct."
    if errors:
        return render_template("account/password.html", title=title, errors=errors, form={}), 400
    g.user.password_hash = hash_password(request.form["password"])
    log_action("auth.password_changed", actor=g.user, target_type="user", target_id=g.user.id)
    db.session.commit()
    flash("Your password has been changed.", "success")
    return redirect(url_for("account.password"))


@bp.get("/notifications")
@login_required()
def notifications():
    items = db.session.scalars(select(Notification).where(Notification.user_id == g.user.id)
                               .order_by(Notification.created_at.desc()).limit(50)).all()
    rows = [(n, not n.is_read) for n in items]  # remember what was new before marking everything as read
    for n in items:
        n.is_read = True
    db.session.commit()
    return render_template("account/notifications.html", title="Notifications | VerifyTalent Global", rows=rows)
