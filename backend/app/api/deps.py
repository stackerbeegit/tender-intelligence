"""
Shared FastAPI dependencies: DB session, current authenticated user, and a
role-based access guard factory. Every protected endpoint depends on
`get_current_user` (or `require_roles(...)`) rather than re-implementing
token parsing.
"""
import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import TokenType, decode_token
from app.models.user import User
from app.repositories.user_repository import UserRepository

# tokenUrl is documentation-only here; the actual login endpoint takes JSON,
# not form-encoded credentials — see api/v1/auth.py.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=True)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise credentials_exc

    if payload.get("type") != TokenType.ACCESS.value:
        raise credentials_exc

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise credentials_exc

    user = UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise credentials_exc

    return user


def require_roles(*allowed_roles: str):
    """Usage: `Depends(require_roles("admin"))`. Raises 403 if the current
    user's role isn't in the allowed set."""

    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role.name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role.name}' is not permitted to perform this action",
            )
        return user

    return _check
