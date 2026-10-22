"""
Sends notifications and records every attempt on `notifications`. Sending
never raises into the caller: a status change must not fail because the
mail server is down. The outcome (sent / failed / skipped, with the
error) is stored instead, per brief Rule 6 — nothing silently lost.

Sends synchronously for now (a handful of recipients per event); moving
delivery onto the Celery worker is Sprint 8 work alongside document
processing.
"""
from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.enums import NotificationStatus
from app.models.notification import Notification
from app.models.user import User
from app.notifications import email as email_channel

logger = get_logger(__name__)


def app_link(path: str) -> str:
    return get_settings().app_base_url.rstrip("/") + path


def notify(
    db: Session,
    users: Iterable[User],
    *,
    event_type: str,
    subject: str,
    text: str,
    html: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    exclude: User | None = None,
) -> list[Notification]:
    """One e-mail per distinct active recipient (minus `exclude`, usually the
    person who caused the event). Commits the notification rows."""
    sender = email_channel.get_email_sender()
    rows: list[Notification] = []
    seen: set = set()
    for user in users:
        if user is None or not user.is_active or user.id in seen or (exclude is not None and user.id == exclude.id):
            continue
        seen.add(user.id)
        row = Notification(
            user_id=user.id,
            channel="email",
            event_type=event_type,
            subject=subject[:500],
            body_text=text,
            entity_type=entity_type,
            entity_id=entity_id,
            status=NotificationStatus.SKIPPED,
        )
        try:
            sender.send(email_channel.EmailMessage(to=user.email, subject=subject, text=text, html=html))
            row.status = NotificationStatus.SENT
            row.sent_at = datetime.now(timezone.utc)
        except email_channel.EmailNotConfiguredError as exc:
            row.status = NotificationStatus.SKIPPED
            row.error = str(exc)
        except Exception as exc:  # noqa: BLE001 — recorded on the row; must not break the caller
            logger.exception("E-mail to %s failed (%s)", user.email, event_type)
            row.status = NotificationStatus.FAILED
            row.error = f"{type(exc).__name__}: {exc}"[:2000]
        db.add(row)
        rows.append(row)
    db.commit()
    return rows
