"""Rule-based matching (no paid AI). Weights: skills 40, experience 20, profession 20, location 10, availability 10."""
import re

from sqlalchemy import select

from ..extensions import db
from ..models import Match, TalentApplication, TalentID, User

ELIGIBLE_STATUSES = ["VERIFIED_TALENT", "AVAILABLE", "MATCHED", "INTERVIEWING"]
MAX_MATCHES = 25
_SPLIT = re.compile(r"[,;\n]+")


def _tokens(text):
    seen, out = set(), []
    for part in _SPLIT.split(text or ""):
        token = part.strip().lower()
        if token and token not in seen:
            seen.add(token)
            out.append(token)
    return out


def _has(haystack, needle):
    return re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", haystack) is not None


def score_match(job, talent):
    """Returns {'score': 0-100, 'breakdown': {...}}. Pure function: easy to test and explain."""
    required = _tokens(job.required_skills)
    text = " ".join([talent.skills or ""] + [str(v) for v in (talent.details or {}).values()]).lower()
    matched = [t for t in required if _has(text, t)]
    skills = 40.0 * len(matched) / len(required) if required else 20.0  # no skills listed = neutral

    need, have = job.min_experience_years or 0, talent.years_experience or 0
    experience = 20.0 if need <= 0 or have >= need else 20.0 * have / need

    if talent.profession == job.profession:
        profession = 20.0
    elif talent.category == job.category:
        profession = 10.0
    else:
        profession = 0.0

    loc, country = (job.location or "").strip().lower(), (talent.country or "").strip().lower()
    same_country = bool(loc) and (loc in country or country in loc)
    if job.work_mode == "Remote":
        location = 10.0 if (not loc or same_country) else 5.0
    else:
        location = 10.0 if same_country else 0.0

    if talent.availability == "Not available right now":
        availability = 0.0
    elif talent.availability == job.contract_type:
        availability = 10.0
    else:
        availability = 5.0

    total = round(skills + experience + profession + location + availability)
    return {
        "score": max(0, min(100, total)),
        "breakdown": {"skills": round(skills), "experience": round(experience), "profession": round(profession),
                      "location": round(location), "availability": round(availability),
                      "matched_skills": matched, "missing_skills": [t for t in required if t not in matched]},
    }


def run_matching(job):
    """Scores every eligible verified talent and stores the best matches. Does not commit.
    Existing matches that an admin has already moved forward are never changed."""
    talents = db.session.scalars(
        select(TalentApplication)
        .join(User, TalentApplication.user_id == User.id)
        .join(TalentID, TalentID.application_id == TalentApplication.id)
        .where(TalentApplication.status.in_(ELIGIBLE_STATUSES), User.is_active.is_(True), TalentID.status == "ACTIVE")
    ).all()
    scored = sorted(((score_match(job, t), t) for t in talents), key=lambda pair: pair[0]["score"], reverse=True)
    existing = {m.talent_application_id: m for m in db.session.scalars(select(Match).where(Match.job_id == job.id))}
    changed = 0
    for result, talent in scored[:MAX_MATCHES]:
        if result["score"] <= 0:
            continue
        match = existing.get(talent.id)
        if match is None:
            db.session.add(Match(job_id=job.id, talent_application_id=talent.id, score=result["score"],
                                 breakdown=result["breakdown"], status="SUGGESTED"))
            changed += 1
        elif match.status == "SUGGESTED":
            match.score, match.breakdown = result["score"], result["breakdown"]
            changed += 1
    return changed
