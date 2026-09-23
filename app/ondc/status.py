from fastapi.responses import JSONResponse

from app.ondc.callback import BecknCallback, CallbackError
from app.ondc.catalog import ack, context_error, nack, response_context


class StatusService:
    def __init__(
        self,
        contracts,
        callback: BecknCallback,
        *,
        bpp_id: str,
        bpp_uri: str,
    ) -> None:
        self.contracts = contracts
        self.callback = callback
        self.bpp_id = bpp_id
        self.bpp_uri = bpp_uri

    async def status(self, body: object) -> JSONResponse:
        context = body.get("context") if isinstance(body, dict) else None
        error = context_error(context, action="status")
        reply_context = response_context(
            context if isinstance(context, dict) else {},
            action="status",
            bpp_id=self.bpp_id,
            bpp_uri=self.bpp_uri,
        )
        if error is not None or not isinstance(context, dict) or not isinstance(body, dict):
            return JSONResponse(status_code=400, content=nack(reply_context, error or "context is required"))

        transaction_id = str(context.get("transaction_id", "")).strip()
        message = body.get("message")
        if not transaction_id and isinstance(message, dict):
            order_id = str(message.get("order_id", "")).strip()
            if order_id.startswith("ORD-"):
                transaction_id = order_id[4:]

        if not transaction_id:
            return JSONResponse(status_code=400, content=nack(reply_context, "transaction_id is required"))

        contract = await self.contracts.get_by_transaction(transaction_id)
        if contract is None:
            return JSONResponse(status_code=400, content=nack(reply_context, "contract not found"))

        state = (
            "Completed"
            if contract.status == "settled"
            else ("Accepted" if contract.status == "confirmed" else "Created")
        )
        fulfillment_state = (
            "Order-delivered"
            if contract.status == "settled"
            else ("Order-confirmed" if contract.status == "confirmed" else "Pending")
        )
        payment_status = (
            "PAID-TO-SELLER"
            if contract.status == "settled"
            else ("PAID-TO-ESCROW" if contract.status == "confirmed" else "NOT-PAID")
        )
        item_value = contract.price_inr - contract.commission_inr
        order_id = f"ORD-{contract.transaction_id}"[:64]

        on_status = {
            "context": response_context(context, action="on_status", bpp_id=self.bpp_id, bpp_uri=self.bpp_uri),
            "message": {
                "order": {
                    "id": order_id,
                    "state": state,
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
                        "state": {"descriptor": {"code": fulfillment_state}},
                    },
                    "quote": {
                        "price": {"currency": "INR", "value": str(contract.price_inr)},
                        "breakup": [
                            {"title": "item", "price": {"currency": "INR", "value": str(item_value)}},
                            {"title": "delivery", "price": {"currency": "INR", "value": "0"}},
                            {"title": "commission", "price": {"currency": "INR", "value": str(contract.commission_inr)}},
                        ],
                    },
                    "payment": {"type": "ON-FULFILLMENT", "status": payment_status},
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
            await self.callback.send(str(context["bap_uri"]), "on_status", on_status)
        except CallbackError:
            return JSONResponse(status_code=400, content=nack(reply_context, "on_status callback failed"))
        return JSONResponse(status_code=200, content=ack(reply_context))
