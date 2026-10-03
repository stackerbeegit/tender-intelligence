from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
) -> list[User]:
    """Admin-only. Broader listing/filtering/pagination arrives with the
    rest of the API design in later sprints (brief §19)."""
    stmt = select(User).options(joinedload(User.role)).order_by(User.created_at)
    return list(db.scalars(stmt))
