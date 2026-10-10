import logging
from datetime import datetime, timezone

from datetime import timedelta

from flask import Flask, g, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from .extensions import db


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # Render proxy

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
    if Config.IS_PROD and not Config.SECRET_KEY_FROM_ENV:
        raise RuntimeError("SESSION_SECRET must be set in production. Add it in your Render environment variables.")

    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
    db.init_app(app)
    from . import models  # noqa: F401  (registers tables)
    from .security import init_security
    init_security(app)

    from .cli import register_cli
    from .routes.account import bp as account_bp
    from .routes.admin import bp as admin_bp
    from .routes.admin_clients import bp as admin_clients_bp
    from .routes.admin_jobs import bp as admin_jobs_bp
    from .routes.auth import bp as auth_bp
    from .routes.client import bp as client_bp
    from .routes.health import bp as health_bp
    from .routes.main import bp as main_bp
    from .routes.talent import bp as talent_bp
    from .routes.verify import bp as verify_bp

    for blueprint in (health_bp, main_bp, auth_bp, talent_bp, client_bp, admin_bp, admin_clients_bp, admin_jobs_bp, verify_bp, account_bp):
        app.register_blueprint(blueprint)

    register_cli(app)

    @app.template_filter("dt")
    def format_date(value, with_time=False):
        if not value:
            return ""
        return value.strftime("%d %b %Y %H:%M UTC" if with_time else "%d %b %Y")

    with app.app_context():
        try:
            db.create_all()  # creates missing tables; safe to run on every start
        except Exception as err:  # the site must still start if the database is down
            app.logger.error("Database setup failed: %s", type(err).__name__)
        else:
            from .services.bootstrap import bootstrap_admin
            bootstrap_admin(app)

    @app.context_processor
    def inject_globals():
        return {
            "brand_name": app.config["BRAND_NAME"],
            "brand_tagline": app.config["BRAND_TAGLINE"],
            "company_email": app.config["COMPANY_EMAIL"],
            "telegram_username": app.config["TELEGRAM_USERNAME"],
            "year": datetime.now(timezone.utc).year,
        }

    @app.after_request
    def security_headers(resp):
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; script-src 'self'; "
            "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if g.get("user") is not None:
            resp.headers["Cache-Control"] = "no-store"  # signed-in pages are never kept in a browser cache
        if Config.IS_PROD:
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return resp

    def _error(code, title, message):
        return render_template("error.html", title=title, code=code, message=message), code

    @app.errorhandler(400)
    def bad_request(_e):
        return _error(400, "Request could not be completed",
                      "Your session may have expired. Go back, refresh the page, and try again.")

    @app.errorhandler(403)
    def forbidden(_e):
        return _error(403, "Access denied", "You do not have permission to view this page.")

    @app.errorhandler(429)
    def too_many(_e):
        return _error(429, "Too many attempts", "Please wait a few minutes before trying again.")

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", title="Page not found", code=404,
                               message="We could not find that page."), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.error("Server error: %s", e, exc_info=True)  # stack trace goes to logs only
        return render_template("error.html", title="Something went wrong", code=500,
                               message="Something went wrong on our side. Please try again shortly."), 500

    return app
