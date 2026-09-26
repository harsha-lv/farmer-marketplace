"""Cryptographic primitives for password hashing, API keys, and JWT tokens."""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

from app.config import get_settings


def utcnow() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Password Hashing (Argon2id PHC)
# ---------------------------------------------------------------------------

ARGON2_MEMORY_COST = 65536
ARGON2_ITERATIONS = 3
ARGON2_LANES = 4
ARGON2_KEY_LENGTH = 32
ARGON2_SALT_LENGTH = 16


def hash_password(password: str) -> str:
    """Hash a password using Argon2id with standard PHC encoding."""
    salt = os.urandom(ARGON2_SALT_LENGTH)
    kdf = Argon2id(
        salt=salt,
        length=ARGON2_KEY_LENGTH,
        iterations=ARGON2_ITERATIONS,
        lanes=ARGON2_LANES,
        memory_cost=ARGON2_MEMORY_COST,
    )
    return kdf.derive_phc_encoded(password.encode("utf-8"))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against an Argon2id PHC-encoded hash."""
    try:
        Argon2id.verify_phc_encoded(plain_password.encode("utf-8"), hashed_password)
        return True
    except (InvalidKey, ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# API Key Management
# Format: ak_live_<32 alphanumeric chars>
# Stored as SHA-256 hash, display prefix ak_live_<first 6 chars>
# ---------------------------------------------------------------------------


def generate_api_key() -> tuple[str, str, str]:
    """Generate an API key, its short display prefix, and its SHA-256 hash.

    Returns:
        tuple[str, str, str]: (plain_key, key_prefix, hashed_key)
    """
    random_part = secrets.token_hex(16)  # 32 hex chars
    plain_key = f"ak_live_{random_part}"
    key_prefix = plain_key[:14]  # e.g., "ak_live_a1b2c3"
    hashed_key = hashlib.sha256(plain_key.encode("utf-8")).hexdigest()
    return plain_key, key_prefix, hashed_key


def hash_token(raw_token: str) -> str:
    """Hash a token using SHA-256 for secure storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# JWT (HMAC-SHA256)
# Standard base64url-encoded header.payload.signature
# ---------------------------------------------------------------------------


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _base64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


def sign_jwt(payload: dict[str, Any], secret: str | None = None) -> str:
    """Sign a JWT dictionary with HMAC-SHA256."""
    settings = get_settings()
    secret_key = (secret or settings.jwt_secret_key).encode("utf-8")

    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode()

    signature = hmac.new(secret_key, signing_input, hashlib.sha256).digest()
    encoded_sig = _base64url_encode(signature)

    return f"{encoded_header}.{encoded_payload}.{encoded_sig}"


def decode_jwt(token: str, secret: str | None = None) -> dict[str, Any]:
    """Verify and decode a JWT. Raises ValueError on invalid or expired token."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format")

    encoded_header, encoded_payload, encoded_sig = parts
    settings = get_settings()
    secret_key = (secret or settings.jwt_secret_key).encode("utf-8")

    signing_input = f"{encoded_header}.{encoded_payload}".encode()
    expected_sig = hmac.new(secret_key, signing_input, hashlib.sha256).digest()
    actual_sig = _base64url_decode(encoded_sig)

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("Invalid token signature")

    payload_json = _base64url_decode(encoded_payload).decode("utf-8")
    payload = json.loads(payload_json)

    # Check expiration
    exp = payload.get("exp")
    if exp is not None:
        now_ts = int(datetime.now(UTC).timestamp())
        if now_ts >= exp:
            raise ValueError("Token has expired")

    return payload


def create_access_token(
    user_id: int | str,
    roles: list[str],
    org_id: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a 15-minute scoped JWT access token."""
    settings = get_settings()
    delta = expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    now = datetime.now(UTC)
    exp = now + delta

    payload = {
        "sub": str(user_id),
        "email": email,
        "phone": phone,
        "roles": roles,
        "org_id": org_id,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return sign_jwt(payload)


def create_refresh_token(
    user_id: int | str,
    family_id: str | None = None,
    expires_delta: timedelta | None = None,
) -> tuple[str, str, datetime]:
    """Create a 30-day refresh token with family tracking.

    Returns:
        tuple[str, str, datetime]: (raw_token, family_id, expires_at)
    """
    settings = get_settings()
    delta = expires_delta or timedelta(days=settings.jwt_refresh_token_expire_days)
    now = datetime.now(UTC)
    exp = now + delta
    fam_id = family_id or str(uuid.uuid4())

    payload = {
        "sub": str(user_id),
        "family_id": fam_id,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = sign_jwt(payload)
    return token, fam_id, exp


def extract_token_from_header(auth_header: str | None) -> str | None:
    """Extract token supporting both 'Authorization: Bearer <token>' and 'Authorization: token <token>'."""
    if not auth_header:
        return None
    header_str = auth_header.strip()
    match = re.match(r"^(?:Bearer|token)\s+(\S+)$", header_str, re.IGNORECASE)
    if match:
        return match.group(1)
    return None
