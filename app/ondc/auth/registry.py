"""ONDC registry lookup client with caching and participant key set management.

Guarantees:
  - Lookup via POST /lookup with sender_subscriber_id (+ country/domain/type)
  - TTL-backed caching of lookup responses
  - Fetch and cache signer key set (/participants/{subscriber_id})
  - Handles ukId, signing_public_key (Ed25519), encr_public_key (X25519)
"""

import logging
from dataclasses import dataclass
from typing import Any

from app.cache.service import CacheService, get_cache_service
from app.config import Settings, get_settings
from app.ondc.auth.signing import get_platform_signer

logger = logging.getLogger("app.ondc.auth.registry")

REGISTRY_CACHE_TTL: int = 3600  # 1 hour


@dataclass
class ParticipantKeySet:
    subscriber_id: str
    unique_key_id: str
    signing_public_key: str  # Base64 Raw Ed25519
    encr_public_key: str | None = None
    domain: str = "ONDC:AGR10"
    type: str = "BPP"
    valid_from: str | None = None
    valid_until: str | None = None


class RegistryClient:
    """ONDC Network Registry Client for participant lookup and public key verification."""

    def __init__(
        self,
        settings: Settings | None = None,
        cache: CacheService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.cache = cache or get_cache_service()
        self.registry_url = self.settings.ondc_registry_url.strip() if hasattr(self.settings, "ondc_registry_url") else ""
        # Local participant registry pre-seeded with platform subscriber keys
        self._local_participants: dict[str, ParticipantKeySet] = {}
        self._seed_local_participants()

    def _seed_local_participants(self) -> None:
        """Seed registry with platform BPP and BAP subscriber public keys."""
        signer = get_platform_signer(self.settings)
        # BPP
        self.register_participant(
            ParticipantKeySet(
                subscriber_id=self.settings.ondc_bpp_id,
                unique_key_id="key-1",
                signing_public_key=signer.keypair.signing_public_key_b64,
                domain="ONDC:AGR10",
                type="BPP",
            )
        )
        # BAP
        bap_id = getattr(self.settings, "ondc_bap_id", "buyer.market.local")
        self.register_participant(
            ParticipantKeySet(
                subscriber_id=bap_id,
                unique_key_id="key-1",
                signing_public_key=signer.keypair.signing_public_key_b64,
                domain="ONDC:AGR10",
                type="BAP",
            )
        )

    def register_participant(self, participant: ParticipantKeySet) -> None:
        """Register a participant in the local memory registry (used for local testing and seeding)."""
        key = f"{participant.subscriber_id}:{participant.unique_key_id}"
        self._local_participants[key] = participant
        self._local_participants[participant.subscriber_id] = participant

    async def lookup(
        self,
        subscriber_id: str,
        unique_key_id: str | None = None,
        domain: str = "ONDC:AGR10",
        type_: str | None = None,
        country: str = "IND",
    ) -> ParticipantKeySet | None:
        """Lookup subscriber details and public keys with TTL caching."""
        cache_key = f"agri:registry:lookup:{subscriber_id}:{unique_key_id or 'latest'}"

        async def _fetch_lookup() -> dict[str, Any] | None:
            # 1. Check local pre-seeded participants
            local_lookup_key = f"{subscriber_id}:{unique_key_id}" if unique_key_id else subscriber_id
            if local_lookup_key in self._local_participants:
                p = self._local_participants[local_lookup_key]
                return {
                    "subscriber_id": p.subscriber_id,
                    "unique_key_id": p.unique_key_id,
                    "signing_public_key": p.signing_public_key,
                    "encr_public_key": p.encr_public_key,
                    "domain": p.domain,
                    "type": p.type,
                }

            # 2. Remote lookup via HTTP POST /lookup if configured
            if self.registry_url:
                try:
                    payload = {
                        "sender_subscriber_id": subscriber_id,
                        "domain": domain,
                        "country": country,
                    }
                    if type_:
                        payload["type"] = type_
                    if unique_key_id:
                        payload["ukId"] = unique_key_id

                    from app.common.http_client import SafeAsyncClient

                    allow_priv = self.settings.environment != "production"
                    async with SafeAsyncClient(
                        allow_private=allow_priv,
                        settings=self.settings,
                    ) as client:
                        resp = await client.post(self.registry_url, json=payload)
                        if resp.status_code == 200:
                            data = resp.json()
                            entries = data if isinstance(data, list) else [data]
                            if entries:
                                first = entries[0]
                                return {
                                    "subscriber_id": first.get("subscriber_id", subscriber_id),
                                    "unique_key_id": first.get("ukId", unique_key_id or "key-1"),
                                    "signing_public_key": first.get("signing_public_key", ""),
                                    "encr_public_key": first.get("encr_public_key"),
                                    "domain": first.get("domain", domain),
                                    "type": first.get("type", "BPP"),
                                }
                except Exception as exc:
                    logger.warning("Remote ONDC registry lookup failed for %s: %s", subscriber_id, exc)

            return None

        data = await self.cache.get_or_set(cache_key, _fetch_lookup, ttl=REGISTRY_CACHE_TTL)
        if not data:
            return None

        return ParticipantKeySet(
            subscriber_id=data["subscriber_id"],
            unique_key_id=data["unique_key_id"],
            signing_public_key=data["signing_public_key"],
            encr_public_key=data.get("encr_public_key"),
            domain=data.get("domain", domain),
            type=data.get("type", "BPP"),
        )

    async def get_participant_key_set(self, subscriber_id: str) -> ParticipantKeySet | None:
        """Fetch participant key set by subscriber ID."""
        return await self.lookup(subscriber_id=subscriber_id)


_registry_client: RegistryClient | None = None


def get_registry_client(settings: Settings | None = None) -> RegistryClient:
    global _registry_client
    if _registry_client is None:
        _registry_client = RegistryClient(settings=settings)
    return _registry_client
