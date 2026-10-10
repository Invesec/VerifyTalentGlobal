"""Centralized email service. Tries Gmail/SMTP first, then Brevo, Mailjet and Resend (HTTPS, work on Render free). Never crashes the app:
if nothing is configured or every provider fails, the event is logged instead."""
import base64
import json
import logging
import smtplib
import threading
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.utils import formataddr

from flask import current_app

from . import email_templates

log = logging.getLogger("email")
BREVO_URL = "https://api.brevo.com/v3/smtp/email"
MAILJET_URL = "https://api.mailjet.com/v3.1/send"
RESEND_URL = "https://api.resend.com/emails"
DEMO_DOMAIN = "@demo.verifytalent.invalid"


def _clean_header(value):
    """Removes line breaks so a crafted name or subject can never inject extra email headers."""
    return " ".join(str(value).replace("\r", " ").replace("\n", " ").split())


def _smtp_send(settings, brand, to_email, to_name, subject, html, text, event):
    """Sends one message through SMTP (Gmail by default). Returns True on success."""
    message = EmailMessage()
    message["From"] = formataddr((_clean_header(brand), settings["user"]))
    message["To"] = formataddr((_clean_header(to_name), _clean_header(to_email)))
    message["Subject"] = _clean_header(subject)
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    try:
        if settings["port"] == 465:
            server = smtplib.SMTP_SSL(settings["host"], settings["port"], timeout=15)
        else:
            server = smtplib.SMTP(settings["host"], settings["port"], timeout=15)
        with server:
            if settings["port"] != 465:
                server.starttls()
            server.login(settings["user"], settings["password"])
            server.send_message(message)
        log.info("Email sent (SMTP): event=%s to=%s", event, to_email)
        return True
    except smtplib.SMTPAuthenticationError:
        log.error("SMTP login was refused: check SMTP_USER and the app password. event=%s", event)
    except Exception as err:  # network down, timeout, and so on
        log.error("SMTP send failed: event=%s to=%s error=%s", event, to_email, type(err).__name__)
    return False


def _post(api_key, payload, event, to_email):
    """Sends one message through the Brevo API. Returns True on success."""
    request = urllib.request.Request(
        BREVO_URL, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"api-key": api_key, "content-type": "application/json", "accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            log.info("Email sent (Brevo): event=%s to=%s status=%s", event, to_email, response.status)
            return True
    except urllib.error.HTTPError as err:
        log.error("Brevo rejected email: event=%s to=%s status=%s", event, to_email, err.code)
    except Exception as err:
        log.error("Brevo send failed: event=%s to=%s error=%s", event, to_email, type(err).__name__)
    return False


def _https_send(name, url, headers, payload, event, to_email):
    """Sends one message through an HTTPS email API (Mailjet, Resend). Returns True on success."""
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"content-type": "application/json", "accept": "application/json",
                 "user-agent": "VerifyTalentGlobal/1.0", **headers},  # some APIs block the default Python user agent
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            log.info("Email sent (%s): event=%s to=%s status=%s", name, event, to_email, response.status)
            return True
    except urllib.error.HTTPError as err:
        log.error("%s rejected email: event=%s to=%s status=%s", name, event, to_email, err.code)
    except Exception as err:
        log.error("%s send failed: event=%s to=%s error=%s", name, event, to_email, type(err).__name__)
    return False


def _deliver(attempts, event, to_email):
    """Runs the configured providers in order and stops at the first one that works."""
    for attempt in attempts:
        if attempt():
            return True
    log.error("Email NOT delivered by any provider: event=%s to=%s", event, to_email)
    return False


def send_email(event, to_email, to_name, subject, html, text):
    cfg = current_app.config
    if to_email.endswith(DEMO_DOMAIN):
        log.info("Email skipped for demo account: event=%s", event)
        return False
    attempts = []
    if cfg.get("SMTP_USER") and cfg.get("SMTP_PASSWORD"):
        settings = {"host": cfg["SMTP_HOST"], "port": cfg["SMTP_PORT"], "user": cfg["SMTP_USER"], "password": cfg["SMTP_PASSWORD"]}
        attempts.append(lambda: _smtp_send(settings, cfg["BRAND_NAME"], to_email, to_name, subject, html, text, event))
    if cfg.get("BREVO_API_KEY") and cfg.get("BREVO_SENDER_EMAIL"):
        payload = {
            "sender": {"name": cfg["BRAND_NAME"], "email": cfg["BREVO_SENDER_EMAIL"]},
            "to": [{"email": to_email, "name": _clean_header(to_name)}],
            "subject": subject, "htmlContent": html, "textContent": text,
        }
        api_key = cfg["BREVO_API_KEY"]
        attempts.append(lambda: _post(api_key, payload, event, to_email))
    if cfg.get("MAILJET_API_KEY") and cfg.get("MAILJET_SECRET_KEY") and cfg.get("MAILJET_SENDER_EMAIL"):
        token = base64.b64encode(f"{cfg['MAILJET_API_KEY']}:{cfg['MAILJET_SECRET_KEY']}".encode()).decode()
        mj_payload = {"Messages": [{
            "From": {"Email": cfg["MAILJET_SENDER_EMAIL"], "Name": cfg["BRAND_NAME"]},
            "To": [{"Email": to_email, "Name": _clean_header(to_name)}],
            "Subject": _clean_header(subject), "TextPart": text, "HTMLPart": html}]}
        attempts.append(lambda: _https_send("Mailjet", MAILJET_URL, {"authorization": f"Basic {token}"}, mj_payload, event, to_email))
    if cfg.get("RESEND_API_KEY") and cfg.get("RESEND_SENDER_EMAIL"):
        rs_payload = {"from": formataddr((_clean_header(cfg["BRAND_NAME"]), cfg["RESEND_SENDER_EMAIL"])),
                      "to": [to_email], "subject": _clean_header(subject), "html": html, "text": text}
        attempts.append(lambda: _https_send("Resend", RESEND_URL, {"authorization": f"Bearer {cfg['RESEND_API_KEY']}"}, rs_payload, event, to_email))
    if not attempts:
        log.warning("Email NOT sent (no email provider configured): event=%s to=%s subject=%s", event, to_email, subject)
        return False
    threading.Thread(target=_deliver, args=(attempts, event, to_email), daemon=True).start()
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
