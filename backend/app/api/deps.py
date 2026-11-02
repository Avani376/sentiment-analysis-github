"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import UnauthorizedError
from app.core.security import hash_token
from app.db.session import get_db
from app.models.entities import SessionToken, User
from app.services.registry import ModelRegistry, get_registry

DbSession = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def registry_dep() -> Generator[ModelRegistry, None, None]:
    yield get_registry()


RegistryDep = Annotated[ModelRegistry, Depends(registry_dep)]


def get_current_user(request: Request, db: DbSession) -> User | None:
    """Resolve the session user from the HttpOnly cookie or a bearer header."""
    raw = request.cookies.get("sentinex_session")
    if not raw:
        header = request.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            raw = header[7:].strip()
    if not raw:
        return None
    session = db.get(SessionToken, hash_token(raw))
    if session is None:
        return None
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires < datetime.now(UTC):
        return None
    return db.get(User, session.user_id)


def require_user(user: Annotated[User | None, Depends(get_current_user)]) -> User:
    """Dependency for mutating endpoints: 401 unless logged in."""
    if user is None:
        raise UnauthorizedError("unauthorized", "Login required for this action.")
    return user


CurrentUser = Annotated[User | None, Depends(get_current_user)]
AuthUser = Annotated[User, Depends(require_user)]
