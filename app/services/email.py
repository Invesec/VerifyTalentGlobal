"""Centralized email service using the Brevo API. Never crashes the app:
if Brevo is not configured or fails, the event is logged instead."""
import json
import logging
import threading
import urllib.error
import urllib.request

from flask import current_app

from . import email_templates

log = logging.getLogger("email")
BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def _post(api_key, payload, event, to_email):
    request = urllib.request.Request(
        BREVO_URL, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"api-key": api_key, "content-type": "application/json", "accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            log.info("Email sent: event=%s to=%s status=%s", event, to_email, response.status)
    except urllib.error.HTTPError as err:
        log.error("Brevo rejected email: event=%s to=%s status=%s", event, to_email, err.code)
    except Exception as err:  # network down, timeout, and so on
        log.error("Email failed: event=%s to=%s error=%s", event, to_email, type(err).__name__)


DEMO_DOMAIN = "@demo.verifytalent.invalid"


def send_email(event, to_email, to_name, subject, html, text):
    cfg = current_app.config
    if to_email.endswith(DEMO_DOMAIN):
        log.info("Email skipped for demo account: event=%s", event)
        return False
    api_key, sender = cfg["BREVO_API_KEY"], cfg["BREVO_SENDER_EMAIL"]
    if not api_key or not sender:
        log.warning("Email NOT sent (Brevo not configured): event=%s to=%s subject=%s", event, to_email, subject)
        return False
    payload = {
        "sender": {"name": cfg["BRAND_NAME"], "email": sender},
        "to": [{"email": to_email, "name": to_name}],
        "subject": subject, "htmlContent": html, "textContent": text,
    }
    threading.Thread(target=_post, args=(api_key, payload, event, to_email), daemon=True).start()
    return True


def send_application_received(user, application):
    subject, html, text = email_templates.application_received(user.full_name, application.application_id)
    return send_email("application_received", user.email, user.full_name, subject, html, text)


def _send(event, user, built):
    subject, html, text = built
    return send_email(event, user.email, user.full_name, subject, html, text)


def contact_lines():
    cfg = current_app.config
    lines = []
    if cfg["COMPANY_EMAIL"]:
        lines.append(f"Official email: {cfg['COMPANY_EMAIL']}")
    if cfg["TELEGRAM_USERNAME"]:
        lines.append(f"Official Telegram: @{cfg['TELEGRAM_USERNAME']}")
    return lines


def send_status_email(event, user, message=""):
    builders = {"SCREENING": email_templates.under_review, "ASSESSMENT": email_templates.assessment_required,
                "REJECTED": email_templates.application_rejected}
    builder = builders.get(event)
    return _send(event.lower(), user, builder(user.full_name, message)) if builder else False


def send_approved(user, application, message=""):
    return _send("application_approved", user, email_templates.application_approved(
        user.full_name, application.application_id, message))


def send_onboarding(user, application):
    return _send("onboarding_instructions", user, email_templates.onboarding_instructions(
        user.full_name, application.application_id, contact_lines()))


def send_payment_confirmed(user, application):
    return _send("payment_confirmed", user, email_templates.payment_confirmed(
        user.full_name, f"{application.payment_amount:.2f}", application.payment_currency, application.payment_reference))


def send_id_ready(user, application):
    return _send("id_card_ready", user, email_templates.id_card_ready(user.full_name, application.talent_id))


def send_client_received(user, capp):
    return _send("client_received", user, email_templates.client_received(capp.contact_name, capp.company_name, capp.application_id))


def send_client_approved(user, capp, message=""):
    return _send("client_approved", user, email_templates.client_approved(capp.contact_name, capp.company_name, message))


def send_agreement_sent(user, capp, agreement):
    expires = agreement.expires_at.strftime("%d %b %Y") if agreement.expires_at else ""
    return _send("agreement_sent", user, email_templates.agreement_sent(
        capp.contact_name, capp.company_name, agreement.agreement_id, expires))


def send_client_activated(user, capp, client, agreement):
    return _send("client_activated", user, email_templates.client_activated(
        capp.contact_name, capp.company_name, client.client_id, agreement.agreement_id))


def send_job_opportunity(user, job):
    return _send("job_opportunity", user, email_templates.job_opportunity(
        user.full_name, job.title, job.profession, job.work_mode, job.contract_type))


def send_interview_invitation(user, job, match):
    when = match.interview_at.strftime("%d %b %Y at %H:%M UTC")
    return _send("interview_invitation", user, email_templates.interview_invitation(
        user.full_name, job.title, when, match.interview_details or "Details will follow."))


def send_placement(user, job, company):
    return _send("placement_notification", user, email_templates.placement_notification(user.full_name, job.title, company))


def send_password_reset(user, link):
    return _send("password_reset", user, email_templates.password_reset(user.full_name, link))


def send_verification_code(user, code):
    sent = _send("verification_code", user, email_templates.verification_code(user.full_name, code))
    if not sent and not current_app.config["IS_PROD"]:
        log.info("DEV ONLY verification code for %s: %s", user.email, code)  # never logged in production
    return sent
