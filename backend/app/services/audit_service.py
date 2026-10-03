import uuid

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record(
    db: Session,
    *,
    action: str,
    user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """
    Append-only write. Never raises on a logging concern blocking the
    calling request would be worse than losing one audit row, but any
    failure here is still a bug — it surfaces via normal exception
    propagation so it gets caught by request-level error handling/logging,
    not silently swallowed (brief Rule 6).
    """
    entry = AuditLog(
        action=action,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
        ip_address=ip_address,
    )
    db.add(entry)
    db.commit()
    return entry
