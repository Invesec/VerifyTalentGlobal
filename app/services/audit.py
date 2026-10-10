from flask import request

from ..extensions import db
from ..models import AuditLog, Notification


def log_action(action, actor=None, target_type=None, target_id=None, meta=None):
    """Adds an audit entry to the current transaction. The caller commits."""
    db.session.add(AuditLog(
        actor_id=actor.id if actor else None,
        actor_label=actor.email if actor else None,
        action=action, target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        meta=meta, ip_address=(request.remote_addr or "")[:64] if request else None,
    ))


def notify(user_id, title, body):
    """Adds an in-app notification to the current transaction. The caller commits."""
    db.session.add(Notification(user_id=user_id, title=title[:120], body=body))
