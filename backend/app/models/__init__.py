"""
Import every model module here so `Base.metadata` is fully populated for
Alembic autogenerate and for `Base.metadata.create_all()` in tests. As new
sprints add tables (tenders, sources, opportunities, ...), import them here
too.
"""
from app.models.base import Base  # noqa: F401
from app.models.role import Role  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401

__all__ = ["Base", "Role", "User", "AuditLog"]
