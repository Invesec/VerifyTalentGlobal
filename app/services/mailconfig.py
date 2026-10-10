def email_configured(cfg):
    """True when at least one real email provider is set up (Gmail/SMTP, Brevo, Mailjet or Resend)."""
    smtp = bool(cfg.get("SMTP_USER") and cfg.get("SMTP_PASSWORD"))
    brevo = bool(cfg.get("BREVO_API_KEY") and cfg.get("BREVO_SENDER_EMAIL"))
    mailjet = bool(cfg.get("MAILJET_API_KEY") and cfg.get("MAILJET_SECRET_KEY") and cfg.get("MAILJET_SENDER_EMAIL"))
    resend = bool(cfg.get("RESEND_API_KEY") and cfg.get("RESEND_SENDER_EMAIL"))
    return smtp or brevo or mailjet or resend
