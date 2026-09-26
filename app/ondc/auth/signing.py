"""Ed25519 signing and BLAKE2b-512 digest utilities for Beckn Protocol v2.0.0."""

import base64
import hashlib
import time
from typing import NamedTuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.config import Settings, get_settings


class KeyPair(NamedTuple):
    private_key: ed25519.Ed25519PrivateKey
    public_key: ed25519.Ed25519PublicKey
    signing_public_key_b64: str
    signing_private_key_b64: str


def generate_key_pair(seed_bytes: bytes | None = None) -> KeyPair:
    """Generate or derive an Ed25519 keypair."""
    if seed_bytes and len(seed_bytes) == 32:
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed_bytes)
    else:
        private_key = ed25519.Ed25519PrivateKey.generate()

    public_key = private_key.public_key()
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return KeyPair(
        private_key=private_key,
        public_key=public_key,
        signing_public_key_b64=base64.b64encode(pub_bytes).decode("ascii"),
        signing_private_key_b64=base64.b64encode(priv_bytes).decode("ascii"),
    )


def compute_blake2b_digest(body: bytes) -> str:
    """Compute BLAKE2b-512 digest formatted as BLAKE-512=<base64>."""
    digest_bytes = hashlib.blake2b(body, digest_size=64).digest()
    digest_b64 = base64.b64encode(digest_bytes).decode("ascii")
    return f"BLAKE-512={digest_b64}"


def build_authorization_header(
    body: bytes,
    subscriber_id: str,
    unique_key_id: str,
    private_key: ed25519.Ed25519PrivateKey,
    created: int | None = None,
    ttl_seconds: int = 300,
) -> str:
    """Build Beckn Protocol v2.0.0 Authorization header with Ed25519 and BLAKE2b-512 digest.

    Format:
      Signature keyId="<sub_id>|<unique_key_id>|ed25519", algorithm="ed25519",
      created="<epoch>", expires="<epoch>", headers="(created) (expires) digest",
      signature="<b64>"
    """
    now = int(time.time()) if created is None else created
    expires = now + ttl_seconds
    digest_header = compute_blake2b_digest(body)

    signing_string = f"(created): {now}\n(expires): {expires}\ndigest: {digest_header}"
    sig_bytes = private_key.sign(signing_string.encode("utf-8"))
    sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

    return (
        f'Signature keyId="{subscriber_id}|{unique_key_id}|ed25519", '
        f'algorithm="ed25519", '
        f'created="{now}", '
        f'expires="{expires}", '
        f'headers="(created) (expires) digest", '
        f'signature="{sig_b64}"'
    )


class PlatformSigner:
    """Singleton platform signer for BPP/BAP outbound messages."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.subscriber_id = self.settings.ondc_bpp_id
        self.unique_key_id = "key-1"
        # Deterministic test seed if none configured
        seed = hashlib.sha256(b"agri-platform-default-ed25519-seed").digest()
        self.keypair = generate_key_pair(seed)

    def sign_request(self, body_bytes: bytes, subscriber_id: str | None = None) -> str:
        sub_id = subscriber_id or self.subscriber_id
        return build_authorization_header(
            body=body_bytes,
            subscriber_id=sub_id,
            unique_key_id=self.unique_key_id,
            private_key=self.keypair.private_key,
        )


_platform_signer: PlatformSigner | None = None


def get_platform_signer(settings: Settings | None = None) -> PlatformSigner:
    global _platform_signer
    if _platform_signer is None:
        _platform_signer = PlatformSigner(settings=settings)
    return _platform_signer
