import asyncio
import logging
import time
import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from app.telemetry.jetstream import NatsJetStreamEngine, get_jetstream_engine
from app.telemetry.schemas import BecknRpcRequest, BecknRpcResponse

logger = logging.getLogger("app.telemetry.rpc")

RpcHandler = Callable[[BecknRpcRequest], Coroutine[Any, Any, dict[str, Any]]]


class BecknRpcBroker:
    """
    Decentralized Beckn Request-Reply RPC Broker over NATS JetStream.
    Executes real-time asynchronous request-reply patterns for ONDC Beckn microservices.
    """

    def __init__(self, engine: NatsJetStreamEngine | None = None) -> None:
        self.engine = engine or get_jetstream_engine()
        self._handlers: dict[str, RpcHandler] = {}
        self._pending_replies: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._register_default_handlers()

    def register_handler(self, action: str, handler: RpcHandler) -> None:
        self._handlers[action.lower()] = handler
        logger.info("Registered Beckn RPC handler for action: %s", action.lower())

    def _register_default_handlers(self) -> None:
        async def _default_search_handler(req: BecknRpcRequest) -> dict[str, Any]:
            return {
                "context": {
                    "domain": req.domain,
                    "action": "on_search",
                    "version": "2.0.0",
                    "bap_id": req.bap_id,
                    "bap_uri": req.bap_uri,
                    "transaction_id": req.transaction_id,
                    "message_id": req.message_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                "message": {
                    "ack": {"status": "ACK"},
                    "catalog_available": True,
                },
            }

        async def _default_select_handler(req: BecknRpcRequest) -> dict[str, Any]:
            return {
                "context": {
                    "domain": req.domain,
                    "action": "on_select",
                    "version": "2.0.0",
                    "bap_id": req.bap_id,
                    "bap_uri": req.bap_uri,
                    "transaction_id": req.transaction_id,
                    "message_id": req.message_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                "message": {
                    "order": {"status": "SELECTED"},
                },
            }

        self._handlers["search"] = _default_search_handler
        self._handlers["select"] = _default_select_handler

    async def dispatch_request(self, request: BecknRpcRequest) -> BecknRpcResponse:
        start_time = time.perf_counter()
        action = request.action.lower()
        inbox_id = uuid.uuid4().hex[:16]
        reply_subject = f"_INBOX.{inbox_id}"
        request_subject = f"ondc.beckn.request.{action}"

        # Publish request to JetStream audit stream
        try:
            await self.engine.publish(
                subject=request_subject,
                payload={
                    "domain": request.domain,
                    "action": request.action,
                    "bap_id": request.bap_id,
                    "bap_uri": request.bap_uri,
                    "transaction_id": request.transaction_id,
                    "message_id": request.message_id,
                    "payload": request.payload,
                    "reply_to": reply_subject,
                },
                headers={"Reply-To": reply_subject, "Action": request.action},
                msg_id=request.message_id,
            )
        except Exception as exc:
            logger.warning("Failed to publish RPC request to stream: %s", exc)

        # Execute handler (local microservice or dispatched responder)
        handler = self._handlers.get(action)
        if handler is None:
            latency = (time.perf_counter() - start_time) * 1000.0
            return BecknRpcResponse(
                status="ERROR",
                action=request.action,
                transaction_id=request.transaction_id,
                message_id=request.message_id,
                reply_subject=reply_subject,
                error_message=f"No RPC handler registered for action: {request.action}",
                latency_ms=round(latency, 2),
            )

        timeout_sec = request.timeout_ms / 1000.0
        try:
            response_payload = await asyncio.wait_for(handler(request), timeout=timeout_sec)
            latency = (time.perf_counter() - start_time) * 1000.0
            return BecknRpcResponse(
                status="SUCCESS",
                action=request.action,
                transaction_id=request.transaction_id,
                message_id=request.message_id,
                reply_subject=reply_subject,
                response_payload=response_payload,
                latency_ms=round(latency, 2),
            )
        except TimeoutError:
            latency = (time.perf_counter() - start_time) * 1000.0
            return BecknRpcResponse(
                status="TIMEOUT",
                action=request.action,
                transaction_id=request.transaction_id,
                message_id=request.message_id,
                reply_subject=reply_subject,
                error_message=f"RPC request timed out after {request.timeout_ms}ms",
                latency_ms=round(latency, 2),
            )
        except Exception as exc:
            latency = (time.perf_counter() - start_time) * 1000.0
            return BecknRpcResponse(
                status="ERROR",
                action=request.action,
                transaction_id=request.transaction_id,
                message_id=request.message_id,
                reply_subject=reply_subject,
                error_message=str(exc),
                latency_ms=round(latency, 2),
            )


# Global singleton instance for platform runtime
_global_beckn_rpc_broker: BecknRpcBroker | None = None


def get_beckn_rpc_broker() -> BecknRpcBroker:
    global _global_beckn_rpc_broker
    if _global_beckn_rpc_broker is None:
        _global_beckn_rpc_broker = BecknRpcBroker()
    return _global_beckn_rpc_broker
