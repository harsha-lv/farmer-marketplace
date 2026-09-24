from fastapi.responses import JSONResponse

from app.events.repository import EventRepository
from app.ondc.callback import BecknCallback, CallbackError
from app.ondc.catalog import ack, context_error, nack, response_context


class UpdateService:
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

    async def update(self, body: object) -> JSONResponse:
        context = body.get("context") if isinstance(body, dict) else None
        error = context_error(context, action="update")
        reply_context = response_context(
            context if isinstance(context, dict) else {},
            action="update",
            bpp_id=self.bpp_id,
            bpp_uri=self.bpp_uri,
        )
        if error is not None or not isinstance(context, dict) or not isinstance(body, dict):
            return JSONResponse(status_code=400, content=nack(reply_context, error or "context is required"))

        transaction_id = str(context.get("transaction_id", "")).strip()
        message = body.get("message")
        if not transaction_id and isinstance(message, dict):
            order = message.get("order")
            if isinstance(order, dict):
                order_id = str(order.get("id", "")).strip()
                if order_id.startswith("ORD-"):
                    transaction_id = order_id[4:]

        if not transaction_id:
            return JSONResponse(status_code=400, content=nack(reply_context, "transaction_id is required"))

        contract = await self.contracts.get_by_transaction(transaction_id)
        if contract is None:
            return JSONResponse(status_code=400, content=nack(reply_context, "contract not found"))

        if contract.status == "cancelled":
            return JSONResponse(status_code=400, content=nack(reply_context, "cannot update cancelled order"))

        # Parse fulfillment updates
        descriptor_code = "In-transit"
        tracking_url = None
        carrier_name = None
        if isinstance(message, dict):
            order = message.get("order", {})
            fulfillment = None
            if isinstance(order, dict):
                fulfillment = order.get("fulfillment")
            if not isinstance(fulfillment, dict):
                fulfillment = message.get("fulfillment")

            if isinstance(fulfillment, dict):
                state_dict = fulfillment.get("state")
                if isinstance(state_dict, dict):
                    desc = state_dict.get("descriptor")
                    if isinstance(desc, dict) and desc.get("code"):
                        descriptor_code = str(desc["code"])
                elif isinstance(fulfillment.get("descriptor"), dict):
                    desc = fulfillment["descriptor"]
                    if desc.get("code"):
                        descriptor_code = str(desc["code"])

                tracking_url = fulfillment.get("tracking_url")
                if not tracking_url and isinstance(fulfillment.get("tracking"), dict):
                    tracking_url = fulfillment["tracking"].get("url")

                carrier_obj = fulfillment.get("carrier") or fulfillment.get("agent")
                if isinstance(carrier_obj, dict):
                    carrier_name = carrier_obj.get("name")

        # State transition according to fulfillment status
        if descriptor_code in ("Order-delivered", "Delivered"):
            await self.contracts.settle(contract)
        elif descriptor_code in ("Disputed", "Order-disputed"):
            await self.contracts.dispute(contract)

        if hasattr(self.contracts, "update_fulfillment"):
            await self.contracts.update_fulfillment(
                contract,
                fulfillment_status=descriptor_code,
                tracking_url=tracking_url,
                carrier_name=carrier_name,
            )

        # Record outbox event if running with real ContractRepository
        if (
            type(self.contracts).__name__ == "ContractRepository"
            and type(self.contracts).__module__ == "app.trades.repository"
        ):
            await EventRepository(self.contracts.session).record_event(
                event_type="FulfillmentUpdated",
                stream_id=f"trade:{contract.transaction_id}",
                partition_key=contract.farmer_id,
                payload={
                    "transaction_id": contract.transaction_id,
                    "contract_status": contract.status,
                    "fulfillment_status": descriptor_code,
                    "tracking_url": tracking_url or getattr(contract, "tracking_url", None),
                    "carrier_name": carrier_name or getattr(contract, "carrier_name", None),
                },
            )

        if hasattr(self.contracts, "session") and hasattr(self.contracts.session, "commit"):
            await self.contracts.session.commit()

        # Build on_update payload
        state = (
            "Completed"
            if contract.status == "settled"
            else ("Accepted" if contract.status == "confirmed" else "Created")
        )
        payment_status = (
            "PAID-TO-SELLER"
            if contract.status == "settled"
            else ("PAID-TO-ESCROW" if contract.status == "confirmed" else "NOT-PAID")
        )
        item_value = contract.price_inr - contract.commission_inr
        order_id = f"ORD-{contract.transaction_id}"[:64]

        fulfillment_payload: dict = {
            "type": "Delivery",
            "end": {"location": {"gps": contract.delivery_gps}},
            "tracking": True,
            "state": {"descriptor": {"code": descriptor_code}},
        }
        if tracking_url or getattr(contract, "tracking_url", None):
            fulfillment_payload["tracking_url"] = tracking_url or getattr(contract, "tracking_url", None)

        on_update = {
            "context": response_context(context, action="on_update", bpp_id=self.bpp_id, bpp_uri=self.bpp_uri),
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
                    "fulfillment": fulfillment_payload,
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
                            ],
                        }
                    ],
                }
            },
        }

        try:
            await self.callback.send(str(context["bap_uri"]), "on_update", on_update)
        except CallbackError:
            return JSONResponse(status_code=400, content=nack(reply_context, "on_update callback failed"))

        return JSONResponse(status_code=200, content=ack(reply_context))
