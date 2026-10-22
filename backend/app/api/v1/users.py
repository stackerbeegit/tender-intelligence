from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.user import User
from app.schemas.opportunity import DirectoryUser
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


@router.get("/directory", response_model=list[DirectoryUser])
def user_directory(db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> list[DirectoryUser]:
    """Active users' names and roles, for choosing an owner or assignee.
    No other account details."""
    stmt = select(User).options(joinedload(User.role)).where(User.is_active.is_(True)).order_by(User.full_name)
    return [
        DirectoryUser(id=u.id, full_name=u.full_name, email=u.email, role=u.role.name) for u in db.scalars(stmt)
    ]
