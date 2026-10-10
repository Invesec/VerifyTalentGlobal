from flask import Blueprint, Response, render_template

from ..talent_data import CATEGORIES as TALENT_CATEGORIES

bp = Blueprint("main", __name__)

TALENT_STEPS = [
    ("Register for free", "Tell us about your profession, skills, and experience."),
    ("Screening", "Our team reviews your application and may ask for an assessment."),
    ("Verification and onboarding", "Approved professionals complete verification and receive a VerifyTalent Global Talent ID."),
    ("Matching", "Verified talent is considered when relevant client roles open."),
]
CLIENT_STEPS = [
    ("Register your company", "Share your business details and recruitment needs."),
    ("Company review", "We review your application before anything is issued."),
    ("Client agreement", "Approved companies receive an agreement and are activated once it is accepted."),
    ("Job requests and matches", "Submit a job request, then review talent matches presented by our team."),
]
CATEGORIES = [
    ("Technology & IT", "Software, web, and mobile development, cybersecurity, cloud/DevOps, data analysis, AI/ML, IT support, QA"),
    ("Design & Creative", "Logo, graphic, UI/UX, and brand design, video editing, motion graphics, 3D design, illustration"),
    ("Architecture & Engineering", "Architecture, AutoCAD and CAD drafting, 3D visualization, civil, mechanical, electrical, and structural design"),
    ("Writing & Marketing", "Copywriting, content and technical writing, SEO, social media, digital and email marketing"),
    ("Language & Communication", "Translation, interpreting, proofreading, transcription, localization"),
    ("Business & Administration", "Virtual assistance, project management, accounting, bookkeeping, customer support, data entry, research"),
]
FAQS = [
    ("Is registration free?", "Yes. Professionals register for free. After approval, there is a one-time Talent Verification & Onboarding Fee of $60, explained in full before you pay."),
    ("Does paying the fee guarantee me a job?", "No. Payment does not guarantee employment, an interview, a job offer, or placement. It covers verification and onboarding, and makes you eligible for relevant job matching."),
    ("How do companies get started?", "Companies register, are reviewed, and receive a client agreement. A Client ID is issued only after the agreement is accepted and the account is activated."),
]


@bp.get("/")
def home():
    return render_template(
        "home.html",
        title="VerifyTalent Global | Find. Verify. Match.",
        talent_steps=TALENT_STEPS, client_steps=CLIENT_STEPS,
        categories=CATEGORIES, faqs=FAQS,
    )


PAGES = {
    "about": "About us", "how-it-works": "How it works", "find-talent": "Find talent",
    "for-companies": "For companies", "categories": "Talent categories", "contact": "Contact",
    "privacy": "Privacy Policy", "terms": "Terms of Use",
}


def _make_page(slug, title):
    def view():
        return render_template(f"pages/{slug}.html", title=f"{title} | VerifyTalent Global", page_title=title,
                               categories=TALENT_CATEGORIES)
    return view


for _slug, _title in PAGES.items():
    bp.add_url_rule(f"/{_slug}", endpoint="page_" + _slug.replace("-", "_"), view_func=_make_page(_slug, _title))


@bp.get("/robots.txt")
def robots():
    body = ("User-agent: *\nDisallow: /admin\nDisallow: /client\nDisallow: /talent\nDisallow: /account\n"
            "Disallow: /verify\nAllow: /\n")
    return Response(body, mimetype="text/plain")
