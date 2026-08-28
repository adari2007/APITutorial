"""A tiny, in-memory user store for demonstrating POST APIs.

This is intentionally simple — for a tutorial, not production:
  * Users live in a plain dict and disappear when the server restarts.
  * Passwords are salted + hashed with the standard library (pbkdf2), so we
    never store them in plain text — but a real app would use a database and a
    vetted library (e.g. passlib/bcrypt).
  * "Access tokens" are random opaque strings kept in a dict. A real app would
    typically issue signed, expiring JWTs.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timezone


class UserError(Exception):
    """Raised for user/auth problems, carrying an HTTP status code."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# username -> stored user record
_users: dict[str, dict] = {}
# token -> username
_tokens: dict[str, str] = {}


def _hash_password(password: str, salt: bytes) -> str:
    """Return a hex digest of the salted password (pbkdf2-hmac-sha256)."""
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return dk.hex()


def create_user(username: str, email: str, password: str) -> dict:
    """Register a new user. Raises UserError(409) if the username is taken."""
    if username in _users:
        raise UserError(f"Username already exists: {username!r}", status_code=409)

    salt = os.urandom(16)
    _users[username] = {
        "username": username,
        "email": email,
        "salt": salt,
        "password_hash": _hash_password(password, salt),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return public_view(_users[username])


def authenticate(username: str, password: str) -> str:
    """Verify credentials and return a fresh access token.

    Raises UserError(401) on any mismatch (same message either way, so we
    don't reveal whether the username exists).
    """
    user = _users.get(username)
    invalid = UserError("Invalid username or password", status_code=401)
    if user is None:
        raise invalid
    if not secrets.compare_digest(
        user["password_hash"], _hash_password(password, user["salt"])
    ):
        raise invalid

    token = secrets.token_urlsafe(32)
    _tokens[token] = username
    return token


def user_for_token(token: str | None) -> dict:
    """Resolve a Bearer token to its user. Raises UserError(401) if invalid."""
    username = _tokens.get(token or "")
    if username is None:
        raise UserError("Missing or invalid access token", status_code=401)
    return public_view(_users[username])


def public_view(user: dict) -> dict:
    """Strip secrets (salt, hash) before returning a user to a client."""
    return {
        "username": user["username"],
        "email": user["email"],
        "created_at": user["created_at"],
    }
