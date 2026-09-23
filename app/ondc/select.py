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
