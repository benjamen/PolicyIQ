"""Core security primitives: password hashing, JWT tokens, API key hashing.

Design references:
- docs/10-AUTH-AND-ACCOUNTS.md (argon2id, JWT access tokens, long-lived API keys)
- docs/13-COMPETITIVE-STRATEGY.md section 5 (named-user access + API tokens)

No personal insurance information is handled here - email is a login
identifier only, and tokens carry no client data.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# --- Configuration (env-driven, matches the existing os.environ pattern) ---

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-insecure-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

_ph = PasswordHasher()  # argon2id with safe defaults


# --- Password hashing (argon2id) ---


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False


# --- JWT access tokens ---


def create_access_token(user_id: str, email: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Returns the payload dict or None if invalid/expired."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


# --- API keys (long-lived, hashed at rest) ---

API_KEY_PREFIX = "piq_"


def generate_api_key() -> tuple[str, str, str]:
    """Returns (raw_key, sha256_hash, display_prefix).

    The raw key is shown exactly once at creation; only the hash is stored.
    """
    raw = API_KEY_PREFIX + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    prefix = raw[:12]  # e.g. "piq_ab12cd34"
    return raw, key_hash, prefix


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
