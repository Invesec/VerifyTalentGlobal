"""Talent categories, professions, and category-specific questions."""

CATEGORIES = {
    "Technology & IT": ["Software Developer", "Web Developer", "Mobile Developer", "Cybersecurity Specialist",
                        "Cloud/DevOps Engineer", "Data Analyst", "AI/ML Specialist", "IT Support", "QA/Test Engineer"],
    "Design & Creative": ["Logo Designer", "Graphic Designer", "UI/UX Designer", "Brand Designer", "Video Editor",
                          "Motion Graphics Designer", "3D Designer", "Illustrator"],
    "Architecture & Engineering": ["Architect", "AutoCAD Designer", "CAD Draftsman", "3D Architectural Visualizer",
                                   "Civil Engineer", "Mechanical Engineer", "Electrical Engineer", "Structural Designer"],
    "Writing & Marketing": ["Copywriter", "Content Writer", "Technical Writer", "SEO Writer", "Social Media Manager",
                            "Digital Marketer", "Email Marketing Specialist"],
    "Language & Communication": ["Translator", "Interpreter", "Proofreader", "Transcriptionist", "Localization Specialist"],
    "Business & Administration": ["Virtual Assistant", "Project Manager", "Accountant", "Bookkeeper",
                                  "Customer Support Specialist", "Data Entry Specialist", "Research Assistant"],
}

PROFESSION_TO_CATEGORY = {p: c for c, items in CATEGORIES.items() for p in items}

AVAILABILITY = ["Full-time", "Part-time", "Contract / project-based", "Not available right now"]

# group key -> (title, professions, [(field, label)])
FIELD_GROUPS = {
    "developer": ("Developer details",
                  ["Software Developer", "Web Developer", "Mobile Developer", "Cloud/DevOps Engineer"],
                  [("languages", "Programming languages"), ("frameworks", "Frameworks"), ("databases", "Databases"),
                   ("git", "Git/GitHub profile or experience"), ("cloud", "Cloud platforms"),
                   ("projects", "Key projects")]),
    "cybersecurity": ("Cybersecurity details", ["Cybersecurity Specialist"],
                      [("specialization", "Security specialization"), ("tools", "Tools you use"),
                       ("certs", "Security certifications"), ("networking", "Networking experience"),
                       ("linux", "Linux experience"), ("siem", "SIEM experience"),
                       ("pentest", "Penetration testing experience"), ("projects", "Security projects")]),
    "designer": ("Design details",
                 ["Logo Designer", "Graphic Designer", "UI/UX Designer", "Brand Designer", "Video Editor",
                  "Motion Graphics Designer", "3D Designer", "Illustrator"],
                 [("software", "Design software"), ("specialization", "Specialization"),
                  ("projects", "Previous projects")]),
    "architect": ("Architecture details",
                  ["Architect", "AutoCAD Designer", "CAD Draftsman", "3D Architectural Visualizer"],
                  [("specialization", "Architecture specialization"), ("autocad", "AutoCAD experience"),
                   ("revit", "Revit experience"), ("sketchup", "SketchUp experience"),
                   ("rendering", "3D rendering tools"), ("qualifications", "Qualifications")]),
    "writer": ("Writing details", ["Copywriter", "Content Writer", "Technical Writer", "SEO Writer"],
               [("specialization", "Writing specialization"), ("industries", "Industries you write for"),
                ("seo", "SEO experience"), ("advertising", "Advertising experience"),
                ("samples", "Links to writing samples")]),
    "translator": ("Language details",
                   ["Translator", "Interpreter", "Proofreader", "Transcriptionist", "Localization Specialist"],
                   [("native", "Native language"), ("pairs", "Language pairs (for example English to French)"),
                    ("specialization", "Specialization (legal, medical, technical, and so on)"),
                    ("certs", "Certifications"), ("samples", "Links to translation samples")]),
}

PROFESSION_TO_GROUP = {p: key for key, (_t, profs, _f) in FIELD_GROUPS.items() for p in profs}

STATUS_LABELS = {
    "NEW": "New", "SCREENING": "Screening", "ASSESSMENT": "Assessment", "INTERVIEW": "Interview",
    "VERIFICATION": "Verification", "APPROVED": "Approved", "REJECTED": "Not progressed",
    "PAYMENT_PENDING": "Payment pending", "PAYMENT_VERIFIED": "Payment verified",
    "ID_PROCESSING": "ID processing", "VERIFIED_TALENT": "Verified Talent", "AVAILABLE": "Available",
    "MATCHED": "Matched", "INTERVIEWING": "Interviewing", "PLACED": "Placed", "UNAVAILABLE": "Unavailable",
}


TALENT_STEPS = ["Applied", "Under review", "Onboarding", "Verified", "Matching", "Placed"]
_TALENT_STEP_OF_STATUS = {
    "NEW": 1, "SCREENING": 1, "ASSESSMENT": 1, "INTERVIEW": 1, "VERIFICATION": 1,
    "APPROVED": 2, "PAYMENT_PENDING": 2, "PAYMENT_VERIFIED": 3, "ID_PROCESSING": 3,
    "VERIFIED_TALENT": 3, "AVAILABLE": 3, "MATCHED": 4, "INTERVIEWING": 4, "PLACED": 5,
}


def talent_progress(status):
    """Returns (steps, current_index) for the progress tracker, or (None, None) when it does not apply."""
    index = _TALENT_STEP_OF_STATUS.get(status)
    return (TALENT_STEPS, index) if index is not None else (None, None)
