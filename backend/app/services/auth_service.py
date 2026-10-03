"""
Business logic for registration, login, and token refresh. No HTTP concepts
here (no HTTPException, no status codes) — see app/core/exceptions.py.
"""
import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    RoleNotFoundError,
)
from app.core.security import TokenType, create_token, decode_token, hash_password, verify_password
from app.models.user import User
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse
from app.schemas.user import UserCreate
from app.services import audit_service


def register_user(db: Session, payload: UserCreate) -> User:
    users = UserRepository(db)
    roles = RoleRepository(db)

    if users.exists_with_email(payload.email):
        raise EmailAlreadyRegisteredError(payload.email)

    role = roles.get_by_name(payload.role_name)
    if role is None:
        raise RoleNotFoundError(payload.role_name)

    user = users.create(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role_id=role.id,
    )
    audit_service.record(db, action="user.register", user_id=user.id, entity_type="user", entity_id=str(user.id))
    return user


def _issue_tokens(user: User) -> TokenResponse:
    access = create_token(user.id, TokenType.ACCESS, extra_claims={"role": user.role.name})
    refresh = create_token(user.id, TokenType.REFRESH)
    return TokenResponse(access_token=access, refresh_token=refresh)


def authenticate(db: Session, email: str, password: str, ip_address: str | None = None) -> TokenResponse:
    users = UserRepository(db)
    user = users.get_by_email(email)
    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError(email)
    if not user.is_active:
        raise InactiveUserError(email)

    users.mark_login(user)
    audit_service.record(
        db,
        action="user.login",
        user_id=user.id,
        entity_type="user",
        entity_id=str(user.id),
        ip_address=ip_address,
    )
    return _issue_tokens(user)


def refresh_access_token(db: Session, refresh_token: str) -> TokenResponse:
    try:
        payload = decode_token(refresh_token)
    except Exception as exc:  # jwt.PyJWTError and subclasses
        raise InvalidTokenError(str(exc)) from exc

    if payload.get("type") != TokenType.REFRESH.value:
        raise InvalidTokenError("Token is not a refresh token")

    users = UserRepository(db)
    user = users.get_by_id(uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise InvalidTokenError("User no longer valid")

    return _issue_tokens(user)
