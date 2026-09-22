from datetime import UTC, datetime

from fastapi.responses import JSONResponse

from app.consent.repository import ConsentRepository
from app.consent.signing import authorize_profile_fetch
from app.ondc.callback import BecknCallback, CallbackError
from app.ondc.catalog import ack, context_error, nack, response_context
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
        order = _order(body.get("message"))
        if isinstance(order, str):
            return JSONResponse(status_code=400, content=nack(reply_context, order))
        item, provider_id = order
        lot = await self.lots.get(str(item.get("id", "")).strip())
        unavailable = await self._unavailable(lot, provider_id)
        if unavailable is not None or lot is None or lot.assay is None:
            return JSONResponse(status_code=400, content=nack(reply_context, unavailable or "item is not available"))
        quantity = selected_quantity(item, lot.quantity_mt)
        if isinstance(quantity, str):
            return JSONResponse(status_code=400, content=nack(reply_context, quantity))
        series = await self.prices.daily_modal_prices(PriceFilter(commodity=lot.commodity))
        if not series:
            return JSONResponse(status_code=400, content=nack(reply_context, "no price for this commodity"))
        quote = build_quote(quantity, series[-1][1])
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
                }
            },
        }
        try:
            await self.callback.send(str(context["bap_uri"]), "on_select", on_select)
        except CallbackError:
            return JSONResponse(status_code=400, content=nack(reply_context, "on_select callback failed"))
        return JSONResponse(status_code=200, content=ack(reply_context))

    async def _unavailable(self, lot, provider_id: str | None) -> str | None:
        if lot is None or lot.assay is None or not lot.enam_lot_id:
            return "item is not available"
        if provider_id is not None and provider_id != lot.farmer_id:
            return "provider does not match the item"
        farmer = await self.farmers.get(lot.farmer_id)
        artifact = await self.consents.get(lot.consent_artifact_id)
        if farmer is None or farmer.consent_artifact_id != lot.consent_artifact_id:
            return "item is not available"
        record = None if artifact is None else ConsentRepository.record(artifact)
        if authorize_profile_fetch(record, lot.farmer_id, datetime.now(UTC)) is not None:
            return "item is not available"
        return None


def _order(message: object) -> tuple[dict, str | None] | str:
    if not isinstance(message, dict):
        return "one item is required"
    order = message.get("order")
    if not isinstance(order, dict):
        return "one item is required"
    items = order.get("items")
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        return "one item is required"
    if not str(items[0].get("id", "")).strip():
        return "one item is required"
    provider = order.get("provider")
    provider_id = None
    if isinstance(provider, dict) and str(provider.get("id", "")).strip():
        provider_id = str(provider["id"]).strip()
    return items[0], provider_id
