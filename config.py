"""Central configuration. Every secret comes from environment variables."""
import os
import secrets

from dotenv import load_dotenv

load_dotenv()


def _clean(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _database_url() -> str:
    url = _clean("DATABASE_URL")
    if not url:
        return "sqlite:///verifytalent.db"  # stored in the instance/ folder
    # Render gives postgres://, SQLAlchemy needs postgresql://
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


class Config:
    IS_PROD = _clean("RENDER") != "" or _clean("APP_ENV") == "production"
    SECRET_KEY = _clean("SESSION_SECRET") or secrets.token_hex(32)
    SECRET_KEY_FROM_ENV = bool(_clean("SESSION_SECRET"))
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 240}  # survives databases that sleep (Neon)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = IS_PROD
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB upload cap (used from Milestone 2)

    # Email: Gmail (or any SMTP) is tried first, Brevo second. Either one is enough.
    SMTP_HOST = _clean("SMTP_HOST") or "smtp.gmail.com"
    SMTP_PORT = int(_clean("SMTP_PORT") or 587)
    SMTP_USER = _clean("SMTP_USER")
    SMTP_PASSWORD = _clean("SMTP_PASSWORD").replace(" ", "")  # Google shows app passwords in groups of 4
    BREVO_API_KEY = _clean("BREVO_API_KEY")
    BREVO_SENDER_EMAIL = _clean("BREVO_SENDER_EMAIL")
    ADMIN_EMAIL = _clean("ADMIN_EMAIL")
    ADMIN_INITIAL_PASSWORD = _clean("ADMIN_INITIAL_PASSWORD")
    COMPANY_EMAIL = _clean("COMPANY_EMAIL")
    TELEGRAM_USERNAME = _clean("TELEGRAM_USERNAME").lstrip("@")

    BRAND_NAME = "VerifyTalent Global"
    BRAND_TAGLINE = "Find. Verify. Match."
