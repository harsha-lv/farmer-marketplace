from fastapi.responses import JSONResponse

from app.ondc.callback import BecknCallback, CallbackError
from app.ondc.catalog import ack, context_error, nack, response_context
from app.ondc.order import parse_order, unavailable_reason
from app.ondc.quote import build_quote, selected_quantity
from app.prices.schemas import PriceFilter


class SelectService:
    def __init__(self, lots, farmers, consents, prices, callback: BecknCallback, *, bpp_id: str, bpp_uri: str) -> None:
        self.lots = lots
        self.farmers = farmers
        self.consents = consents
        self.prices = prices
        self.callback = callback
        self.bpp_id = bpp_id
        self.bpp_uri = bpp_uri

    async def select(self, body: object) -> JSONResponse:
        context = body.get("context") if isinstance(body, dict) else None
        error = context_error(context, action="select")
        reply_context = response_context(
            context if isinstance(context, dict) else {},
            action="select",
            bpp_id=self.bpp_id,
            bpp_uri=self.bpp_uri,
        )
        if error is not None or not isinstance(context, dict) or not isinstance(body, dict):
            return JSONResponse(status_code=400, content=nack(reply_context, error or "context is required"))
        order = parse_order(body.get("message"))
        if isinstance(order, str):
            return JSONResponse(status_code=400, content=nack(reply_context, order))
        item, provider_id = order
        lot = await self.lots.get(str(item.get("id", "")).strip())
        unavailable = await unavailable_reason(lot, provider_id, self.farmers, self.consents)
        if unavailable is not None or lot is None or lot.assay is None:
            return JSONResponse(status_code=400, content=nack(reply_context, unavailable or "item is not available"))
        quantity = selected_quantity(item, lot.quantity_mt)
        if isinstance(quantity, str):
            return JSONResponse(status_code=400, content=nack(reply_context, quantity))
        series = await self.prices.daily_modal_prices(PriceFilter(commodity=lot.commodity))
        if not series:
            return JSONResponse(status_code=400, content=nack(reply_context, "no price for this commodity"))
        # Extract delivery locations from buyer request
        origin_lat, origin_lon = 18.5204, 73.8567  # Default APMC mandi origin
        dest_lat, dest_lon = 19.0760, 72.8777     # Default delivery destination
        requires_cold_chain = False

        msg_order = body.get("message", {}).get("order", {})
        fulfillments_req = msg_order.get("fulfillments") or [msg_order.get("fulfillment")] if msg_order.get("fulfillment") else []
        if fulfillments_req and isinstance(fulfillments_req[0], dict):
            end_gps = fulfillments_req[0].get("end", {}).get("location", {}).get("gps")
            if end_gps and isinstance(end_gps, str) and "," in end_gps:
                try:
                    parts = end_gps.split(",")
                    dest_lat, dest_lon = float(parts[0].strip()), float(parts[1].strip())
                except Exception:
                    pass

        # Check item cold chain tags
        tags = item.get("tags", {})
        if isinstance(tags, dict):
            requires_cold_chain = str(tags.get("cold_chain", "false")).lower() in ("true", "1", "yes")

        # Aggregate internal and network logistics quotes
        from app.logistics.quote_aggregator import aggregate_freight_quotes
        ranked_freight = aggregate_freight_quotes(
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            destination_lat=dest_lat,
            destination_lon=dest_lon,
            quantity_quintals=float(quantity * 10),
            requires_cold_chain=requires_cold_chain,
        )

        quote = build_quote(quantity, series[-1][1], freight_quotes=ranked_freight)

        fulfillment_options = [
            {
                "id": f.quote_id,
                "type": "Delivery",
                "tracking": f.tracking_enabled,
                "@ondc/org/provider_id": f.lsp_id,
                "@ondc/org/provider_name": f.lsp_name,
                "@ondc/org/category": f.source,
                "@ondc/org/is_committed": f.is_committed_offer,
                "@ondc/org/TAT": f"PT{int(f.eta_hours)}H",
                "quote": {
                    "price": {"currency": "INR", "value": str(f.price_inr)},
                    "source": f.source,
                    "is_committed_offer": f.is_committed_offer,
                },
            }
            for f in ranked_freight
        ]

        on_select = {
            "context": response_context(context, action="on_select", bpp_id=self.bpp_id, bpp_uri=self.bpp_uri),
            "message": {
                "order": {
                    "provider": {"id": lot.farmer_id},
                    "items": [
                        {
                            "id": lot.lot_code,
                            "quantity": {"measure": {"unit": "metric_ton", "value": str(quantity)}},
                        }
                    ],
                    "quote": quote,
                    "fulfillments": fulfillment_options,
                }
            },
        }
        try:
            await self.callback.send(str(context["bap_uri"]), "on_select", on_select)
        except CallbackError:
            return JSONResponse(status_code=400, content=nack(reply_context, "on_select callback failed"))
        return JSONResponse(status_code=200, content=ack(reply_context))
