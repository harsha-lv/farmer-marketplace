"""FastAPI router for ONDC BAP inbound callbacks and multi-BPP quote comparison."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.deps import SessionDep, SettingsDep
from app.ondc.auth.verification import verify_inbound_beckn_request
from app.ondc.bap.service import BapService
from app.ondc.schemas import build_beckn_nack
from app.ondc.shim import (
    apply_deprecation_headers,
    is_v1_request,
    translate_v1_to_v2,
    translate_v2_to_v1,
)

logger = logging.getLogger("app.api.beckn_bap")

router = APIRouter(prefix="/beckn/bap", tags=["beckn_bap"])


def get_bap_service(session: SessionDep, settings: SettingsDep) -> BapService:
    return BapService(session=session, settings=settings)


BapDep = Annotated[BapService, Depends(get_bap_service)]


async def parse_and_verify(request: Request) -> tuple[dict[str, Any] | None, bool, JSONResponse | None]:
    """Parse request body, verify signature (if auth enabled), and handle v1 translation."""
    try:
        body_bytes = await request.body()
        body = await request.json()
    except Exception:
        return None, False, JSONResponse(status_code=400, content=build_beckn_nack({}, "30000", "Invalid JSON payload"))

    is_v1 = is_v1_request(body)
    if is_v1:
        body = translate_v1_to_v2(body)

    context = body.get("context", {})
    # Verify signature if Authorization header present
    auth_header = request.headers.get("Authorization")
    if auth_header:
        valid, err = await verify_inbound_beckn_request(request, body_bytes, context=context)
        if not valid:
            logger.warning("BAP callback authentication failed: %s", err)
            return None, is_v1, JSONResponse(status_code=401, content=build_beckn_nack(context, "30001", str(err)))

    return body, is_v1, None


@router.post("/on_search")
async def on_search(request: Request, service: BapDep) -> JSONResponse:
    body, is_v1, err_resp = await parse_and_verify(request)
    if err_resp:
        return err_resp
    result = await service.handle_on_search(body)
    resp = JSONResponse(status_code=200, content=translate_v2_to_v1(result) if is_v1 else result)
    return apply_deprecation_headers(resp) if is_v1 else resp


@router.post("/on_select")
async def on_select(request: Request, service: BapDep) -> JSONResponse:
    body, is_v1, err_resp = await parse_and_verify(request)
    if err_resp:
        return err_resp
    result = await service.handle_on_select(body)
    resp = JSONResponse(status_code=200, content=translate_v2_to_v1(result) if is_v1 else result)
    return apply_deprecation_headers(resp) if is_v1 else resp


@router.post("/on_init")
async def on_init(request: Request, service: BapDep) -> JSONResponse:
    body, is_v1, err_resp = await parse_and_verify(request)
    if err_resp:
        return err_resp
    result = await service.handle_on_init(body)
    resp = JSONResponse(status_code=200, content=translate_v2_to_v1(result) if is_v1 else result)
    return apply_deprecation_headers(resp) if is_v1 else resp


@router.post("/on_confirm")
async def on_confirm(request: Request, service: BapDep) -> JSONResponse:
    body, is_v1, err_resp = await parse_and_verify(request)
    if err_resp:
        return err_resp
    result = await service.handle_on_confirm(body)
    resp = JSONResponse(status_code=200, content=translate_v2_to_v1(result) if is_v1 else result)
    return apply_deprecation_headers(resp) if is_v1 else resp


@router.post("/on_status")
async def on_status(request: Request, service: BapDep) -> JSONResponse:
    body, is_v1, err_resp = await parse_and_verify(request)
    if err_resp:
        return err_resp
    result = await service.handle_on_status(body)
    resp = JSONResponse(status_code=200, content=translate_v2_to_v1(result) if is_v1 else result)
    return apply_deprecation_headers(resp) if is_v1 else resp


@router.post("/on_track")
async def on_track(request: Request, service: BapDep) -> JSONResponse:
    body, is_v1, err_resp = await parse_and_verify(request)
    if err_resp:
        return err_resp
    result = await service.handle_on_track(body)
    resp = JSONResponse(status_code=200, content=translate_v2_to_v1(result) if is_v1 else result)
    return apply_deprecation_headers(resp) if is_v1 else resp


@router.post("/on_cancel")
async def on_cancel(request: Request, service: BapDep) -> JSONResponse:
    body, is_v1, err_resp = await parse_and_verify(request)
    if err_resp:
        return err_resp
    result = await service.handle_on_cancel(body)
    resp = JSONResponse(status_code=200, content=translate_v2_to_v1(result) if is_v1 else result)
    return apply_deprecation_headers(resp) if is_v1 else resp


@router.post("/on_update")
async def on_update(request: Request, service: BapDep) -> JSONResponse:
    body, is_v1, err_resp = await parse_and_verify(request)
    if err_resp:
        return err_resp
    result = await service.handle_on_update(body)
    resp = JSONResponse(status_code=200, content=translate_v2_to_v1(result) if is_v1 else result)
    return apply_deprecation_headers(resp) if is_v1 else resp


@router.post("/on_support")
async def on_support(request: Request, service: BapDep) -> JSONResponse:
    body, is_v1, err_resp = await parse_and_verify(request)
    if err_resp:
        return err_resp
    result = await service.handle_on_support(body)
    resp = JSONResponse(status_code=200, content=translate_v2_to_v1(result) if is_v1 else result)
    return apply_deprecation_headers(resp) if is_v1 else resp


@router.post("/on_rating")
async def on_rating(request: Request, service: BapDep) -> JSONResponse:
    body, is_v1, err_resp = await parse_and_verify(request)
    if err_resp:
        return err_resp
    result = await service.handle_on_rating(body)
    resp = JSONResponse(status_code=200, content=translate_v2_to_v1(result) if is_v1 else result)
    return apply_deprecation_headers(resp) if is_v1 else resp


@router.get("/quotes/{transaction_id}")
async def get_quotes(transaction_id: str, service: BapDep) -> dict[str, Any]:
    """API for frontend to view ranked multi-BPP quotes for a transaction."""
    quotes = await service.get_multi_bpp_quote_comparison(transaction_id)
    return {
        "transaction_id": transaction_id,
        "count": len(quotes),
        "total_quotes": len(quotes),
        "quotes": quotes,
    }
