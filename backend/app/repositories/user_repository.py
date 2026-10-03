import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.user import User


class UserRepository:
    """DB access only — no business rules (password hashing, token issuance,
    etc. live in services/auth_service.py)."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).options(joinedload(User.role)).where(User.email == email)
        return self.db.scalar(stmt)

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).options(joinedload(User.role)).where(User.id == user_id)
        return self.db.scalar(stmt)

    def create(self, *, email: str, hashed_password: str, full_name: str, role_id: uuid.UUID) -> User:
        user = User(email=email, hashed_password=hashed_password, full_name=full_name, role_id=role_id)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def mark_login(self, user: User) -> None:
        user.last_login_at = datetime.now(timezone.utc)
        self.db.add(user)
        self.db.commit()

    def exists_with_email(self, email: str) -> bool:
        return self.get_by_email(email) is not None
