import re
from urllib.parse import urlparse

from .talent_data import AVAILABILITY, FIELD_GROUPS, PROFESSION_TO_CATEGORY, PROFESSION_TO_GROUP

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+()\-\s]{6,30}$")


def _s(form, name):
    return (form.get(name) or "").strip()


def _length(errors, name, value, label, minimum=0, maximum=200):
    if len(value) < minimum:
        errors[name] = f"{label} is required." if minimum == 1 else f"{label} must be at least {minimum} characters."
    elif len(value) > maximum:
        errors[name] = f"{label} must be {maximum} characters or fewer."


def validate_profile(form):
    """Professional profile fields, shared by registration and profile editing."""
    errors, clean = {}, {}

    clean["profession"] = _s(form, "profession")
    if clean["profession"] not in PROFESSION_TO_CATEGORY:
        errors["profession"] = "Choose your primary profession."
    clean["category"] = PROFESSION_TO_CATEGORY.get(clean["profession"], "")

    clean["country"] = _s(form, "country")
    _length(errors, "country", clean["country"], "Country", 1, 60)

    clean["phone"] = _s(form, "phone")
    if clean["phone"] and not PHONE_RE.match(clean["phone"]):
        errors["phone"] = "Use digits, spaces, and + ( ) - only."

    years = _s(form, "years_experience")
    if not years.isdigit() or not 0 <= int(years) <= 60:
        errors["years_experience"] = "Enter whole years between 0 and 60."
    clean["years_experience"] = int(years) if years.isdigit() and int(years) <= 60 else 0

    clean["skills"] = _s(form, "skills")
    _length(errors, "skills", clean["skills"], "Skills", 3, 1000)
    for name, label, maximum in [("education", "Education", 1000), ("certifications", "Certifications", 1000),
                                 ("expected_rate", "Expected rate", 60), ("bio", "Short bio", 1500)]:
        clean[name] = _s(form, name)
        _length(errors, name, clean[name], label, 0, maximum)
    clean["languages"] = _s(form, "languages")
    _length(errors, "languages", clean["languages"], "Languages", 1, 200)

    clean["portfolio_url"] = _s(form, "portfolio_url")
    if clean["portfolio_url"]:
        parsed = urlparse(clean["portfolio_url"])
        if parsed.scheme not in ("http", "https") or not parsed.netloc or len(clean["portfolio_url"]) > 300:
            errors["portfolio_url"] = "Enter a full link starting with http:// or https://."

    clean["availability"] = _s(form, "availability")
    if clean["availability"] not in AVAILABILITY:
        errors["availability"] = "Choose your availability."

    # Category-specific answers: only the selected profession's group is accepted.
    details = {}
    group = PROFESSION_TO_GROUP.get(clean["profession"])
    if group:
        for field, label in FIELD_GROUPS[group][2]:
            value = _s(form, f"{group}__{field}")
            if len(value) > 800:
                errors[f"{group}__{field}"] = f"{label} must be 800 characters or fewer."
            elif value:
                details[field] = value
    clean["details"] = details
    return clean, errors


def validate_registration(form):
    """Returns (clean, errors). Nothing here trusts the browser: IDs, status, and payment fields are never read."""
    errors, clean = {}, {}

    clean["full_name"] = _s(form, "full_name")
    _length(errors, "full_name", clean["full_name"], "Full name", 2, 100)

    clean["email"] = _s(form, "email").lower()
    if not EMAIL_RE.match(clean["email"]) or len(clean["email"]) > 254:
        errors["email"] = "Enter a valid email address."

    password, confirm = form.get("password") or "", form.get("confirm_password") or ""
    if len(password) < 10:
        errors["password"] = "Use at least 10 characters."
    elif len(password) > 128:
        errors["password"] = "Use 128 characters or fewer."
    elif password.lower() == clean["email"]:
        errors["password"] = "Your password cannot be your email address."
    if password != confirm:
        errors["confirm_password"] = "The two passwords do not match."
    clean["password"] = password

    profile_clean, profile_errors = validate_profile(form)
    clean.update(profile_clean)
    errors.update(profile_errors)

    if form.get("accept") != "yes":
        errors["accept"] = "Please confirm that you understand this before applying."
    return clean, errors


# ---- Companies (Milestone 4) ----
from datetime import date, datetime  # noqa: E402

from .client_data import AGREEMENT_TYPES, COMPANY_SIZES  # noqa: E402


def _url(errors, name, value, label):
    if value:
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or len(value) > 300:
            errors[name] = f"{label} must be a full link starting with http:// or https://."


def validate_client_registration(form):
    errors, clean = {}, {}
    clean["company_name"] = _s(form, "company_name")
    _length(errors, "company_name", clean["company_name"], "Company name", 2, 120)
    clean["website"] = _s(form, "website")
    _url(errors, "website", clean["website"], "Website")
    clean["industry"] = _s(form, "industry")
    _length(errors, "industry", clean["industry"], "Industry", 1, 80)
    clean["country"] = _s(form, "country")
    _length(errors, "country", clean["country"], "Country", 1, 60)
    clean["company_size"] = _s(form, "company_size")
    if clean["company_size"] not in COMPANY_SIZES:
        errors["company_size"] = "Choose your company size."
    clean["contact_name"] = _s(form, "contact_name")
    _length(errors, "contact_name", clean["contact_name"], "Contact person", 2, 100)
    clean["job_title"] = _s(form, "job_title")
    _length(errors, "job_title", clean["job_title"], "Job title", 1, 100)

    clean["business_email"] = _s(form, "business_email").lower()
    if not EMAIL_RE.match(clean["business_email"]) or len(clean["business_email"]) > 254:
        errors["business_email"] = "Enter a valid business email address."
    clean["phone"] = _s(form, "phone")
    if clean["phone"] and not PHONE_RE.match(clean["phone"]):
        errors["phone"] = "Use digits, spaces, and + ( ) - only."
    clean["linkedin_url"] = _s(form, "linkedin_url")
    _url(errors, "linkedin_url", clean["linkedin_url"], "LinkedIn link")
    clean["description"] = _s(form, "description")
    _length(errors, "description", clean["description"], "Company description", 0, 1500)
    clean["recruitment_needs"] = _s(form, "recruitment_needs")
    _length(errors, "recruitment_needs", clean["recruitment_needs"], "Recruitment needs", 10, 1500)

    password, confirm = form.get("password") or "", form.get("confirm_password") or ""
    if len(password) < 10:
        errors["password"] = "Use at least 10 characters."
    elif len(password) > 128:
        errors["password"] = "Use 128 characters or fewer."
    elif password.lower() == clean["business_email"]:
        errors["password"] = "Your password cannot be your email address."
    if password != confirm:
        errors["confirm_password"] = "The two passwords do not match."
    clean["password"] = password
    if form.get("accept") != "yes":
        errors["accept"] = "Please confirm this before registering."
    return clean, errors


def validate_agreement(form, require_document):
    errors, clean = {}, {}
    clean["agreement_type"] = _s(form, "agreement_type")
    if clean["agreement_type"] not in AGREEMENT_TYPES:
        errors["agreement_type"] = "Choose an agreement type."
    clean["document_reference"] = _s(form, "document_reference")
    if len(clean["document_reference"]) > 300:
        errors["document_reference"] = "Use 300 characters or fewer."
    elif clean["document_reference"].lower().startswith(("http://", "https://")):
        _url(errors, "document_reference", clean["document_reference"], "Document link")
    if require_document and not clean["document_reference"]:
        errors["document_reference"] = "Add the agreement document link or reference before sending."
    clean["expires_at"] = None
    raw = _s(form, "expires_at")
    if raw:
        try:
            clean["expires_at"] = datetime.strptime(raw, "%Y-%m-%d").date()
            if clean["expires_at"] < date.today():
                errors["expires_at"] = "The expiry date cannot be in the past."
        except ValueError:
            errors["expires_at"] = "Use the date format YYYY-MM-DD."
    clean["notes"] = _s(form, "notes")
    _length(errors, "notes", clean["notes"], "Notes", 0, 1000)
    return clean, errors


# ---- Job requests (Milestone 5) ----
from .job_data import CONTRACT_TYPES, CURRENCIES, WORK_MODES  # noqa: E402


def validate_job(form):
    errors, clean = {}, {}
    clean["title"] = _s(form, "title")
    _length(errors, "title", clean["title"], "Job title", 3, 120)
    clean["profession"] = _s(form, "profession")
    if clean["profession"] not in PROFESSION_TO_CATEGORY:
        errors["profession"] = "Choose the profession you need."
    clean["category"] = PROFESSION_TO_CATEGORY.get(clean["profession"], "")

    workers = _s(form, "workers_needed")
    if not workers.isdigit() or not 1 <= int(workers) <= 500:
        errors["workers_needed"] = "Enter a whole number between 1 and 500."
    clean["workers_needed"] = int(workers) if workers.isdigit() and 1 <= int(workers) <= 500 else 1
    years = _s(form, "min_experience_years")
    if not years.isdigit() or not 0 <= int(years) <= 60:
        errors["min_experience_years"] = "Enter whole years between 0 and 60."
    clean["min_experience_years"] = int(years) if years.isdigit() and int(years) <= 60 else 0

    clean["required_skills"] = _s(form, "required_skills")
    _length(errors, "required_skills", clean["required_skills"], "Required skills", 3, 1000)
    for name, label, maximum in [("qualifications", "Qualifications", 1000), ("certifications", "Certifications", 1000),
                                 ("location", "Location", 100), ("timezone", "Timezone", 60),
                                 ("contract_duration", "Contract duration", 60), ("budget", "Budget", 40),
                                 ("additional_requirements", "Additional requirements", 1500)]:
        clean[name] = _s(form, name)
        _length(errors, name, clean[name], label, 0, maximum)
    clean["description"] = _s(form, "description")
    _length(errors, "description", clean["description"], "Job description", 20, 3000)

    clean["work_mode"] = _s(form, "work_mode")
    if clean["work_mode"] not in WORK_MODES:
        errors["work_mode"] = "Choose remote, hybrid, or onsite."
    clean["contract_type"] = _s(form, "contract_type")
    if clean["contract_type"] not in CONTRACT_TYPES:
        errors["contract_type"] = "Choose a contract type."
    clean["currency"] = _s(form, "currency")
    if clean["currency"] and clean["currency"] not in CURRENCIES:
        errors["currency"] = "Choose a currency."
    clean["start_date"] = None
    raw = _s(form, "start_date")
    if raw:
        try:
            clean["start_date"] = datetime.strptime(raw, "%Y-%m-%d").date()
            if clean["start_date"] < date.today():
                errors["start_date"] = "The start date cannot be in the past."
        except ValueError:
            errors["start_date"] = "Use the date format YYYY-MM-DD."
    return clean, errors


def parse_interview_time(raw):
    """Accepts 2026-10-20T14:30 (from the browser) or '2026-10-20 14:30'. Times are treated as UTC."""
    from datetime import timezone
    raw = (raw or "").strip().replace(" ", "T")
    try:
        value = datetime.strptime(raw, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return value if value > datetime.now(timezone.utc) else None


def validate_new_password(password, confirm, email=""):
    errors = {}
    if len(password) < 10:
        errors["password"] = "Use at least 10 characters."
    elif len(password) > 128:
        errors["password"] = "Use 128 characters or fewer."
    elif email and password.lower() == email.lower():
        errors["password"] = "Your password cannot be your email address."
    if password != confirm:
        errors["confirm_password"] = "The two passwords do not match."
    return errors
