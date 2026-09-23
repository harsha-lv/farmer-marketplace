from fastapi.responses import JSONResponse

from app.ondc.callback import BecknCallback, CallbackError
from app.ondc.catalog import ack, context_error, nack, response_context


class CancelService:
    def __init__(
        self,
        lots,
        contracts,
        callback: BecknCallback,
        *,
        bpp_id: str,
        bpp_uri: str,
    ) -> None:
        self.lots = lots
        self.contracts = contracts
        self.callback = callback
        self.bpp_id = bpp_id
        self.bpp_uri = bpp_uri

    async def cancel(self, body: object) -> JSONResponse:
        context = body.get("context") if isinstance(body, dict) else None
        error = context_error(context, action="cancel")
        reply_context = response_context(
            context if isinstance(context, dict) else {},
            action="cancel",
            bpp_id=self.bpp_id,
            bpp_uri=self.bpp_uri,
        )
        if error is not None or not isinstance(context, dict) or not isinstance(body, dict):
            return JSONResponse(status_code=400, content=nack(reply_context, error or "context is required"))

        transaction_id = str(context.get("transaction_id", "")).strip()
        message = body.get("message")
        cancellation_reason = "Buyer request"
        if isinstance(message, dict):
            reason_id = message.get("cancellation_reason_id")
            if reason_id:
                cancellation_reason = f"Reason code: {reason_id}"

        if not transaction_id:
            return JSONResponse(status_code=400, content=nack(reply_context, "transaction_id is required"))

        contract = await self.contracts.get_by_transaction(transaction_id)
        if contract is None:
            return JSONResponse(status_code=400, content=nack(reply_context, "contract not found"))

        if contract.status == "settled":
            return JSONResponse(status_code=400, content=nack(reply_context, "cannot cancel settled order"))

        if contract.status != "cancelled":
            if contract.status == "confirmed":
                lot = await self.lots.get(contract.lot_code)
                if lot is not None:
                    await self.lots.restore_quantity(lot, contract.quantity_mt)
            await self.contracts.cancel(contract)
            await self.contracts.session.commit()

        order_id = f"ORD-{contract.transaction_id}"[:64]
        on_cancel = {
            "context": response_context(context, action="on_cancel", bpp_id=self.bpp_id, bpp_uri=self.bpp_uri),
            "message": {
                "order": {
                    "id": order_id,
                    "state": "Cancelled",
                    "cancellation": {"reason": {"descriptor": {"code": cancellation_reason}}},
                    "tags": [
                        {
                            "code": "tlc",
                            "list": [
                                {"code": "id", "value": contract.contract_code},
                                {"code": "status", "value": "cancelled"},
                            ],
                        }
                    ],
                }
            },
        }

        try:
            await self.callback.send(str(context["bap_uri"]), "on_cancel", on_cancel)
        except CallbackError:
            return JSONResponse(status_code=400, content=nack(reply_context, "on_cancel callback failed"))
        return JSONResponse(status_code=200, content=ack(reply_context))
