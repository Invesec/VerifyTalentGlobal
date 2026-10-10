def email_configured(cfg):
    """True when at least one real email provider is set up (Gmail/SMTP or Brevo)."""
    smtp = bool(cfg.get("SMTP_USER") and cfg.get("SMTP_PASSWORD"))
    brevo = bool(cfg.get("BREVO_API_KEY") and cfg.get("BREVO_SENDER_EMAIL"))
    return smtp or brevo
