"""Authentication endpoints: register, login, logout, me.

Session model: opaque random token in an HttpOnly cookie (also accepted as an
Authorization: Bearer header for API clients); only the SHA-256 of the token is
persisted. Registration is open — this is a portfolio demo, and the limitation
is documented in the README.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request, Response
from sqlalchemy import delete, select

from app.api.deps import DbSession
from app.core.errors import ConflictError, UnauthorizedError, UnprocessableError
from app.core.security import hash_password, hash_token, new_session_token, verify_password
from app.models.entities import SessionToken, User
from app.schemas.auth import LoginRequest, RegisterRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_COOKIE = "sentinex_session"
SESSION_TTL = timedelta(days=7)
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9._@+-]{3,64}$")


def _utcnow_naive() -> datetime:
    """Naive UTC clock — SQLite DateTime columns store naive values."""
    return datetime.now(UTC).replace(tzinfo=None)


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, username=user.username, display_name=user.display_name)


def _issue_session(db, user: User, request: Request, response: Response) -> UserOut:
    raw, token_hash = new_session_token()
    db.add(
        SessionToken(
            token_hash=token_hash,
            user_id=user.id,
            expires_at=_utcnow_naive() + SESSION_TTL,
            user_agent=(request.headers.get("user-agent") or "")[:255],
        )
    )
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        raw,
        httponly=True,
        samesite="lax",
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
    )
    return _user_out(user)


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: RegisterRequest, db: DbSession) -> UserOut:
    username = payload.username.strip().lower()
    # Emails are accepted as usernames (abc@gmail.com is fine). Everything
    # else that isn't a sane identifier is rejected with a HELPFUL message.
    if not _USERNAME_RE.match(username):
        if "@" in username:
            raise UnprocessableError(
                "invalid_username",
                "That email address is missing something (check the format, e.g. name@gmail.com), "
                "or use a plain username: 3-64 characters — letters, numbers, or . _ @ + -.",
            )
        raise UnprocessableError(
            "invalid_username",
            "Username must be 3-64 characters and may contain letters, numbers, and . _ @ + - "
            "(you can use your email address).",
        )
    if len(payload.password) < 8:
        raise UnprocessableError(
            "invalid_password",
            "Password must be at least 8 characters long.",
        )
    if db.scalar(select(User.id).where(User.username == username)):
        raise ConflictError("username_taken", f"Username {username!r} is already registered.")
    user = User(
        username=username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, db: DbSession, request: Request, response: Response) -> UserOut:
    user = db.scalar(select(User).where(User.username == payload.username.strip().lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise UnauthorizedError("invalid_credentials", "Incorrect username or password.")
    return _issue_session(db, user, request, response)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: DbSession) -> None:
    raw = request.cookies.get(SESSION_COOKIE)
    if raw:
        db.execute(delete(SessionToken).where(SessionToken.token_hash == hash_token(raw)))
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=UserOut)
def me(request: Request, db: DbSession) -> UserOut:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        raise UnauthorizedError("unauthorized", "No active session.")
    session = db.get(SessionToken, hash_token(raw))
    if session is None or session.expires_at < _utcnow_naive():
        raise UnauthorizedError("unauthorized", "Session expired or invalid.")
    user = db.get(User, session.user_id)
    if user is None:
        raise UnauthorizedError("unauthorized", "Session user no longer exists.")
    return _user_out(user)
