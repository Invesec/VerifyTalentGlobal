import re
from datetime import datetime, timezone

from flask import Blueprint, render_template
from sqlalchemy import select

from ..extensions import db
from ..models import TalentApplication, TalentID, User
from ..security import rate_limit

bp = Blueprint("verify", __name__)
TALENT_ID_RE = re.compile(r"^VTG-TL-\d{6}$")


@bp.get("/verify/talent/<talent_id>")
@rate_limit("verify", 60, 60, methods=("GET",))
def talent(talent_id):
    """Public page. Shows limited information only: no email, phone, address, payment, documents, or notes."""
    record = None
    if TALENT_ID_RE.match(talent_id):
        record = db.session.execute(
            select(TalentID, TalentApplication, User)
            .join(TalentApplication, TalentID.application_id == TalentApplication.id)
            .join(User, TalentApplication.user_id == User.id)
            .where(TalentID.talent_id == talent_id)).first()
    if record is None:
        return render_template("verify/talent.html", title="Verification | VerifyTalent Global", found=False,
                               talent_id=talent_id[:20]), 404
    card, application, user = record
    expires = card.expires_at
    valid = card.status == "ACTIVE" and (expires is None or expires > datetime.now(timezone.utc))
    return render_template("verify/talent.html", title="Verification | VerifyTalent Global", found=True,
                           talent_id=card.talent_id, name=user.full_name, profession=application.profession,
                           issued=card.issued_at, expires=expires, valid=valid, card_status=card.status)
