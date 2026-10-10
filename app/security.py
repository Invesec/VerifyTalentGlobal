import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from functools import wraps
from urllib.parse import urlparse

from werkzeug.security import generate_password_hash
from flask import abort, flash, g, redirect, request, session, url_for

from sqlalchemy import func, select

from .extensions import db
from .services import verification
from .models import Notification, User

_hits = defaultdict(deque)  # in-memory; fine for one worker. Move to Redis when you scale out.


def hash_password(password):
    """scrypt when this Python supports it (Termux and Render do), otherwise PBKDF2. Never stores plaintext."""
    method = "scrypt" if hasattr(hashlib, "scrypt") else "pbkdf2:sha256"
    return generate_password_hash(password, method=method)


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def safe_next(target, default="main.home"):
    """Only allow redirects to paths on this site."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        if not urlparse(target).netloc:
            return target
    return url_for(default)


def rate_limit(name, limit, window_seconds, methods=("POST",)):
    """Limits requests per IP (POST by default). Returns 429 when exceeded."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if request.method in methods:
                now = time.monotonic()
                hits = _hits[(name, request.remote_addr)]
                while hits and now - hits[0] > window_seconds:
                    hits.popleft()
                if len(hits) >= limit:
                    abort(429)
                hits.append(now)
            return view(*args, **kwargs)
        return wrapper
    return decorator


def login_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if g.get("user") is None:
                flash("Please log in to continue.", "info")
                return redirect(url_for("auth.login", next=request.path))
            if roles and g.user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapper
    return decorator


def init_security(app):
    @app.before_request
    def load_user_and_check_csrf():
        g.user = None
        if request.endpoint == "static":
            return
        if "user_id" in session:
            user = db.session.get(User, session["user_id"])
            if user and user.is_active:
                g.user = user
            else:
                session.clear()
        # Talents and companies must confirm their email before using their private pages.
        if (g.user is not None and g.user.role in verification.VERIFIED_ROLES
                and request.blueprint in ("talent", "client", "account") and verification.required(app.config)
                and not session.get("ev")):
            if verification.is_verified(g.user):
                session["ev"] = True
            else:
                return redirect(url_for("auth.verify_email"))
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            sent = request.form.get("_csrf") or request.headers.get("X-CSRF-Token") or ""
            expected = session.get("_csrf") or ""
            if not expected or not hmac.compare_digest(sent.encode(), expected.encode()):
                abort(400)

    @app.context_processor
    def security_context():
        unread = 0
        user = g.get("user")
        if user is not None:
            try:
                unread = db.session.scalar(select(func.count()).select_from(Notification)
                                           .where(Notification.user_id == user.id, Notification.is_read.is_(False))) or 0
            except Exception:  # a badge must never break a page
                db.session.rollback()
        return {"csrf_token": csrf_token, "current_user": user, "unread_count": unread}
