from decimal import Decimal

import httpx

from app.common.http_client import SafeAsyncClient
from app.errors import AppError


class EnamError(Exception):
    """The market registry could not register the lot."""


class EnamClient:
    def __init__(
        self,
        base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
        allow_private: bool | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._transport = transport
        self._allow_private = allow_private if allow_private is not None else (transport is not None)

    async def open_gate(
        self,
        *,
        lot_code: str,
        farmer_id: str,
        commodity: str,
        quantity_mt: Decimal,
        grade: str,
        mandi: str,
    ) -> str:
        body = await self._post(
            "/gate-entries",
            {
                "lot_code": lot_code,
                "farmer_id": farmer_id,
                "commodity": commodity,
                "quantity_mt": str(quantity_mt),
                "grade": grade,
                "mandi": mandi,
            },
        )
        gate_id = body.get("gate_id")
        if not isinstance(gate_id, str) or not gate_id.strip():
            raise EnamError("market registry did not return a gate id")
        return gate_id.strip()

    async def create_lot(
        self,
        *,
        gate_id: str,
        lot_code: str,
        commodity: str,
        quantity_mt: Decimal,
        grade: str,
        variety: str,
    ) -> str:
        body = await self._post(
            "/lots",
            {
                "gate_id": gate_id,
                "lot_code": lot_code,
                "commodity": commodity,
                "quantity_mt": str(quantity_mt),
                "grade": grade,
                "variety": variety,
            },
        )
        lot_id = body.get("lot_id")
        if not isinstance(lot_id, str) or not lot_id.strip():
            raise EnamError("market registry did not return a lot id")
        return lot_id.strip()

    async def issue_receipt(
        self,
        *,
        enam_lot_id: str,
        lot_code: str,
        commodity: str,
        quantity_mt: Decimal,
        grade: str,
        warehouse_id: str,
    ) -> str:
        body = await self._post(
            "/warehouse-receipts",
            {
                "enam_lot_id": enam_lot_id,
                "lot_code": lot_code,
                "commodity": commodity,
                "quantity_mt": str(quantity_mt),
                "grade": grade,
                "warehouse_id": warehouse_id,
            },
        )
        receipt_id = body.get("receipt_id")
        if not isinstance(receipt_id, str) or not receipt_id.strip():
            raise EnamError("market registry did not return a receipt id")
        return receipt_id.strip()

    async def _post(self, path: str, payload: dict) -> dict:
        try:
            async with SafeAsyncClient(
                transport=self._transport,
                allow_private=self._allow_private,
            ) as client:
                response = await client.post(f"{self.base_url}{path}", json=payload)
        except (httpx.HTTPError, AppError) as exc:
            raise EnamError("market registry request failed") from exc
        if response.status_code >= 400:
            raise EnamError(f"market registry returned {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise EnamError("market registry returned invalid json") from exc
        if not isinstance(body, dict):
            raise EnamError("market registry returned an unexpected payload")
        return body
