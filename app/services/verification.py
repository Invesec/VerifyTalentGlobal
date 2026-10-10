"""Email verification with a 6-digit code. Codes expire after 15 minutes, allow 5 wrong guesses,
and can be re-sent no more than once a minute. Only a keyed hash of the code is stored."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy import select

from ..extensions import db
from ..models import EmailVerification

CODE_TTL = timedelta(minutes=15)
MAX_ATTEMPTS = 5
RESEND_COOLDOWN = 60  # seconds
VERIFIED_ROLES = ("TALENT", "CLIENT")  # admins are exempt


def required(config):
    """On when emails can really be delivered, or while developing locally (the code is printed in the terminal).
    Off in production without Brevo, so a missing email setup never locks everyone out."""
    return bool(config["BREVO_API_KEY"] and config["BREVO_SENDER_EMAIL"]) or not config["IS_PROD"]


def _aware(value):
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)  # SQLite returns naive times


def _hash(secret, user_id, code):
    return hmac.new(secret.encode(), f"verify:{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


def new_code():
    return f"{secrets.randbelow(10 ** 6):06d}"


def cooldown_remaining(record, now):
    if record is None or record.sent_at is None:
        return 0
    return max(0, int(RESEND_COOLDOWN - (now - _aware(record.sent_at)).total_seconds()))


def evaluate_code(record, code, secret, user_id, now):
    """Pure check: returns 'ok', 'wrong', 'expired', 'locked', or 'none'."""
    if record is None or not record.code_hash or record.verified_at:
        return "none"
    if (record.attempts or 0) >= MAX_ATTEMPTS:
        return "locked"
    if _aware(record.expires_at) < now:
        return "expired"
    if hmac.compare_digest(_hash(secret, user_id, code), record.code_hash):
        return "ok"
    return "wrong"


# ---- database helpers ----
def get_record(user):
    return db.session.scalar(select(EmailVerification).where(EmailVerification.user_id == user.id))


def is_verified(user):
    record = get_record(user)
    return bool(record and record.verified_at)


def issue_code(user, now=None):
    """Creates a fresh code and returns it, or None if one was sent less than a minute ago. Caller commits."""
    now = now or datetime.now(timezone.utc)
    record = get_record(user)
    if record is None:
        record = EmailVerification(user_id=user.id, attempts=0, send_count=0)
        db.session.add(record)
    if record.verified_at or cooldown_remaining(record, now) > 0:
        return None
    code = new_code()
    record.code_hash = _hash(current_app.config["SECRET_KEY"], user.id, code)
    record.expires_at, record.attempts, record.sent_at = now + CODE_TTL, 0, now
    record.send_count = (record.send_count or 0) + 1
    return code


def mark_verified(user, now=None):
    now = now or datetime.now(timezone.utc)
    record = get_record(user)
    if record is None:
        record = EmailVerification(user_id=user.id, attempts=0, send_count=0)
        db.session.add(record)
    record.verified_at, record.code_hash = now, None


def mask_email(email):
    name, _, domain = email.partition("@")
    return (name[:1] + "***" if len(name) > 1 else "*") + "@" + domain
