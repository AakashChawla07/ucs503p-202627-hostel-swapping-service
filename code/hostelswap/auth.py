"""Password hashing and session-cookie auth.

No external auth provider: passwords are salted PBKDF2 hashes (stdlib
only), and a session is an opaque random token stored server-side in
`sessions`, handed to the browser as an httpOnly cookie.
"""

import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, Depends, HTTPException, Request

from . import db

COOKIE_NAME = "hostelswap_session"
SESSION_LIFETIME = timedelta(days=7)
_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt, _, expected = stored.partition("$")
    if not salt or not expected:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS)
    return secrets.compare_digest(digest.hex(), expected)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    roll_no: str
    name: str
    role: str


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def session_expiry() -> datetime:
    return datetime.now(timezone.utc) + SESSION_LIFETIME


def current_user(
    request: Request,
    session: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> CurrentUser:
    connection = db.dsn()
    if not connection or not session:
        raise HTTPException(status_code=401, detail="not logged in")
    row = db.fetch_session_user(connection, session)
    if row is None:
        raise HTTPException(status_code=401, detail="session expired or invalid")
    return CurrentUser(**row)


def require_role(role: str):
    def dependency(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        if user.role != role:
            raise HTTPException(status_code=403, detail=f"{role} access required")
        return user

    return dependency
