"""Clearly labelled demo data. Demo accounts use the reserved .invalid domain and cannot log in or receive email."""
import secrets

from sqlalchemy import delete, select

from ..extensions import db
from ..models import (Agreement, AuditLog, Client, ClientApplication, Job, Match, Notification, TalentApplication,
                      TalentID, User)
from ..security import hash_password
from ..talent_data import PROFESSION_TO_CATEGORY
from .email import DEMO_DOMAIN

DEMO_PEOPLE = [
    ("Amara", "Software Developer", "NEW"), ("Tunde", "Logo Designer", "SCREENING"),
    ("Ngozi", "Translator", "APPROVED"), ("Ibrahim", "Copywriter", "PAYMENT_PENDING"),
    ("Chidi", "Cybersecurity Specialist", "ASSESSMENT"), ("Efe", "Bookkeeper", "NEW"),
    ("Kemi", "Software Developer", "VERIFIED_TALENT"),
]


DEMO_COMPANIES = [("Northwind Demo Ltd", "NEW"), ("Contoso Demo Inc", "APPROVED"), ("Fabrikam Demo LLC", "ACTIVE")]


def seed_demo():
    created = 0
    for n, (company, status) in enumerate(DEMO_COMPANIES, start=1):
        email = f"democlient{n}{DEMO_DOMAIN}"
        if db.session.scalar(select(User).filter_by(email=email)):
            continue
        user = User(email=email, full_name=f"[DEMO] Contact {n}", role="CLIENT",
                    password_hash=hash_password(secrets.token_hex(24)))
        capp = ClientApplication(user=user, company_name=f"[DEMO] {company}", industry="Software", country="Nigeria",
                                 company_size="11-50", contact_name=f"[DEMO] Contact {n}", job_title="Founder",
                                 business_email=email, recruitment_needs="Demo recruitment needs for testing.", status=status)
        db.session.add(capp)
        db.session.flush()
        capp.application_id = f"VTG-APP-CLIENT-{capp.id:06d}"
        if status == "ACTIVE":
            client = Client(application_id=capp.id, membership_status="ACTIVE")
            db.session.add(client)
            db.session.flush()
            client.client_id = f"VTG-CL-{client.id:06d}"
            job = Job(client_application_id=capp.id, title="[DEMO] Backend developer", category="Technology & IT",
                      profession="Software Developer", workers_needed=1, required_skills="Python, Flask, PostgreSQL",
                      min_experience_years=2, work_mode="Remote", contract_type="Full-time", contract_duration="6 months",
                      description="Demo job request used to test matching. Not a real vacancy.", status="SUBMITTED")
            db.session.add(job)
            db.session.flush()
            job.job_id = f"VTG-JOB-{job.id:06d}"
        created += 1
    for n, (first, profession, status) in enumerate(DEMO_PEOPLE, start=1):
        email = f"demo{n}{DEMO_DOMAIN}"
        if db.session.scalar(select(User).filter_by(email=email)):
            continue
        user = User(email=email, full_name=f"[DEMO] {first}", role="TALENT",
                    password_hash=hash_password(secrets.token_hex(24)))  # nobody knows this password
        app_row = TalentApplication(
            user=user, category=PROFESSION_TO_CATEGORY[profession], profession=profession, country="Nigeria",
            years_experience=n + 1, skills="Demo skills for testing", availability="Full-time",
            languages="English", details={}, status=status, verification_status="UNVERIFIED",
            payment_status="PENDING" if status in ("APPROVED", "PAYMENT_PENDING") else "NOT_REQUIRED",
        )
        db.session.add(app_row)
        db.session.flush()
        app_row.application_id = f"VTG-APP-{app_row.id:06d}"
        if status == "VERIFIED_TALENT":
            app_row.skills, app_row.verification_status, app_row.payment_status = "Python, Flask, PostgreSQL, Docker", "VERIFIED", "VERIFIED"
            card = TalentID(application_id=app_row.id, status="ACTIVE")
            db.session.add(card)
            db.session.flush()
            card.talent_id = f"VTG-TL-{card.id:06d}"
            app_row.talent_id = card.talent_id
        created += 1
    db.session.commit()
    return created


def reset_demo():
    ids = list(db.session.scalars(select(User.id).where(User.email.like(f"%{DEMO_DOMAIN}"))))
    if not ids:
        return 0
    app_ids = select(TalentApplication.id).where(TalentApplication.user_id.in_(ids))
    capp_ids = select(ClientApplication.id).where(ClientApplication.user_id.in_(ids))
    job_ids = select(Job.id).where(Job.client_application_id.in_(capp_ids))
    db.session.execute(delete(Match).where(Match.job_id.in_(job_ids)))
    db.session.execute(delete(Match).where(Match.talent_application_id.in_(app_ids)))
    db.session.execute(delete(Job).where(Job.client_application_id.in_(capp_ids)))
    db.session.execute(delete(Agreement).where(Agreement.client_application_id.in_(capp_ids)))
    db.session.execute(delete(Client).where(Client.application_id.in_(capp_ids)))
    db.session.execute(delete(ClientApplication).where(ClientApplication.user_id.in_(ids)))
    db.session.execute(delete(Notification).where(Notification.user_id.in_(ids)))
    db.session.execute(delete(AuditLog).where(AuditLog.actor_id.in_(ids)))
    db.session.execute(delete(TalentID).where(TalentID.application_id.in_(app_ids)))
    db.session.execute(delete(TalentApplication).where(TalentApplication.user_id.in_(ids)))
    db.session.execute(delete(User).where(User.id.in_(ids)))
    db.session.commit()
    return len(ids)
