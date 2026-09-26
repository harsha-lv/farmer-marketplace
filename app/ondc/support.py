from fastapi.responses import JSONResponse

from app.ondc.callback import BecknCallback, CallbackError
from app.ondc.catalog import ack, context_error, nack, response_context
from app.ondc.igm import IgmService


class SupportService:
    def __init__(
        self,
        contracts,
        callback: BecknCallback,
        *,
        bpp_id: str,
        bpp_uri: str,
        support_phone: str = "+911800123456",
        support_email: str = "grievance@market.local",
    ) -> None:
        self.contracts = contracts
        self.callback = callback
        self.bpp_id = bpp_id
        self.bpp_uri = bpp_uri
        self.support_phone = support_phone
        self.support_email = support_email

    async def support(self, body: object) -> JSONResponse:
        context = body.get("context") if isinstance(body, dict) else None
        error = context_error(context, action="support")
        reply_context = response_context(
            context if isinstance(context, dict) else {},
            action="support",
            bpp_id=self.bpp_id,
            bpp_uri=self.bpp_uri,
        )
        if error is not None or not isinstance(context, dict) or not isinstance(body, dict):
            return JSONResponse(status_code=400, content=nack(reply_context, error or "context is required"))

        transaction_id = str(context.get("transaction_id", "")).strip()
        message = body.get("message")
        if not transaction_id and isinstance(message, dict):
            ref_id = str(message.get("ref_id", "")).strip()
            if ref_id.startswith("ORD-"):
                transaction_id = ref_id[4:]
            elif ref_id:
                transaction_id = ref_id

        if not transaction_id:
            return JSONResponse(status_code=400, content=nack(reply_context, "transaction_id is required"))

        contract = await self.contracts.get_by_transaction(transaction_id)
        if contract is None:
            return JSONResponse(status_code=400, content=nack(reply_context, "contract not found"))

        # Extract issue info if provided
        issue_data = message.get("issue") if isinstance(message, dict) and isinstance(message.get("issue"), dict) else {}
        category = issue_data.get("category", "QUALITY")
        sub_category = issue_data.get("sub_category", "MOISTURE_EXCESS")
        description = issue_data.get("description", "Quality or fulfillment grievance")
        complainant_info = issue_data.get(
            "complainant_info",
            {"person": {"name": contract.buyer_name, "phone": contract.buyer_phone}},
        )
        respondent_info = issue_data.get(
            "respondent_info",
            {"type": "BPP", "organization": {"id": self.bpp_id, "name": "Seller Desk"}},
        )

        igm_service = IgmService(self.contracts.session)
        ticket = await igm_service.create_ticket(
            transaction_id=contract.transaction_id,
            category=category,
            sub_category=sub_category,
            description=description,
            complainant_info=complainant_info,
            respondent_info=respondent_info,
            ticket_id=str(issue_data.get("id")) if issue_data.get("id") else None,
        )

        on_support = {
            "context": response_context(context, action="on_support", bpp_id=self.bpp_id, bpp_uri=self.bpp_uri),
            "message": {
                "phone": self.support_phone,
                "email": self.support_email,
                "uri": f"{self.bpp_uri}/support/{ticket.ticket_id}",
                "issue": {
                    "id": ticket.ticket_id,
                    "category": ticket.category,
                    "sub_category": ticket.sub_category,
                    "description": ticket.description,
                    "status": ticket.status,
                    "expected_response_time": ticket.expected_response_time,
                    "complainant_info": ticket.complainant_info,
                    "respondent_info": ticket.respondent_info,
                },
                "tags": [
                    {
                        "code": "igm_ticket",
                        "list": [
                            {"code": "id", "value": ticket.ticket_id},
                            {"code": "status", "value": ticket.status},
                            {"code": "escalation_level", "value": f"Level {ticket.escalation_level} - FPO Nodal Officer"},
                            {"code": "resolution_sla_hours", "value": "48"},
                            {"code": "ref_transaction", "value": contract.transaction_id},
                            {"code": "contract_code", "value": contract.contract_code},
                            {"code": "settlement_paused", "value": str(ticket.settlement_paused)},
                        ],
                    }
                ],
            },
        }

        try:
            await self.callback.send(str(context["bap_uri"]), "on_support", on_support)
        except CallbackError:
            return JSONResponse(status_code=400, content=nack(reply_context, "on_support callback failed"))
        return JSONResponse(status_code=200, content=ack(reply_context))
