"""ONDC BAP (Buyer App) outbound client for driving network Beckn transactions.

Guarantees:
  - Broadcasts search across the network or to specific BPPs
  - Drives select, init, confirm, status, track, cancel, update, support, rating
  - Signs every outbound request with Ed25519 + BLAKE2b-512 Authorization header
  - Uses canonical Beckn v2.0.0 envelopes with JSON-LD @context
"""

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.ondc.auth.signing import get_platform_signer
from app.ondc.schemas import (
    DEFAULT_JSONLD_CONTEXT,
    DOMAIN_AGRICULTURE,
    PROTOCOL_VERSION_V2,
)

logger = logging.getLogger("app.ondc.bap.client")


class BapClient:
    """Outbound client for BAP buyer interactions across the ONDC network."""

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        allow_private: bool | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.bap_id = getattr(self.settings, "ondc_bap_id", "buyer.market.local")
        self.bap_uri = getattr(self.settings, "ondc_bap_uri", "http://127.0.0.1:8000/beckn/bap")
        self.signer = get_platform_signer(self.settings)
        self._transport = transport
        self._allow_private = (
            allow_private
            if allow_private is not None
            else (transport is not None or self.settings.environment != "production")
        )

    def _build_context(
        self,
        action: str,
        transaction_id: str | None = None,
        bpp_id: str | None = None,
        bpp_uri: str | None = None,
    ) -> dict[str, Any]:
        """Construct standard Beckn v2.0.0 context for buyer request."""
        return {
            "@context": DEFAULT_JSONLD_CONTEXT,
            "domain": DOMAIN_AGRICULTURE,
            "action": action,
            "version": PROTOCOL_VERSION_V2,
            "core_version": PROTOCOL_VERSION_V2,
            "bap_id": self.bap_id,
            "bap_uri": self.bap_uri,
            "bpp_id": bpp_id,
            "bpp_uri": bpp_uri,
            "transaction_id": transaction_id or f"tx_{uuid.uuid4().hex[:16]}",
            "message_id": f"msg_{uuid.uuid4().hex[:16]}",
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ttl": "PT30S",
        }

    async def _send_request(
        self,
        target_uri: str,
        action: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Serialize, sign, and dispatch outbound HTTP POST request to BPP."""
        body_bytes = json.dumps(payload, default=str).encode("utf-8")
        auth_header = self.signer.sign_request(body_bytes, subscriber_id=self.bap_id)

        headers = {
            "Content-Type": "application/json",
            "Authorization": auth_header,
        }

        endpoint = f"{target_uri.rstrip('/')}/{action}"
        try:
            from app.common.http_client import SafeAsyncClient

            async with SafeAsyncClient(
                transport=self._transport,
                allow_private=self._allow_private,
                settings=self.settings,
            ) as client:
                resp = await client.post(endpoint, content=body_bytes, headers=headers)
                return {
                    "status_code": resp.status_code,
                    "body": resp.json() if resp.status_code == 200 else resp.text,
                    "ack": resp.status_code == 200,
                }
        except Exception as exc:
            logger.warning("BAP outbound dispatch to %s failed: %s", endpoint, exc)
            return {
                "status_code": 500,
                "error": str(exc),
                "ack": False,
            }

    async def search(
        self,
        commodity: str | None = None,
        grade: str | None = None,
        bpp_uri: str | None = None,
        transaction_id: str | None = None,
    ) -> dict[str, Any]:
        """Broadcast search for lots by commodity and grade."""
        ctx = self._build_context("search", transaction_id=transaction_id)
        item_filter: dict[str, Any] = {}
        if commodity:
            item_filter["descriptor"] = {"name": commodity}
        if grade:
            item_filter.setdefault("descriptor", {})["code"] = grade

        payload = {
            "context": ctx,
            "message": {
                "intent": {
                    "item": item_filter if item_filter else None,
                    "category": {"id": "AGRICULTURE_COMMODITY"},
                }
            },
        }

        target = bpp_uri or self.settings.ondc_bpp_uri
        return await self._send_request(target, "search", payload)

    async def select(
        self,
        bpp_uri: str,
        lot_code: str,
        transaction_id: str,
        provider_id: str | None = None,
        quantity_mt: float = 1.0,
    ) -> dict[str, Any]:
        """Select a specific lot and request quotation."""
        ctx = self._build_context("select", transaction_id=transaction_id, bpp_uri=bpp_uri)
        payload = {
            "context": ctx,
            "message": {
                "order": {
                    "provider": {"id": provider_id} if provider_id else None,
                    "items": [
                        {
                            "id": lot_code,
                            "quantity": {"measure": {"unit": "metric_ton", "value": str(quantity_mt)}},
                        }
                    ],
                }
            },
        }
        return await self._send_request(bpp_uri, "select", payload)

    async def init(
        self,
        bpp_uri: str,
        lot_code: str,
        transaction_id: str,
        buyer_name: str,
        buyer_phone: str,
        delivery_address: str,
        delivery_gps: str,
        quantity_mt: float = 1.0,
    ) -> dict[str, Any]:
        """Initialize order with delivery terms and request TLC generation."""
        ctx = self._build_context("init", transaction_id=transaction_id, bpp_uri=bpp_uri)
        payload = {
            "context": ctx,
            "message": {
                "order": {
                    "items": [{"id": lot_code, "quantity": {"measure": {"unit": "metric_ton", "value": str(quantity_mt)}}}],
                    "billing": {
                        "name": buyer_name,
                        "phone": buyer_phone,
                        "address": delivery_address,
                    },
                    "fulfillments": [
                        {
                            "end": {
                                "location": {"gps": delivery_gps, "address": {"street_address": delivery_address}},
                                "contact": {"phone": buyer_phone},
                            }
                        }
                    ],
                }
            },
        }
        return await self._send_request(bpp_uri, "init", payload)

    async def confirm(
        self,
        bpp_uri: str,
        transaction_id: str,
        order_id: str,
        payment_amount_inr: int,
        payment_mode: str = "ESCROW",
    ) -> dict[str, Any]:
        """Confirm order with payment escrow reference."""
        ctx = self._build_context("confirm", transaction_id=transaction_id, bpp_uri=bpp_uri)
        payload = {
            "context": ctx,
            "message": {
                "order": {
                    "id": order_id,
                    "payment": {
                        "params": {"amount": str(payment_amount_inr), "currency": "INR"},
                        "status": "PAID",
                        "type": payment_mode,
                    },
                }
            },
        }
        return await self._send_request(bpp_uri, "confirm", payload)

    async def status(self, bpp_uri: str, transaction_id: str, order_id: str | None = None) -> dict[str, Any]:
        """Poll order fulfillment status."""
        ctx = self._build_context("status", transaction_id=transaction_id, bpp_uri=bpp_uri)
        payload = {"context": ctx, "message": {"order_id": order_id or transaction_id}}
        return await self._send_request(bpp_uri, "status", payload)

    async def track(self, bpp_uri: str, transaction_id: str, order_id: str | None = None) -> dict[str, Any]:
        """Request active live tracking URL."""
        ctx = self._build_context("track", transaction_id=transaction_id, bpp_uri=bpp_uri)
        payload = {"context": ctx, "message": {"order_id": order_id or transaction_id}}
        return await self._send_request(bpp_uri, "track", payload)

    async def cancel(self, bpp_uri: str, transaction_id: str, order_id: str, reason_id: str = "001") -> dict[str, Any]:
        """Request order cancellation."""
        ctx = self._build_context("cancel", transaction_id=transaction_id, bpp_uri=bpp_uri)
        payload = {
            "context": ctx,
            "message": {"order_id": order_id, "cancellation_reason_id": reason_id},
        }
        return await self._send_request(bpp_uri, "cancel", payload)

    async def update(self, bpp_uri: str, transaction_id: str, order_id: str, update_target: str) -> dict[str, Any]:
        """Request order update."""
        ctx = self._build_context("update", transaction_id=transaction_id, bpp_uri=bpp_uri)
        payload = {
            "context": ctx,
            "message": {"update_target": update_target, "order": {"id": order_id}},
        }
        return await self._send_request(bpp_uri, "update", payload)

    async def support(self, bpp_uri: str, transaction_id: str, issue_dict: dict[str, Any] | None = None) -> dict[str, Any]:
        """Submit IGM support issue."""
        ctx = self._build_context("support", transaction_id=transaction_id, bpp_uri=bpp_uri)
        payload = {
            "context": ctx,
            "message": {"ref_id": transaction_id, "issue": issue_dict},
        }
        return await self._send_request(bpp_uri, "support", payload)

    async def rating(
        self,
        bpp_uri: str,
        transaction_id: str,
        target_id: str,
        score: int,
        category: str = "seller",
        feedback: str | None = None,
    ) -> dict[str, Any]:
        """Submit post-fulfillment rating."""
        ctx = self._build_context("rating", transaction_id=transaction_id, bpp_uri=bpp_uri)
        payload = {
            "context": ctx,
            "message": {
                "id": target_id,
                "rating_category": category,
                "value": score,
                "feedback": feedback,
            },
        }
        return await self._send_request(bpp_uri, "rating", payload)
