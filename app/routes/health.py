from flask import Blueprint, jsonify
from sqlalchemy import text

from ..extensions import db

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    """Render health check: answers whenever the web server is running."""
    return jsonify(status="ok")


@bp.get("/health/db")
def health_db():
    """Deeper check that also tests the database connection."""
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify(status="ok", database="connected")
    except Exception:  # never leak connection details
        db.session.rollback()
        return jsonify(status="degraded", database="unavailable"), 503
