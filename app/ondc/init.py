from fastapi.responses import JSONResponse

from app.ondc.callback import BecknCallback, CallbackError
from app.ondc.catalog import ack, context_error, nack, response_context
from app.ondc.contract import delivery_terms, quote_with_commission
from app.ondc.order import parse_order, unavailable_reason
from app.ondc.quote import selected_quantity
from app.ondc.tlc import TlcService
from app.prices.schemas import PriceFilter


class InitService:
    def __init__(
        self,
        lots,
        farmers,
        consents,
        prices,
        contracts,
        callback: BecknCallback,
        *,
        bpp_id: str,
        bpp_uri: str,
        commission_percent: int,
    ) -> None:
        self.lots = lots
        self.farmers = farmers
        self.consents = consents
        self.prices = prices
        self.contracts = contracts
        self.callback = callback
        self.bpp_id = bpp_id
        self.bpp_uri = bpp_uri
        self.commission_percent = commission_percent

    async def init(self, body: object) -> JSONResponse:
        context = body.get("context") if isinstance(body, dict) else None
        error = context_error(context, action="init")
        reply_context = response_context(
            context if isinstance(context, dict) else {},
            action="init",
            bpp_id=self.bpp_id,
            bpp_uri=self.bpp_uri,
        )
        if error is not None or not isinstance(context, dict) or not isinstance(body, dict):
            return JSONResponse(status_code=400, content=nack(reply_context, error or "context is required"))
        parsed = parse_order(body.get("message"))
        if isinstance(parsed, str):
            return JSONResponse(status_code=400, content=nack(reply_context, parsed))
        item, provider_id = parsed
        order = body["message"]["order"]
        terms = delivery_terms(order)
        if isinstance(terms, str):
            return JSONResponse(status_code=400, content=nack(reply_context, terms))
        lot = await self.lots.get(str(item.get("id", "")).strip())
        unavailable = await unavailable_reason(lot, provider_id, self.farmers, self.consents)
        if unavailable is not None or lot is None:
            return JSONResponse(status_code=400, content=nack(reply_context, unavailable or "item is not available"))
        quantity = selected_quantity(item, lot.quantity_mt)
        if isinstance(quantity, str):
            return JSONResponse(status_code=400, content=nack(reply_context, quantity))
        series = await self.prices.daily_modal_prices(PriceFilter(commodity=lot.commodity))
        if not series:
            return JSONResponse(status_code=400, content=nack(reply_context, "no price for this commodity"))
        quote = quote_with_commission(quantity, series[-1][1], self.commission_percent)
        contract = await self.contracts.save_draft(
            transaction_id=str(context["transaction_id"]),
            lot_code=lot.lot_code,
            farmer_id=lot.farmer_id,
            buyer_name=terms["name"],
            buyer_address=terms["address"],
            buyer_phone=terms["phone"],
            delivery_gps=terms["gps"],
            quantity_mt=quantity,
            price_inr=int(quote["price"]["value"]),
            commission_inr=int(quote["breakup"][2]["price"]["value"]),
        )
        # Extract chosen LSP from order fulfillments
        fulfillment = order.get("fulfillment") or (order.get("fulfillments")[0] if order.get("fulfillments") else {})
        chosen_lsp_name = None
        chosen_lsp_id = None
        if isinstance(fulfillment, dict):
            chosen_lsp_name = (
                fulfillment.get("@ondc/org/provider_name")
                or fulfillment.get("carrier_name")
                or fulfillment.get("provider_name")
            )
            chosen_lsp_id = (
                fulfillment.get("@ondc/org/provider_id")
                or fulfillment.get("provider_id")
                or fulfillment.get("id")
            )
            if chosen_lsp_name or chosen_lsp_id:
                contract.carrier_name = chosen_lsp_name or chosen_lsp_id

        grade = lot.assay.grade if lot.assay else "Standard"
        tlc_service = TlcService(self.contracts.session)
        tlc_record = await tlc_service.generate_and_persist(
            transaction_id=str(context["transaction_id"]),
            contract_code=contract.contract_code,
            commodity=lot.commodity,
            grade=grade,
            quantity_mt=quantity,
            price_per_mt=int(int(quote["price"]["value"]) / quantity) if quantity > 0 else int(quote["price"]["value"]),
            commission_percent=self.commission_percent,
            buyer_name=terms["name"],
            farmer_id=lot.farmer_id,
            delivery_location=str(terms.get("gps", terms.get("address", ""))),
            chosen_lsp={"lsp_id": chosen_lsp_id, "lsp_name": chosen_lsp_name} if (chosen_lsp_id or chosen_lsp_name) else None,
        )
        contract.tlc_hash = tlc_record.tlc_hash
        await self.contracts.session.commit()
        on_init = {
            "context": response_context(context, action="on_init", bpp_id=self.bpp_id, bpp_uri=self.bpp_uri),
            "message": {
                "order": {
                    "provider": {"id": lot.farmer_id},
                    "items": [
                        {
                            "id": lot.lot_code,
                            "quantity": {"measure": {"unit": "metric_ton", "value": str(quantity)}},
                        }
                    ],
                    "billing": {"name": terms["name"], "address": terms["address"]},
                    "fulfillment": {"type": "Delivery", "end": {"location": {"gps": terms["gps"]}}},
                    "quote": quote,
                    "payment": {"type": "ON-FULFILLMENT", "status": "NOT-PAID"},
                    "tags": [
                        {
                            "code": "tlc",
                            "list": [
                                {"code": "id", "value": contract.contract_code},
                                {"code": "status", "value": contract.status},
                                {"code": "settlement", "value": "Friday + 2 Banking Days"},
                                {"code": "tlc_hash", "value": tlc_record.tlc_hash},
                                {"code": "signature", "value": tlc_record.signature},
                            ],
                        }
                    ],
                }
            },
        }
        try:
            await self.callback.send(str(context["bap_uri"]), "on_init", on_init)
        except CallbackError:
            return JSONResponse(status_code=400, content=nack(reply_context, "on_init callback failed"))
        return JSONResponse(status_code=200, content=ack(reply_context))
