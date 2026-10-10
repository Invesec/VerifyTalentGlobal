"""Password-reset tokens: signed, expire after one hour, and stop working once the password changes."""
from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ..extensions import db
from ..models import User

RESET_MAX_AGE = 3600  # seconds


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="vtg-password-reset")


def make_reset_token(user):
    # The tail of the password hash changes whenever the password changes, so a used link stops working.
    return _serializer().dumps({"uid": user.id, "v": user.password_hash[-12:]})


def read_reset_token(token, max_age=RESET_MAX_AGE):
    try:
        data = _serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    user = db.session.get(User, data.get("uid"))
    if user is None or not user.is_active or user.password_hash[-12:] != data.get("v"):
        return None
    return user
