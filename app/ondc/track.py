from datetime import UTC, datetime
from fastapi.responses import JSONResponse

from app.ondc.callback import BecknCallback, CallbackError
from app.ondc.catalog import ack, context_error, nack, response_context


class TrackService:
    def __init__(
        self,
        contracts,
        callback: BecknCallback,
        *,
        bpp_id: str,
        bpp_uri: str,
        tracking_base_url: str = "https://track.market.local/shipments",
    ) -> None:
        self.contracts = contracts
        self.callback = callback
        self.bpp_id = bpp_id
        self.bpp_uri = bpp_uri
        self.tracking_base_url = tracking_base_url.rstrip("/")

    async def track(self, body: object) -> JSONResponse:
        context = body.get("context") if isinstance(body, dict) else None
        error = context_error(context, action="track")
        reply_context = response_context(
            context if isinstance(context, dict) else {},
            action="track",
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

        now_iso = datetime.now(UTC).isoformat()
        if contract.status == "settled":
            tracking_status = "completed"
            carrier_status = "Delivered"
            location_gps = contract.delivery_gps or "18.5204,73.8567"
        elif contract.status == "confirmed":
            tracking_status = "active"
            carrier_status = "In-Transit"
            location_gps = contract.delivery_gps or "18.5204,73.8567"
        elif contract.status == "cancelled":
            tracking_status = "inactive"
            carrier_status = "Cancelled"
            location_gps = contract.delivery_gps or "18.5204,73.8567"
        else:
            tracking_status = "inactive"
            carrier_status = "Pending-Confirmation"
            location_gps = contract.delivery_gps or "18.5204,73.8567"

        custom_carrier_status = getattr(contract, "fulfillment_status", None)
        carrier_status = custom_carrier_status or carrier_status
        tracking_url = getattr(contract, "tracking_url", None) or f"{self.tracking_base_url}/{contract.transaction_id}"
        carrier_name = getattr(contract, "carrier_name", None) or "FPO Agri-Logistics Direct"
        order_id = f"ORD-{contract.transaction_id}"[:64]

        on_track = {
            "context": response_context(context, action="on_track", bpp_id=self.bpp_id, bpp_uri=self.bpp_uri),
            "message": {
                "tracking": {
                    "url": tracking_url,
                    "status": tracking_status,
                    "location": {
                        "gps": location_gps,
                        "time": {"timestamp": now_iso},
                        "updated_at": now_iso,
                    },
                    "tags": [
                        {
                            "code": "order",
                            "list": [
                                {"code": "id", "value": order_id},
                                {"code": "status", "value": contract.status},
                            ],
                        },
                        {
                            "code": "carrier",
                            "list": [
                                {"code": "name", "value": carrier_name},
                                {"code": "status", "value": carrier_status},
                                {"code": "vehicle_type", "value": "Refrigerated Container Truck (Eicher Pro)"},
                            ],
                        },
                    ],
                }
            },
        }

        try:
            await self.callback.send(str(context["bap_uri"]), "on_track", on_track)
        except CallbackError:
            return JSONResponse(status_code=400, content=nack(reply_context, "on_track callback failed"))

        return JSONResponse(status_code=200, content=ack(reply_context))
