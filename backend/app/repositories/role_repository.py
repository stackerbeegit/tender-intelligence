from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.role import Role


class RoleRepository:
    """DB access only — no business rules. Services decide what a missing
    role means; this class just queries."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_name(self, name: str) -> Role | None:
        return self.db.scalar(select(Role).where(Role.name == name))

    def get_by_id(self, role_id) -> Role | None:
        return self.db.get(Role, role_id)

    def list_all(self) -> list[Role]:
        return list(self.db.scalars(select(Role).order_by(Role.name)))
