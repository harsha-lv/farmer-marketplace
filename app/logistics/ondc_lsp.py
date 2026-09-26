"""ONDC Beckn Logistics Service Provider (LSP) BAP client.

Acts as a BAP (Buyer App) toward third-party logistics BPPs:
  - Builds and sends Beckn `search` on the ONDC P2P and P2H2P logistics domains.
  - Specifies pickup/drop GPS coordinates, commodity, weight/volume, vehicle profile,
    and cold-chain requirements.
  - Normalizes multiple `on_search` quotes from network LSPs into a canonical `FreightQuote`.
  - Drives `select`, `init`, and `confirm` toward the chosen LSP.
  - Persists the booked shipment reference to the database.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.logistics.models import Shipment
from app.ondc.auth.signing import get_platform_signer
from app.ondc.schemas import (
    DEFAULT_JSONLD_CONTEXT,
    PROTOCOL_VERSION_V2,
)

logger = logging.getLogger("app.logistics.ondc_lsp")

DOMAIN_LOGISTICS_P2P = "nic2004:60232"   # ONDC standard P2P logistics domain
DOMAIN_LOGISTICS_P2H2P = "ONDC:LOG11"     # Hub-routed P2H2P logistics domain


@dataclass
class FreightQuote:
    """Canonical normalized freight quotation across network LSPs and internal estimates."""

    quote_id: str
    lsp_id: str
    lsp_name: str
    lsp_uri: str
    price: int                      # Price in INR
    eta_hours: float                # Transit hours to delivery
    vehicle: str                    # TRACTOR_TROLLEY, LITTLE_TRUCK, MEDIUM_TRUCK, HEAVY_TRUCK
    cold_chain: bool
    terms: dict[str, Any]
    validity: str | None = None
    source: str = "network"         # "network" | "internal"
    is_committed_offer: bool = True # False for internal benchmark quotes
    tracking_enabled: bool = True
    category: str = "P2P"           # "P2P" | "P2H2P"
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_iso8601_duration_hours(tat: str | None) -> float:
    """Parse ISO8601 duration such as 'PT24H', 'PT6H30M', or 'P1D' into hours."""
    if not tat:
        return 24.0
    text = tat.strip().upper()
    try:
        hours = 0.0
        days_match = re.search(r"(\d+)D", text)
        if days_match:
            hours += float(days_match.group(1)) * 24.0
        hours_match = re.search(r"(\d+(?:\.\d+)?)H", text)
        if hours_match:
            hours += float(hours_match.group(1))
        minutes_match = re.search(r"(\d+)M", text)
        if minutes_match:
            hours += float(minutes_match.group(1)) / 60.0
        return round(hours if hours > 0 else 24.0, 2)
    except Exception:
        return 24.0


class OndcLspClient:
    """Platform client driving logistics transactions over ONDC network."""

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        allow_private: bool | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.bap_id = getattr(self.settings, "ondc_logistics_bap_id", "agri-logistics.bap.local")
        self.bap_uri = getattr(
            self.settings,
            "ondc_logistics_bap_uri",
            "http://127.0.0.1:8000/api/v1/logistics/webhook",
        )
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
        domain: str = DOMAIN_LOGISTICS_P2P,
        transaction_id: str | None = None,
        bpp_id: str | None = None,
        bpp_uri: str | None = None,
    ) -> dict[str, Any]:
        """Build canonical Beckn v2.0.0 logistics context."""
        now_str = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "@context": DEFAULT_JSONLD_CONTEXT,
            "domain": domain,
            "action": action,
            "version": PROTOCOL_VERSION_V2,
            "core_version": PROTOCOL_VERSION_V2,
            "bap_id": self.bap_id,
            "bap_uri": self.bap_uri,
            "bpp_id": bpp_id,
            "bpp_uri": bpp_uri,
            "transaction_id": transaction_id or f"tx_lsp_{uuid.uuid4().hex[:16]}",
            "message_id": f"msg_lsp_{uuid.uuid4().hex[:16]}",
            "timestamp": now_str,
            "ttl": "PT30S",
        }

    def build_search_payload(
        self,
        origin_gps: str,
        destination_gps: str,
        commodity: str,
        weight_mt: float,
        vehicle_type: str = "MEDIUM_TRUCK",
        requires_cold_chain: bool = False,
        is_hub_route: bool = False,
        transaction_id: str | None = None,
    ) -> dict[str, Any]:
        """Assemble Beckn search intent for logistics network quotation."""
        domain = DOMAIN_LOGISTICS_P2H2P if is_hub_route else DOMAIN_LOGISTICS_P2P
        ctx = self._build_context("search", domain=domain, transaction_id=transaction_id)

        intent: dict[str, Any] = {
            "category": {"id": "P2H2P" if is_hub_route else "P2P"},
            "fulfillment": {
                "type": "Delivery",
                "start": {"location": {"gps": origin_gps}},
                "end": {"location": {"gps": destination_gps}},
            },
            "item": {
                "descriptor": {"name": commodity},
                "quantity": {
                    "measure": {
                        "unit": "metric_ton",
                        "value": str(weight_mt),
                    }
                },
                "tags": {
                    "vehicle_type": vehicle_type,
                    "cold_chain": "true" if requires_cold_chain else "false",
                    "route_type": "P2H2P" if is_hub_route else "P2P",
                },
            },
        }

        return {"context": ctx, "message": {"intent": intent}}

    async def send_search(
        self,
        target_uri: str,
        search_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Sign and dispatch Beckn search payload to a logistics BPP."""
        body_bytes = json.dumps(search_payload, default=str).encode("utf-8")
        auth_header = self.signer.sign_request(body_bytes, subscriber_id=self.bap_id)
        headers = {
            "Content-Type": "application/json",
            "Authorization": auth_header,
        }
        endpoint = f"{target_uri.rstrip('/')}/search"
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
            logger.warning("Logistics search dispatch to %s failed: %s", endpoint, exc)
            return {"status_code": 500, "error": str(exc), "ack": False}

    def normalize_on_search(self, body: dict[str, Any]) -> list[FreightQuote]:
        """Normalize an incoming Beckn on_search catalog from an LSP into FreightQuote objects."""
        context = body.get("context", {})
        message = body.get("message", {})
        catalog = message.get("catalog", {})

        bpp_id = context.get("bpp_id", "network-lsp")
        bpp_uri = context.get("bpp_uri", "")
        providers = catalog.get("bpp/providers", [])

        quotes: list[FreightQuote] = []
        now_iso = datetime.now(UTC).isoformat()

        for provider in providers:
            lsp_id = provider.get("id", bpp_id)
            lsp_name = provider.get("descriptor", {}).get("name", "Logistics Provider")
            fulfillments = provider.get("fulfillments", [])
            items = provider.get("items", [])

            # Extract TAT from fulfillment
            eta_hours = 24.0
            tracking_enabled = True
            if fulfillments:
                f = fulfillments[0]
                tat = f.get("@ondc/org/TAT") or f.get("time", {}).get("duration")
                eta_hours = parse_iso8601_duration_hours(tat)
                tracking_enabled = bool(f.get("tracking", True))

            for item in items:
                quote_id = item.get("id", f"quote_{uuid.uuid4().hex[:8]}")
                tags = item.get("tags", {})
                vehicle = tags.get("vehicle_type", "MEDIUM_TRUCK")
                cold_chain = str(tags.get("cold_chain", "false")).lower() in ("true", "1", "yes")

                price_inr = 0
                price_obj = item.get("price", {})
                if isinstance(price_obj, dict):
                    try:
                        price_inr = int(float(price_obj.get("value", 0)))
                    except Exception:
                        price_inr = 0

                terms = {
                    "cancellation_terms": item.get("cancellation_terms", "Standard 10% fee if cancelled post-dispatch"),
                    "insurance_covered": tags.get("insurance", True),
                    "sla_tat": f"PT{int(eta_hours)}H",
                }

                quotes.append(
                    FreightQuote(
                        quote_id=quote_id,
                        lsp_id=lsp_id,
                        lsp_name=lsp_name,
                        lsp_uri=bpp_uri,
                        price=price_inr,
                        eta_hours=eta_hours,
                        vehicle=vehicle,
                        cold_chain=cold_chain,
                        terms=terms,
                        validity=now_iso,
                        source="network",
                        is_committed_offer=True,
                        tracking_enabled=tracking_enabled,
                        category=context.get("domain", DOMAIN_LOGISTICS_P2P),
                        created_at=now_iso,
                    )
                )

        return quotes

    async def select(
        self,
        lsp_uri: str,
        quote_id: str,
        transaction_id: str,
        provider_id: str | None = None,
    ) -> dict[str, Any]:
        """Send Beckn select to chosen LSP BPP."""
        ctx = self._build_context("select", transaction_id=transaction_id, bpp_uri=lsp_uri)
        payload = {
            "context": ctx,
            "message": {
                "order": {
                    "provider": {"id": provider_id} if provider_id else None,
                    "items": [{"id": quote_id}],
                }
            },
        }
        return await self._dispatch(lsp_uri, "select", payload)

    async def init(
        self,
        lsp_uri: str,
        quote_id: str,
        transaction_id: str,
        pickup_gps: str,
        drop_gps: str,
        pickup_address: str,
        drop_address: str,
        contact_phone: str,
        billing_name: str,
    ) -> dict[str, Any]:
        """Send Beckn init with pickup/drop locations and contact info."""
        ctx = self._build_context("init", transaction_id=transaction_id, bpp_uri=lsp_uri)
        payload = {
            "context": ctx,
            "message": {
                "order": {
                    "items": [{"id": quote_id}],
                    "billing": {"name": billing_name, "phone": contact_phone},
                    "fulfillments": [
                        {
                            "type": "Delivery",
                            "start": {
                                "location": {"gps": pickup_gps, "address": {"street_address": pickup_address}},
                                "contact": {"phone": contact_phone},
                            },
                            "end": {
                                "location": {"gps": drop_gps, "address": {"street_address": drop_address}},
                                "contact": {"phone": contact_phone},
                            },
                        }
                    ],
                }
            },
        }
        return await self._dispatch(lsp_uri, "init", payload)

    async def confirm(
        self,
        lsp_uri: str,
        transaction_id: str,
        order_id: str,
    ) -> dict[str, Any]:
        """Send Beckn confirm to book logistics shipment."""
        ctx = self._build_context("confirm", transaction_id=transaction_id, bpp_uri=lsp_uri)
        payload = {
            "context": ctx,
            "message": {
                "order": {
                    "id": order_id,
                    "payment": {"status": "PAID", "type": "ESCROW"},
                }
            },
        }
        return await self._dispatch(lsp_uri, "confirm", payload)

    async def _dispatch(
        self,
        target_uri: str,
        action: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Sign and dispatch outbound HTTP POST."""
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
            logger.warning("Logistics %s to %s failed: %s", action, endpoint, exc)
            return {"status_code": 500, "error": str(exc), "ack": False}

    async def persist_shipment(
        self,
        session: AsyncSession,
        transaction_id: str,
        quote: FreightQuote,
        pickup_gps: str,
        drop_gps: str,
        order_id: str | None = None,
        trade_contract_id: int | None = None,
        contract_code: str | None = None,
        pickup_window_hours: float = 24.0,
    ) -> Shipment:
        """Persist or update shipment reference in database."""
        stmt = select(Shipment).where(Shipment.transaction_id == transaction_id)
        existing = (await session.scalars(stmt)).first()

        now = datetime.now(UTC)
        pickup_end = now + timedelta(hours=pickup_window_hours)
        eta_delivery = now + timedelta(hours=quote.eta_hours)

        if existing is None:
            shipment = Shipment(
                shipment_id=f"SHP-{uuid.uuid4().hex[:12].upper()}",
                transaction_id=transaction_id,
                order_id=order_id or transaction_id,
                trade_contract_id=trade_contract_id,
                contract_code=contract_code,
                lsp_id=quote.lsp_id,
                lsp_name=quote.lsp_name,
                lsp_uri=quote.lsp_uri,
                quote_id=quote.quote_id,
                source=quote.source,
                state="ASSIGNED",
                pickup_gps=pickup_gps,
                drop_gps=drop_gps,
                pickup_window_start=now,
                pickup_window_end=pickup_end,
                eta_delivery_at=eta_delivery,
                vehicle_type=quote.vehicle,
                cold_chain=quote.cold_chain,
                freight_charge_inr=quote.price,
                sla_status="ON_TIME",
                raw_details=quote.to_dict(),
                created_at=now,
                updated_at=now,
            )
            session.add(shipment)
            await session.commit()
            return shipment

        existing.lsp_id = quote.lsp_id
        existing.lsp_name = quote.lsp_name
        existing.lsp_uri = quote.lsp_uri
        existing.quote_id = quote.quote_id
        existing.freight_charge_inr = quote.price
        existing.vehicle_type = quote.vehicle
        existing.cold_chain = quote.cold_chain
        existing.eta_delivery_at = eta_delivery
        existing.raw_details = quote.to_dict()
        existing.updated_at = now
        await session.commit()
        return existing
