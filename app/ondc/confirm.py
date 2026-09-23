from fastapi.responses import JSONResponse

from app.ondc.callback import BecknCallback, CallbackError
from app.ondc.catalog import ack, context_error, nack, response_context
from app.ondc.order import unavailable_reason


class ConfirmService:
    def __init__(
        self,
        lots,
        farmers,
        consents,
        contracts,
        callback: BecknCallback,
        *,
        bpp_id: str,
        bpp_uri: str,
    ) -> None:
        self.lots = lots
        self.farmers = farmers
        self.consents = consents
        self.contracts = contracts
        self.callback = callback
        self.bpp_id = bpp_id
        self.bpp_uri = bpp_uri

    async def confirm(self, body: object) -> JSONResponse:
        context = body.get("context") if isinstance(body, dict) else None
        error = context_error(context, action="confirm")
        reply_context = response_context(
            context if isinstance(context, dict) else {},
            action="confirm",
            bpp_id=self.bpp_id,
            bpp_uri=self.bpp_uri,
        )
        if error is not None or not isinstance(context, dict) or not isinstance(body, dict):
            return JSONResponse(status_code=400, content=nack(reply_context, error or "context is required"))

        transaction_id = str(context.get("transaction_id", "")).strip()
        if not transaction_id:
            return JSONResponse(status_code=400, content=nack(reply_context, "transaction_id is required"))

        contract = await self.contracts.get_by_transaction(transaction_id)
        if contract is None:
            return JSONResponse(status_code=400, content=nack(reply_context, "contract not found"))

        if contract.status not in ("draft", "confirmed"):
            return JSONResponse(status_code=400, content=nack(reply_context, f"contract is in {contract.status} state"))

        if contract.status == "draft":
            lot = await self.lots.get(contract.lot_code)
            unavailable = await unavailable_reason(lot, contract.farmer_id, self.farmers, self.consents)
            if unavailable is not None or lot is None:
                return JSONResponse(status_code=400, content=nack(reply_context, unavailable or "item is not available"))
            if lot.quantity_mt < contract.quantity_mt:
                return JSONResponse(status_code=400, content=nack(reply_context, "insufficient quantity available"))

            await self.lots.deduct_quantity(lot, contract.quantity_mt)
            await self.contracts.confirm(contract)
            await self.contracts.session.commit()

        item_value = contract.price_inr - contract.commission_inr
        order_id = f"ORD-{contract.transaction_id}"[:64]
        on_confirm = {
            "context": response_context(context, action="on_confirm", bpp_id=self.bpp_id, bpp_uri=self.bpp_uri),
            "message": {
                "order": {
                    "id": order_id,
                    "state": "Accepted",
                    "provider": {"id": contract.farmer_id},
                    "items": [
                        {
                            "id": contract.lot_code,
                            "quantity": {"measure": {"unit": "metric_ton", "value": str(contract.quantity_mt)}},
                        }
                    ],
                    "billing": {
                        "name": contract.buyer_name,
                        "address": contract.buyer_address,
                        "phone": contract.buyer_phone,
                    },
                    "fulfillment": {
                        "type": "Delivery",
                        "end": {"location": {"gps": contract.delivery_gps}},
                        "tracking": True,
                        "state": {"descriptor": {"code": "Order-confirmed"}},
                    },
                    "quote": {
                        "price": {"currency": "INR", "value": str(contract.price_inr)},
                        "breakup": [
                            {"title": "item", "price": {"currency": "INR", "value": str(item_value)}},
                            {"title": "delivery", "price": {"currency": "INR", "value": "0"}},
                            {"title": "commission", "price": {"currency": "INR", "value": str(contract.commission_inr)}},
                        ],
                    },
                    "payment": {"type": "ON-FULFILLMENT", "status": "PAID-TO-ESCROW"},
                    "tags": [
                        {
                            "code": "tlc",
                            "list": [
                                {"code": "id", "value": contract.contract_code},
                                {"code": "status", "value": contract.status},
                                {"code": "settlement", "value": "on delivery acceptance"},
                            ],
                        }
                    ],
                }
            },
        }

        try:
            await self.callback.send(str(context["bap_uri"]), "on_confirm", on_confirm)
        except CallbackError:
            return JSONResponse(status_code=400, content=nack(reply_context, "on_confirm callback failed"))
        return JSONResponse(status_code=200, content=ack(reply_context))
