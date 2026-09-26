"""Inbound Beckn Protocol v2.0.0 Authorization header verification.

Guarantees:
  - Parses Beckn Signature header: keyId, algorithm, created, expires, headers, signature
  - Recomputes BLAKE2b-512 digest of the request body
  - Rejects clock skew > 30s
  - Rejects replayed message_id using 10 min TTL in cache
  - Looks up signer's public key in ONDC registry
  - Rejects unknown subscribers and invalid signatures
"""

import base64
import hashlib
import logging
import re
import time
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519
from fastapi import Request

from app.cache.client import CacheClient, get_cache_client
from app.ondc.auth.registry import RegistryClient, get_registry_client

logger = logging.getLogger("app.ondc.auth.verification")

AUTH_HEADER_PATTERN = re.compile(r'([a-zA-Z0-9_\-]+)="([^"]+)"')
MAX_CLOCK_SKEW_SECONDS = 30
MESSAGE_ID_DEDUP_TTL_SECONDS = 600  # 10 minutes


def parse_authorization_header(header_value: str) -> dict[str, str] | None:
    """Parse key="value" pairs from Beckn Authorization header."""
    if not header_value.startswith("Signature "):
        return None
    content = header_value[len("Signature "):].strip()
    matches = AUTH_HEADER_PATTERN.findall(content)
    if not matches:
        return None
    return dict(matches)


async def check_message_id_replay(message_id: str, cache: CacheClient) -> bool:
    """Returns True if message_id was previously seen within the 10 min deduplication window."""
    if not message_id:
        return False
    key = f"agri:beckn:msg_replay:{message_id}"
    exists = await cache.exists(key)
    if exists:
        return True
    await cache.set(key, "1", ex=MESSAGE_ID_DEDUP_TTL_SECONDS)
    return False


async def verify_beckn_authorization_header(
    auth_header: str | None,
    body_bytes: bytes,
    message_id: str | None = None,
    registry: RegistryClient | None = None,
    cache: CacheClient | None = None,
) -> tuple[bool, str | None]:
    """Verify inbound Beckn request signature against registry public key.

    Returns:
      (is_valid, error_reason)
    """
    if not auth_header:
        return False, "Missing Authorization header"

    parsed = parse_authorization_header(auth_header)
    if not parsed:
        return False, "Malformed Authorization header format"

    key_id = parsed.get("keyId")
    algorithm = parsed.get("algorithm")
    created_str = parsed.get("created")
    expires_str = parsed.get("expires")
    sig_b64 = parsed.get("signature")

    if not all([key_id, algorithm, created_str, expires_str, sig_b64]):
        return False, "Authorization header missing required fields"

    if algorithm.lower() != "ed25519":
        return False, f"Unsupported algorithm '{algorithm}', expected 'ed25519'"

    # 1. Parse keyId: <subscriber_id>|<unique_key_id>|ed25519
    key_parts = key_id.split("|")
    if len(key_parts) < 2:
        return False, "Invalid keyId format in Authorization header"

    subscriber_id = key_parts[0]
    unique_key_id = key_parts[1]

    # 2. Clock skew verification (max 30s skew)
    now = int(time.time())
    try:
        created = int(created_str)
        expires = int(expires_str)
    except ValueError:
        return False, "Invalid created or expires epoch timestamp"

    if abs(now - created) > MAX_CLOCK_SKEW_SECONDS:
        return False, f"Clock skew exceeded: request created at {created}, current time is {now} (skew {abs(now - created)}s > {MAX_CLOCK_SKEW_SECONDS}s)"

    # 3. Request expiration verification
    if now > expires:
        return False, f"Request has expired at epoch {expires} (current time {now})"

    # 4. Message ID replay check (10 min TTL)
    if message_id:
        cache_client = cache or get_cache_client()
        is_replay = await check_message_id_replay(message_id, cache_client)
        if is_replay:
            return False, f"Replay detected for message_id '{message_id}'"

    # 5. Registry lookup for subscriber public key
    registry_client = registry or get_registry_client()
    participant = await registry_client.lookup(subscriber_id, unique_key_id=unique_key_id)
    if not participant or not participant.signing_public_key:
        return False, f"Subscriber '{subscriber_id}' not found or has no signing public key in registry"

    # 6. Recompute BLAKE2b-512 digest
    digest_bytes = hashlib.blake2b(body_bytes, digest_size=64).digest()
    digest_b64 = base64.b64encode(digest_bytes).decode("ascii")
    expected_digest_header = f"BLAKE-512={digest_b64}"

    # 7. Reconstruct canonical signing string
    signing_string = f"(created): {created}\n(expires): {expires}\ndigest: {expected_digest_header}"

    # 8. Cryptographic Ed25519 signature verification
    try:
        raw_pub_bytes = base64.b64decode(participant.signing_public_key.encode("ascii"))
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(raw_pub_bytes)
        sig_bytes = base64.b64decode(sig_b64.encode("ascii"))
        public_key.verify(sig_bytes, signing_string.encode("utf-8"))
        return True, None
    except InvalidSignature:
        return False, "Invalid cryptographic Ed25519 signature"
    except Exception as exc:
        return False, f"Signature verification error: {exc}"


async def verify_inbound_beckn_request(
    request: Request,
    body_bytes: bytes,
    context: dict[str, Any] | None = None,
    registry: RegistryClient | None = None,
    cache: CacheClient | None = None,
) -> tuple[bool, str | None]:
    """Verify inbound FastAPI Beckn request."""
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    msg_id = None
    if context and isinstance(context, dict):
        msg_id = context.get("message_id")
    return await verify_beckn_authorization_header(
        auth_header=auth_header,
        body_bytes=body_bytes,
        message_id=msg_id,
        registry=registry,
        cache=cache,
    )
