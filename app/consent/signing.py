import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime

PURPOSE = "Market Linkage and Profile Verification"
PROFILE_ATTRIBUTES = frozenset({"profile", "land"})


@dataclass(frozen=True)
class ConsentRecord:
    artifact_id: str
    farmer_id: str
    purpose: str
    attributes: tuple[str, ...]
    created_at: datetime
    expires_at: datetime
    status: str


def canonical_grant(
    *,
    artifact_id: str,
    farmer_id: str,
    purpose: str,
    attributes: list[str] | tuple[str, ...],
    created_at: datetime,
    expires_at: datetime,
) -> bytes:
    payload = {
        "artifact_id": artifact_id,
        "attributes": sorted(attributes),
        "created_at": _stamp(created_at),
        "expires_at": _stamp(expires_at),
        "farmer_id": farmer_id,
        "purpose": purpose,
    }
    return json.dumps(payload, separators=(",", ":")).encode()


def canonical_withdrawal(artifact_id: str) -> bytes:
    payload = {"action": "withdraw", "artifact_id": artifact_id}
    return json.dumps(payload, separators=(",", ":")).encode()


def sign(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def signature_matches(payload: bytes, signature: str, secret: str) -> bool:
    expected = sign(payload, secret)
    return hmac.compare_digest(expected, signature.strip().lower())


def authorize_profile_fetch(
    artifact: ConsentRecord | None,
    farmer_id: str,
    now: datetime,
) -> str | None:
    if artifact is None or artifact.status != "active":
        return "Consent is not active"
    if artifact.expires_at <= now:
        return "Consent has expired"
    if artifact.farmer_id != farmer_id:
        return "Consent does not cover this farmer"
    if artifact.purpose != PURPOSE:
        return "Consent purpose is not allowed"
    if not PROFILE_ATTRIBUTES <= set(artifact.attributes):
        return "Consent does not cover this data"
    return None


def _stamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
