import click
from sqlalchemy import select, text

from .extensions import db
from .models import User
from .security import hash_password
from .services import demo


def register_cli(app):
    @app.cli.command("create-admin")
    @click.option("--email", default=None, help="Defaults to ADMIN_EMAIL")
    @click.option("--name", default="Administrator")
    def create_admin(email, name):
        """Create the administrator account (password is typed hidden, never stored in .env)."""
        email = (email or app.config["ADMIN_EMAIL"] or click.prompt("Admin email")).strip().lower()
        if db.session.scalar(select(User).filter_by(email=email)):
            click.echo(f"An account for {email} already exists. Nothing changed.")
            return
        password = click.prompt("Password (at least 12 characters)", hide_input=True, confirmation_prompt=True)
        if len(password) < 12:
            raise click.ClickException("Password must be at least 12 characters.")
        db.session.add(User(email=email, full_name=name, role="ADMIN", password_hash=hash_password(password)))
        db.session.commit()
        click.echo(f"Admin created: {email}")

    @app.cli.command("seed-demo")
    def seed_demo_command():
        """Add clearly labelled demo talents for testing."""
        click.echo(f"Added {demo.seed_demo()} demo talents.")

    @app.cli.command("reset-demo")
    def reset_demo_command():
        """Delete all demo data."""
        click.echo(f"Removed {demo.reset_demo()} demo accounts.")


    @app.cli.command("check-config")
    def check_config():
        """Show which settings are in place (never prints secret values)."""
        cfg = app.config
        def line(name, ok, hint=""):
            click.echo(f"{'OK     ' if ok else 'MISSING'}  {name}" + (f"  ({hint})" if hint and not ok else ""))
        line("SESSION_SECRET", cfg["SECRET_KEY_FROM_ENV"], "required in production")
        line("DATABASE_URL", "sqlite" not in cfg["SQLALCHEMY_DATABASE_URI"], "using local SQLite")
        try:
            db.session.execute(text("SELECT 1"))
            line("Database connection", True)
        except Exception:
            line("Database connection", False, "cannot connect")
        line("SMTP_USER and SMTP_PASSWORD (Gmail)", bool(cfg["SMTP_USER"] and cfg["SMTP_PASSWORD"]), "emails will only be logged unless Brevo is set")
        line("BREVO_API_KEY and BREVO_SENDER_EMAIL (optional)", bool(cfg["BREVO_API_KEY"] and cfg["BREVO_SENDER_EMAIL"]), "optional backup provider")
        line("COMPANY_EMAIL", bool(cfg["COMPANY_EMAIL"]), "hidden on the site")
        line("TELEGRAM_USERNAME", bool(cfg["TELEGRAM_USERNAME"]), "hidden on the site")
        from .services import verification
        line("Email verification is ON", verification.required(cfg), "OFF: set SMTP_USER and SMTP_PASSWORD so codes can be emailed")
        line("An admin account exists", db.session.scalar(select(User.id).where(User.role == "ADMIN").limit(1)) is not None,
             "run create-admin, or set ADMIN_EMAIL and ADMIN_INITIAL_PASSWORD")
        if cfg["ADMIN_INITIAL_PASSWORD"]:
            click.echo("WARNING  ADMIN_INITIAL_PASSWORD is still set. Remove it once you can log in.")
