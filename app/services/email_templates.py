from html import escape

NAVY, GOLD = "#0A2A6B", "#D9A21B"


def _wrap(heading, paragraphs_html):
    return f"""<!DOCTYPE html><html><body style="margin:0;background:#F3F7FC;font-family:Arial,Helvetica,sans-serif;color:#0F1B33">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#fff;border-radius:10px;overflow:hidden">
<tr><td style="background:{NAVY};padding:20px 28px;color:#fff;font-size:20px;font-weight:bold">Verify<span style="color:{GOLD}">Talent</span>Global</td></tr>
<tr><td style="padding:28px;line-height:1.6;font-size:16px"><h1 style="margin:0 0 16px;font-size:22px;color:{NAVY}">{heading}</h1>{paragraphs_html}</td></tr>
<tr><td style="padding:16px 28px;background:#F3F7FC;font-size:12px;color:#4A5873">Find. Verify. Match.<br>VerifyTalent Global does not guarantee employment, interviews, job offers, or placement.</td></tr>
</table></td></tr></table></body></html>"""


def application_received(full_name, application_id):
    name, app_id = escape(full_name), escape(application_id)
    subject = "VerifyTalent Global: we received your application"
    html = _wrap("Application received", f"""
<p>Hello {name},</p>
<p>Thank you for applying to the VerifyTalent Global talent network. We have received your application.</p>
<p style="background:#F3F7FC;border-left:4px solid {GOLD};padding:12px 16px"><strong>Your Application ID:</strong> {app_id}<br>Keep this ID. You will need it if you contact us.</p>
<p>Your application is now under review by our team. Registering does not guarantee employment, an interview, a job offer, or placement.</p>
<p>If your application progresses, VerifyTalent Global will contact you by email with the next steps.</p>
<p>Kind regards,<br>The VerifyTalent Global Team</p>""")
    text = (f"Hello {full_name},\n\nThank you for applying to the VerifyTalent Global talent network. "
            f"We have received your application.\n\nYour Application ID: {application_id}\n\n"
            "Your application is now under review. Registering does not guarantee employment, an interview, "
            "a job offer, or placement. If your application progresses, VerifyTalent Global will contact you "
            "by email with the next steps.\n\nKind regards,\nThe VerifyTalent Global Team")
    return subject, html, text


# ---- Milestone 3 templates ----
def _build(subject, heading, paragraphs, box=None):
    """paragraphs: plain strings (escaped here). box: optional (label, value) highlighted line."""
    body = "".join(f"<p>{escape(p)}</p>" for p in paragraphs)
    text = "\n\n".join(paragraphs)
    if box:
        body = (f'<p style="background:#F3F7FC;border-left:4px solid {GOLD};padding:12px 16px">'
                f"<strong>{escape(box[0])}:</strong> {escape(box[1])}</p>") + body
        text = f"{box[0]}: {box[1]}\n\n" + text
    return subject, _wrap(escape(heading), body), text


def _note(message):
    return [f"Note from our team: {message}"] if message else []


NO_GUARANTEE = "This does not guarantee employment, an interview, a job offer, or placement."
FEE_DISCLAIMER = ("The $60 Talent Verification & Onboarding Fee covers application processing, professional "
                  "screening/review, verification, talent profile creation, qualification/document review where "
                  "applicable, your official VerifyTalent Global ID card, verified talent network onboarding, "
                  "eligibility for relevant job matching, and onboarding support. Payment does not guarantee "
                  "employment, an interview, a job offer, or placement.")


def under_review(name, message=""):
    return _build("VerifyTalent Global: your application is under review", "Application under review",
                  [f"Hello {name},", "Our team has started reviewing your application. You do not need to do anything now.",
                   *_note(message), "If your application progresses, we will contact you by email. " + NO_GUARANTEE])


def assessment_required(name, message=""):
    return _build("VerifyTalent Global: assessment required", "Assessment required",
                  [f"Hello {name},", "As part of our screening, we need you to complete an assessment for your profession.",
                   *_note(message), "Please watch your email for instructions. " + NO_GUARANTEE])


def application_approved(name, application_id, message=""):
    return _build("VerifyTalent Global: Application Approved", "Application approved",
                  [f"Hello {name},", "Good news: you have passed our initial review and may now proceed to the onboarding stage.",
                   "Log in to your dashboard to see your next steps.", *_note(message),
                   "Approval is not a job offer, and you have not been hired. " + NO_GUARANTEE],
                  box=("Application ID", application_id))


def onboarding_instructions(name, application_id, contact_lines):
    paras = [f"Hello {name},", "To complete your onboarding, the Talent Verification & Onboarding Fee is $60.",
             FEE_DISCLAIMER,
             "To pay, contact the official VerifyTalent Global administrator and quote your Application ID."]
    paras += contact_lines or ["Official contact details are shown on your onboarding page after you log in."]
    paras += ["Only use the official contact details above or on your dashboard. VerifyTalent Global will never ask "
              "for your password or card PIN."]
    return _build("VerifyTalent Global: onboarding and payment instructions", "Complete your onboarding", paras,
                  box=("Application ID", application_id))


def payment_confirmed(name, amount, currency, reference):
    return _build("VerifyTalent Global: payment confirmed", "Payment confirmed",
                  [f"Hello {name},", f"We have confirmed your onboarding payment of {amount} {currency}.",
                   "Thank you. Your verification is now complete.", NO_GUARANTEE],
                  box=("Payment reference", reference))


def id_card_ready(name, talent_id):
    return _build("VerifyTalent Global: your ID card is ready", "You are now a Verified Talent",
                  [f"Hello {name},", "Your VerifyTalent Global ID card is ready. Log in and open the ID Card page to view it.",
                   "You are now part of our verified talent network and eligible for relevant job matching. " + NO_GUARANTEE,
                   "This is an internal VerifyTalent Global professional ID card. It is not a government-issued document."],
                  box=("Talent ID", talent_id))


def application_rejected(name, message=""):
    return _build("VerifyTalent Global: update on your application", "Application update",
                  [f"Hello {name},", "Thank you for your interest in VerifyTalent Global. After review, we are not able "
                   "to progress your application at this time.", *_note(message), "We appreciate the time you took to apply."])


# ---- Milestone 4: companies ----
def client_received(contact, company, application_id):
    return _build("VerifyTalent Global: we received your company application", "Company application received",
                  [f"Hello {contact},", f"Thank you for registering {company} with VerifyTalent Global. Your application is under review.",
                   "Next steps: company review, approval, a client agreement for you to review and accept, then activation. "
                   "An official Client ID is issued only after all of these steps are complete.",
                   "Registering does not create an agreement or guarantee talent matches or hires."],
                  box=("Application ID", application_id))


def client_approved(contact, company, message=""):
    return _build("VerifyTalent Global: company application approved", "Company application approved",
                  [f"Hello {contact},", f"Good news: the application for {company} has been approved.",
                   "Next we will send you a client agreement to review and accept. Your account is not active until that is done.",
                   *_note(message)])


def agreement_sent(contact, company, agreement_id, expires):
    paras = [f"Hello {contact},", f"The client agreement for {company} is ready for your review.",
             "Please log in, open Agreements, read the document, and accept or decline it."]
    if expires:
        paras.append(f"Please respond by {expires}.")
    return _build("VerifyTalent Global: your client agreement is ready", "Client agreement ready", paras,
                  box=("Agreement ID", agreement_id))


def client_activated(contact, company, client_id, agreement_id):
    return _build("VerifyTalent Global: your client account is active", "Your account is active",
                  [f"Hello {contact},", f"{company} is now an active VerifyTalent Global client.",
                   f"Your agreement reference is {agreement_id}. Log in to your dashboard to see your account.",
                   "Talent matches are reviewed by our team before they are presented to you, and are not a guarantee of hiring."],
                  box=("Client ID", client_id))


# ---- Milestone 5: jobs ----
def job_opportunity(name, job_title, profession, work_mode, contract_type):
    return _build("VerifyTalent Global: new job opportunity", "New job opportunity",
                  [f"Hello {name},", "You have been shortlisted for a role that may suit your profile.",
                   f"Role: {job_title} ({profession}). {work_mode}, {contract_type}.",
                   "Log in and open Opportunities to see the details and tell us whether you are interested.",
                   "Being shortlisted does not guarantee an interview, a job offer, or placement."])


def interview_invitation(name, job_title, when_text, details):
    return _build("VerifyTalent Global: interview invitation", "Interview invitation",
                  [f"Hello {name},", f"A client would like to interview you for: {job_title}.",
                   f"When: {when_text}", f"Details: {details}",
                   "Please reply to the VerifyTalent Global team if you cannot attend. An interview is not a job offer."])


def placement_notification(name, job_title, company):
    return _build("VerifyTalent Global: placement confirmed", "Placement confirmed",
                  [f"Hello {name},", f"We are pleased to confirm your placement as {job_title} with {company}.",
                   "Our team will contact you with the next steps."])


# ---- Milestone 6 ----
def password_reset(name, link):
    subject, html, text = _build("VerifyTalent Global: reset your password", "Reset your password",
                                 [f"Hello {name},", "We received a request to reset your password. The link below works for one hour and can be used once.",
                                  "If you did not ask for this, you can ignore this email and your password will stay the same."])
    html = html.replace("</td></tr>\n<tr><td style=\"padding:16px 28px", f'<p><a href="{escape(link)}" style="display:inline-block;background:{NAVY};color:#fff;padding:12px 22px;border-radius:8px;text-decoration:none;font-weight:bold">Choose a new password</a></p><p style="font-size:13px;color:#4A5873">Or copy this link: {escape(link)}</p></td></tr>\n<tr><td style="padding:16px 28px', 1)
    return subject, html, text + f"\n\nReset link: {link}"


# ---- Milestone 7 ----
def verification_code(name, code):
    return _build("VerifyTalent Global: your verification code", "Verify your email",
                  [f"Hello {name},", "Enter this code on VerifyTalent Global to confirm your email address. It expires in 15 minutes.",
                   "If you did not create an account, you can ignore this email."],
                  box=("Your code", code))
