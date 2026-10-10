"""Database tables. Milestone 2 creates users, talent_applications, and audit_logs.
Payment, Talent ID, and verification columns exist now but are admin-controlled (Milestone 3)."""
from datetime import datetime, timezone

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="TALENT", index=True)  # ADMIN, TALENT, CLIENT, RECRUITER
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime(timezone=True))

    talent_application = db.relationship(
        "TalentApplication", back_populates="user", uselist=False,
        foreign_keys="TalentApplication.user_id",
    )


class TalentApplication(db.Model):
    __tablename__ = "talent_applications"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.String(20), unique=True, index=True)  # VTG-APP-000001, set server-side
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    # Professional profile (entered by the talent)
    category = db.Column(db.String(60), nullable=False, index=True)
    profession = db.Column(db.String(60), nullable=False, index=True)
    country = db.Column(db.String(60), nullable=False)
    phone = db.Column(db.String(30))
    years_experience = db.Column(db.Integer, nullable=False, default=0)
    skills = db.Column(db.Text, nullable=False)
    education = db.Column(db.Text)
    certifications = db.Column(db.Text)
    portfolio_url = db.Column(db.String(300))
    availability = db.Column(db.String(40), nullable=False)
    expected_rate = db.Column(db.String(60))
    languages = db.Column(db.String(200), nullable=False)
    bio = db.Column(db.Text)
    details = db.Column(db.JSON, nullable=False, default=dict)  # category-specific answers

    # Admin-controlled fields (talents can never edit these)
    status = db.Column(db.String(30), nullable=False, default="NEW", index=True)
    verification_status = db.Column(db.String(30), nullable=False, default="UNVERIFIED")
    payment_status = db.Column(db.String(20), nullable=False, default="NOT_REQUIRED", index=True)
    payment_amount = db.Column(db.Numeric(10, 2))
    payment_currency = db.Column(db.String(8))
    payment_reference = db.Column(db.String(120))
    payment_method = db.Column(db.String(40))
    payment_submitted_at = db.Column(db.DateTime(timezone=True))
    payment_verified_at = db.Column(db.DateTime(timezone=True))
    payment_verified_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    talent_id = db.Column(db.String(20), unique=True, index=True)  # VTG-TL-000001, issued after payment verified
    admin_notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    user = db.relationship("User", back_populates="talent_application", foreign_keys=[user_id])


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    actor_label = db.Column(db.String(254))
    action = db.Column(db.String(80), nullable=False, index=True)
    target_type = db.Column(db.String(40))
    target_id = db.Column(db.String(40))
    meta = db.Column(db.JSON)
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class TalentID(db.Model):
    """The internal VerifyTalent Global ID card record. Created only when payment is verified."""
    __tablename__ = "talent_ids"

    id = db.Column(db.Integer, primary_key=True)
    talent_id = db.Column(db.String(20), unique=True, index=True)  # VTG-TL-000001, set server-side
    application_id = db.Column(db.Integer, db.ForeignKey("talent_applications.id"), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="ACTIVE")  # ACTIVE, SUSPENDED, REVOKED
    issued_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = db.Column(db.DateTime(timezone=True))  # empty means no expiry set
    issued_by = db.Column(db.Integer, db.ForeignKey("users.id"))


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class ClientApplication(db.Model):
    """A company's registration. It has no official Client ID until it is approved, agrees, and is activated."""
    __tablename__ = "client_applications"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.String(30), unique=True, index=True)  # VTG-APP-CLIENT-000001, set server-side
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    company_name = db.Column(db.String(120), nullable=False, index=True)
    website = db.Column(db.String(300))
    industry = db.Column(db.String(80), nullable=False)
    country = db.Column(db.String(60), nullable=False)
    company_size = db.Column(db.String(20), nullable=False)
    contact_name = db.Column(db.String(100), nullable=False)
    job_title = db.Column(db.String(100), nullable=False)
    business_email = db.Column(db.String(254), nullable=False)
    phone = db.Column(db.String(30))
    linkedin_url = db.Column(db.String(300))
    description = db.Column(db.Text)
    recruitment_needs = db.Column(db.Text, nullable=False)

    status = db.Column(db.String(30), nullable=False, default="NEW", index=True)  # admin-controlled
    admin_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    user = db.relationship("User", foreign_keys=[user_id])


class Client(db.Model):
    """Created only at activation. Holds the official Client ID and the membership."""
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(20), unique=True, index=True)  # VTG-CL-000001, set server-side
    application_id = db.Column(db.Integer, db.ForeignKey("client_applications.id"), unique=True, nullable=False)
    membership_status = db.Column(db.String(20), nullable=False, default="ACTIVE")  # ACTIVE, SUSPENDED, EXPIRED
    membership_expires_at = db.Column(db.Date)
    activated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    activated_by = db.Column(db.Integer, db.ForeignKey("users.id"))


class Agreement(db.Model):
    __tablename__ = "agreements"

    id = db.Column(db.Integer, primary_key=True)
    agreement_id = db.Column(db.String(20), unique=True, index=True)  # VTG-CON-000001, set server-side
    client_application_id = db.Column(db.Integer, db.ForeignKey("client_applications.id"), nullable=False, index=True)
    agreement_type = db.Column(db.String(60), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="PENDING", index=True)
    sent_at = db.Column(db.DateTime(timezone=True))
    viewed_at = db.Column(db.DateTime(timezone=True))
    accepted_at = db.Column(db.DateTime(timezone=True))
    accepted_by_name = db.Column(db.String(300))
    expires_at = db.Column(db.Date)
    document_reference = db.Column(db.String(300))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(20), unique=True, index=True)  # VTG-JOB-000001, set server-side
    client_application_id = db.Column(db.Integer, db.ForeignKey("client_applications.id"), nullable=False, index=True)

    title = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(60), nullable=False, index=True)
    profession = db.Column(db.String(60), nullable=False, index=True)
    workers_needed = db.Column(db.Integer, nullable=False, default=1)
    required_skills = db.Column(db.Text, nullable=False)
    min_experience_years = db.Column(db.Integer, nullable=False, default=0)
    qualifications = db.Column(db.Text)
    certifications = db.Column(db.Text)
    location = db.Column(db.String(100))
    timezone = db.Column(db.String(60))
    work_mode = db.Column(db.String(20), nullable=False, default="Remote")
    contract_type = db.Column(db.String(40), nullable=False)
    contract_duration = db.Column(db.String(60))
    start_date = db.Column(db.Date)
    budget = db.Column(db.String(40))
    currency = db.Column(db.String(8))
    description = db.Column(db.Text, nullable=False)
    additional_requirements = db.Column(db.Text)

    status = db.Column(db.String(20), nullable=False, default="DRAFT", index=True)  # admin-controlled after submission
    assigned_recruiter = db.Column(db.Integer, db.ForeignKey("users.id"))
    admin_notes = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    client = db.relationship("ClientApplication", foreign_keys=[client_application_id])
    recruiter = db.relationship("User", foreign_keys=[assigned_recruiter])


class Match(db.Model):
    """A suggested pairing of one talent with one job. Clients only see it after an admin presents it."""
    __tablename__ = "matches"
    __table_args__ = (db.UniqueConstraint("job_id", "talent_application_id", name="uq_match_job_talent"),)

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False, index=True)
    talent_application_id = db.Column(db.Integer, db.ForeignKey("talent_applications.id"), nullable=False, index=True)
    score = db.Column(db.Integer, nullable=False, default=0)
    breakdown = db.Column(db.JSON)
    status = db.Column(db.String(20), nullable=False, default="SUGGESTED", index=True)
    talent_response = db.Column(db.String(20), nullable=False, default="PENDING")  # PENDING, INTERESTED, DECLINED
    client_decision = db.Column(db.String(24))  # INTERVIEW_REQUESTED
    interview_at = db.Column(db.DateTime(timezone=True))
    interview_details = db.Column(db.Text)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    job = db.relationship("Job", foreign_keys=[job_id])
    talent = db.relationship("TalentApplication", foreign_keys=[talent_application_id])


class EmailVerification(db.Model):
    """One row per user. A row with verified_at set means the email address was confirmed with a code."""
    __tablename__ = "email_verifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    code_hash = db.Column(db.String(64))  # a keyed hash, never the code itself
    expires_at = db.Column(db.DateTime(timezone=True))
    attempts = db.Column(db.Integer, nullable=False, default=0)
    send_count = db.Column(db.Integer, nullable=False, default=0)
    sent_at = db.Column(db.DateTime(timezone=True))
    verified_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
