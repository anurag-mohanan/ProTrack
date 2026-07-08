from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.auth_deps import get_current_user, require_roles
from app.api.deps import Session, get_db
from app.crud.foundation import get_email_template_by_slug
from app.models.models import User
from app.schemas.settings import ManualEmailRequest
from app.services.email_service import send_templated_email

router = APIRouter(
    prefix="/emails",
    tags=["emails"],
    dependencies=[
        Depends(get_current_user),
        Depends(require_roles("Admin", "Engineering Manager", "Design Leader", "Project Manager")),
    ],
)


@router.post("/send")
def send_manual_email(payload: ManualEmailRequest, db: Session = Depends(get_db)):
    template = get_email_template_by_slug(db, payload.template_slug)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email template not found")

    addresses = [address.strip() for address in payload.to_addresses if address.strip()]
    for user_id in payload.user_ids:
        user = db.get(User, user_id)
        if user and user.email:
            addresses.append(user.email)

    if not addresses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one recipient email address is required.",
        )

    sent = send_templated_email(
        db,
        template_slug=payload.template_slug,
        to_addresses=addresses,
        context=payload.context,
    )
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Email could not be sent. Verify SMTP settings are enabled and configured.",
        )
    return {"sent": True, "recipient_count": len(addresses)}
