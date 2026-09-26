"""BAP (Buyer App) inbound callback service, quote comparison, and unified contract tracking."""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.ondc.models import BapQuote, RatingRecord
from app.ondc.schemas import (
    build_beckn_ack,
)
from app.trades.models import TradeContract

logger = logging.getLogger("app.ondc.bap.service")


class BapService:
    """Service handling incoming on_* Beckn callbacks on the Buyer App side."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.bap_id = getattr(self.settings, "ondc_bap_id", "buyer.market.local")

    async def handle_on_search(self, body: dict[str, Any]) -> dict[str, Any]:
        """Process on_search catalog broadcast from a BPP and store quotes for comparison."""
        context = body.get("context", {})
        message = body.get("message", {})
        catalog = message.get("catalog", {})

        transaction_id = context.get("transaction_id", "")
        message_id = context.get("message_id", "")
        bpp_id = context.get("bpp_id", "")
        bpp_uri = context.get("bpp_uri", "")

        providers = catalog.get("bpp/providers", [])
        for provider in providers:
            items = provider.get("items", [])
            for item in items:
                lot_code = str(item.get("id", ""))
                descriptor = item.get("descriptor", {})
                commodity = descriptor.get("name", "COMMODITY")
                grade = descriptor.get("code")

                # Compute seller reputation score from RatingRecord
                rating_stmt = select(RatingRecord.score).where(RatingRecord.target_id == bpp_id)
                scores = (await self.session.scalars(rating_stmt)).all()
                avg_score = float(sum(scores) / len(scores)) if scores else 4.0

                price_inr = 0
                if "price" in item and isinstance(item["price"], dict):
                    try:
                        price_inr = int(float(item["price"].get("value", 0)))
                    except Exception:
                        price_inr = 0

                quote = BapQuote(
                    transaction_id=transaction_id,
                    message_id=message_id,
                    bpp_id=bpp_id,
                    bpp_uri=bpp_uri,
                    lot_code=lot_code,
                    commodity=commodity,
                    grade=grade,
                    quantity_mt=1.0,
                    price_inr=price_inr,
                    seller_score=round(avg_score, 2),
                    raw_quote_json=item,
                )
                self.session.add(quote)

        await self.session.commit()
        return build_beckn_ack(context)

    async def handle_on_select(self, body: dict[str, Any]) -> dict[str, Any]:
        """Process on_select quotation breakdown from BPP."""
        context = body.get("context", {})
        message = body.get("message", {})
        order = message.get("order", {})
        quote = order.get("quote", {})

        transaction_id = context.get("transaction_id", "")
        if transaction_id and quote:
            stmt = select(BapQuote).where(BapQuote.transaction_id == transaction_id)
            existing = (await self.session.scalars(stmt)).first()
            if existing and "price" in quote:
                try:
                    existing.price_inr = int(float(quote["price"].get("value", existing.price_inr)))
                    await self.session.commit()
                except Exception:
                    pass

        return build_beckn_ack(context)

    async def handle_on_init(self, body: dict[str, Any]) -> dict[str, Any]:
        """Process on_init TLC and settlement terms from BPP."""
        context = body.get("context", {})
        return build_beckn_ack(context)

    async def handle_on_confirm(self, body: dict[str, Any]) -> dict[str, Any]:
        """Process on_confirm order creation and persist into unified TradeContract table."""
        context = body.get("context", {})
        message = body.get("message", {})
        order = message.get("order", {})

        transaction_id = context.get("transaction_id", "")
        bpp_id = context.get("bpp_id", "")
        _order_id = order.get("id") or transaction_id

        # Check existing unified trade contract
        stmt = select(TradeContract).where(TradeContract.transaction_id == transaction_id)
        contract = (await self.session.scalars(stmt)).first()

        items = order.get("items", [{}])
        first_item = items[0] if items else {}
        lot_code = str(first_item.get("id", "LOT-ORDER"))

        billing = order.get("billing", {})
        fulfillments = order.get("fulfillments", [{}])
        first_fulfillment = fulfillments[0] if fulfillments else {}
        end_loc = first_fulfillment.get("end", {}).get("location", {})
        gps = end_loc.get("gps", "0.0,0.0")

        quote_val = order.get("quote", {}).get("price", {}).get("value", "0")
        try:
            price_inr = int(float(quote_val))
        except Exception:
            price_inr = 0

        now = datetime.now(UTC)
        if contract is None:
            contract = TradeContract(
                contract_code=f"CTR-{transaction_id[:12].upper()}",
                transaction_id=transaction_id,
                lot_code=lot_code,
                farmer_id="BPP_SELLER",
                buyer_name=billing.get("name", "ONDC Buyer"),
                buyer_address=billing.get("address", "Delivery Address"),
                buyer_phone=billing.get("phone"),
                delivery_gps=gps,
                quantity_mt=Decimal("1.0"),
                price_inr=price_inr,
                commission_inr=0,
                status="CONFIRMED",
                fulfillment_status="ACCEPTED",
                bap_id=self.bap_id,
                bpp_id=bpp_id,
                role="BAP",
                created_at=now,
                updated_at=now,
            )
            self.session.add(contract)
        else:
            contract.status = "CONFIRMED"
            contract.bpp_id = bpp_id
            contract.role = "BAP"
            contract.updated_at = now

        await self.session.commit()
        return build_beckn_ack(context)

    async def handle_on_status(self, body: dict[str, Any]) -> dict[str, Any]:
        """Update unified TradeContract state from on_status notification."""
        context = body.get("context", {})
        message = body.get("message", {})
        order = message.get("order", {})

        transaction_id = context.get("transaction_id", "")
        stmt = select(TradeContract).where(TradeContract.transaction_id == transaction_id)
        contract = (await self.session.scalars(stmt)).first()
        if contract:
            if "status" in order:
                contract.status = order["status"]
            if "fulfillment_status" in order:
                contract.fulfillment_status = order["fulfillment_status"]
            contract.updated_at = datetime.now(UTC)
            await self.session.commit()

        return build_beckn_ack(context)

    async def handle_on_track(self, body: dict[str, Any]) -> dict[str, Any]:
        """Update live tracking URL on TradeContract."""
        context = body.get("context", {})
        message = body.get("message", {})
        tracking = message.get("tracking", {})

        transaction_id = context.get("transaction_id", "")
        stmt = select(TradeContract).where(TradeContract.transaction_id == transaction_id)
        contract = (await self.session.scalars(stmt)).first()
        if contract and "url" in tracking:
            contract.tracking_url = tracking["url"]
            contract.updated_at = datetime.now(UTC)
            await self.session.commit()

        return build_beckn_ack(context)

    async def handle_on_cancel(self, body: dict[str, Any]) -> dict[str, Any]:
        """Mark contract cancelled on on_cancel callback."""
        context = body.get("context", {})
        transaction_id = context.get("transaction_id", "")
        stmt = select(TradeContract).where(TradeContract.transaction_id == transaction_id)
        contract = (await self.session.scalars(stmt)).first()
        if contract:
            contract.status = "CANCELLED"
            contract.updated_at = datetime.now(UTC)
            await self.session.commit()

        return build_beckn_ack(context)

    async def handle_on_update(self, body: dict[str, Any]) -> dict[str, Any]:
        return build_beckn_ack(body.get("context", {}))

    async def handle_on_support(self, body: dict[str, Any]) -> dict[str, Any]:
        return build_beckn_ack(body.get("context", {}))

    async def handle_on_rating(self, body: dict[str, Any]) -> dict[str, Any]:
        return build_beckn_ack(body.get("context", {}))

    async def get_multi_bpp_quote_comparison(self, transaction_id: str) -> list[dict[str, Any]]:
        """Retrieve and rank quotes from multiple BPPs for a given broadcast search."""
        stmt = (
            select(BapQuote)
            .where(BapQuote.transaction_id == transaction_id)
            .order_by(BapQuote.price_inr.asc(), BapQuote.seller_score.desc())
        )
        quotes = (await self.session.scalars(stmt)).all()

        results = []
        for q in quotes:
            # Composite ranking score: higher seller reputation + lower price
            ranking_score = (q.seller_score * 20.0) - (float(q.price_inr) * 0.001)
            results.append({
                "quote_id": q.id,
                "bpp_id": q.bpp_id,
                "bpp_uri": q.bpp_uri,
                "lot_code": q.lot_code,
                "commodity": q.commodity,
                "grade": q.grade,
                "price_inr": q.price_inr,
                "seller_score": q.seller_score,
                "composite_rank": round(ranking_score, 2),
                "created_at": q.created_at.isoformat(),
            })

        results.sort(key=lambda x: x["composite_rank"], reverse=True)
        return results
