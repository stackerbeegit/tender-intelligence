from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.config import get_settings
from app.core.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.notifications import digest
from app.schemas.opportunity import DigestPreview, NotificationRead
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
def my_notifications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=30, ge=1, le=200),
):
    stmt = (
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


@router.get("/digest/preview", response_model=DigestPreview)
def preview_digest(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Today's digest for the signed-in user, rendered but not sent."""
    content = digest.build_digest(db, user, datetime.now(timezone.utc))
    subject, text, html = digest.render_digest(content, user.full_name, get_settings().app_base_url)
    return DigestPreview(subject=subject, text=text, html=html, is_empty=content.is_empty)


@router.post("/digest/test", response_model=NotificationRead)
def send_test_digest(db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    """Sends the admin their own digest now — to check SMTP settings and
    how the e-mail renders. The outcome (sent/failed/skipped) is returned."""
    content = digest.build_digest(db, admin, datetime.now(timezone.utc))
    subject, text, html = digest.render_digest(content, admin.full_name, get_settings().app_base_url)
    [row] = notification_service.notify(
        db, [admin], event_type="digest.test", subject=f"[Test] {subject}", text=text, html=html
    )
    return row
