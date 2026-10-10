import logging

from sqlalchemy import select

from ..extensions import db
from ..models import User
from ..security import hash_password

log = logging.getLogger("bootstrap")


def bootstrap_admin(app):
    """Creates the first admin from ADMIN_EMAIL + ADMIN_INITIAL_PASSWORD when no admin exists yet.
    Useful on Render, where you may not have a shell. Remove the password variable afterwards."""
    email = app.config["ADMIN_EMAIL"].lower()
    password = app.config["ADMIN_INITIAL_PASSWORD"]
    if not email or not password:
        return
    if len(password) < 12:
        log.warning("ADMIN_INITIAL_PASSWORD is shorter than 12 characters, so no admin was created.")
        return
    try:
        if db.session.scalar(select(User.id).where(User.role == "ADMIN").limit(1)) is not None:
            return
        if db.session.scalar(select(User).filter_by(email=email)) is not None:
            log.warning("ADMIN_EMAIL already belongs to a non-admin account, so no admin was created.")
            return
        db.session.add(User(email=email, full_name="Administrator", role="ADMIN", password_hash=hash_password(password)))
        db.session.commit()
        log.warning("Admin account created for %s. Remove ADMIN_INITIAL_PASSWORD from your environment now.", email)
    except Exception as err:
        db.session.rollback()
        log.error("Admin bootstrap failed: %s", type(err).__name__)
