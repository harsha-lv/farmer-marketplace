"""Application custom exception hierarchy and centralized global exception handlers."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors import AppError

logger = logging.getLogger("app.exceptions")


# ============================================================================
# Exception Hierarchy
# ============================================================================


class AppBaseException(Exception):
    """Base application exception with status_code, detail, and error_code fields."""

    def __init__(
        self,
        detail: str = "An internal server error occurred",
        status_code: int = 500,
        error_code: str = "INTERNAL_SERVER_ERROR",
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.error_code = error_code


class NotFoundError(AppBaseException):
    """Exception raised when a requested resource is not found (404)."""

    def __init__(self, detail: str = "Resource not found", error_code: str = "NOT_FOUND") -> None:
        super().__init__(detail=detail, status_code=404, error_code=error_code)


class UnauthorizedError(AppBaseException):
    """Exception raised when authentication credentials are missing or invalid (401)."""

    def __init__(self, detail: str = "Unauthorized", error_code: str = "UNAUTHORIZED") -> None:
        super().__init__(detail=detail, status_code=401, error_code=error_code)


class ForbiddenError(AppBaseException):
    """Exception raised when access to a resource is forbidden (403)."""

    def __init__(self, detail: str = "Forbidden", error_code: str = "FORBIDDEN") -> None:
        super().__init__(detail=detail, status_code=403, error_code=error_code)


class ValidationError(AppBaseException):
    """Exception raised when domain validation rules fail (422)."""

    def __init__(self, detail: str = "Validation failed", error_code: str = "VALIDATION_ERROR") -> None:
        super().__init__(detail=detail, status_code=422, error_code=error_code)


class ConflictError(AppBaseException):
    """Exception raised when a conflict occurs with the current state of a resource (409)."""

    def __init__(self, detail: str = "Conflict", error_code: str = "CONFLICT") -> None:
        super().__init__(detail=detail, status_code=409, error_code=error_code)


class RateLimitError(AppBaseException):
    """Exception raised when rate limits are exceeded (429)."""

    def __init__(self, detail: str = "Rate limit exceeded", error_code: str = "RATE_LIMIT_EXCEEDED") -> None:
        super().__init__(detail=detail, status_code=429, error_code=error_code)


class ExternalServiceError(AppBaseException):
    """Exception raised when an external dependency or service returns an error (502)."""

    def __init__(
        self,
        detail: str = "External service error",
        error_code: str = "EXTERNAL_SERVICE_ERROR",
    ) -> None:
        super().__init__(detail=detail, status_code=502, error_code=error_code)


# ============================================================================
# Request ID Extraction
# ============================================================================


def _extract_trace_id(request: Request) -> str:
    """Extract trace_id or request_id for RFC 7807 error envelopes and logs."""
    # 1. Check OpenTelemetry trace context
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        if span is not None:
            span_ctx = span.get_span_context()
            if span_ctx and span_ctx.is_valid and span_ctx.trace_id != 0:
                return f"{span_ctx.trace_id:032x}"
    except Exception:
        pass

    # 2. Check ContextVar
    try:
        from app.logging_config import request_id_ctx
        ctx_val = request_id_ctx.get("")
        if ctx_val:
            return ctx_val
    except Exception:
        pass

    # 3. Check request state
    req_state_id = getattr(request.state, "request_id", None)
    if req_state_id:
        return str(req_state_id)

    # 4. Check headers
    for hdr in ("x-trace-id", "x-request-id", "traceparent"):
        header_val = request.headers.get(hdr)
        if header_val:
            return header_val.strip()

    import uuid
    return f"req_{uuid.uuid4().hex[:16]}"


_extract_request_id = _extract_trace_id


HTTP_STATUS_MAP: dict[int, tuple[str, str]] = {
    400: ("BAD_REQUEST", "Bad Request"),
    401: ("UNAUTHORIZED", "Unauthorized"),
    403: ("FORBIDDEN", "Forbidden"),
    404: ("NOT_FOUND", "Not Found"),
    405: ("METHOD_NOT_ALLOWED", "Method Not Allowed"),
    409: ("CONFLICT", "Conflict"),
    413: ("PAYLOAD_TOO_LARGE", "Payload Too Large"),
    415: ("UNSUPPORTED_MEDIA_TYPE", "Unsupported Media Type"),
    422: ("VALIDATION_ERROR", "Unprocessable Entity"),
    429: ("RATE_LIMIT_EXCEEDED", "Rate Limit Exceeded"),
    500: ("INTERNAL_SERVER_ERROR", "Internal Server Error"),
    502: ("BAD_GATEWAY", "Bad Gateway"),
    503: ("SERVICE_UNAVAILABLE", "Service Unavailable"),
    504: ("GATEWAY_TIMEOUT", "Gateway Timeout"),
}


def make_problem_response(
    *,
    status_code: int,
    title: str,
    detail: str,
    code: str,
    request: Request,
    headers: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """Generate an RFC 7807 application/problem+json response envelope.

    Standard Attributes:
      - type: Stable URI identifying the problem type
      - title: Short, human-readable summary of the problem type
      - status: The HTTP status code
      - detail: Human-readable explanation specific to this occurrence
      - instance: URI reference identifying the specific occurrence of the problem
      - code: Stable machine-readable error code
      - trace_id: Correlation/trace ID for cross-system debugging
      - success: false (backwards compatibility)
      - error: legacy error object (backwards compatibility)
    """
    trace_id = _extract_trace_id(request)
    instance = request.url.path
    stable_slug = code.lower().replace("_", "-")
    type_uri = f"https://api.agrimarketplace.gov.in/errors/{stable_slug}"

    content: dict[str, Any] = {
        "type": type_uri,
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
        "code": code,
        "trace_id": trace_id,
        "success": False,
        "error": {
            "code": code,
            "message": detail,
            "request_id": trace_id,
        },
    }
    if extra:
        content.update(extra)

    resp_headers = dict(headers or {})
    resp_headers["Content-Type"] = "application/problem+json"
    if trace_id:
        resp_headers["X-Request-ID"] = trace_id
        resp_headers["X-Trace-ID"] = trace_id

    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=resp_headers,
        media_type="application/problem+json",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register centralized RFC 7807 exception handlers for standard problem+json formatting."""
    from sqlalchemy.exc import SQLAlchemyError

    @app.exception_handler(AppBaseException)
    async def app_base_exception_handler(request: Request, exc: AppBaseException) -> JSONResponse:
        title = exc.error_code.replace("_", " ").title()
        return make_problem_response(
            status_code=exc.status_code,
            title=title,
            detail=exc.detail,
            code=exc.error_code,
            request=request,
        )

    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_handler(request: Request, exc: PydanticValidationError) -> JSONResponse:
        errors = []
        for err in exc.errors():
            loc = ".".join(str(part) for part in err.get("loc", []))
            errors.append({
                "loc": list(err.get("loc", [])),
                "field": loc or "body",
                "message": str(err.get("msg", "Invalid value")),
                "type": err.get("type", "validation_error"),
            })
        first_err = errors[0]["message"] if errors else "Validation failed"
        detail = f"Validation failed: {first_err}"
        return make_problem_response(
            status_code=422,
            title="Unprocessable Entity",
            detail=detail,
            code="VALIDATION_ERROR",
            request=request,
            extra={"errors": errors},
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = []
        for err in exc.errors():
            loc = ".".join(str(part) for part in err.get("loc", []))
            errors.append({
                "loc": list(err.get("loc", [])),
                "field": loc or "body",
                "message": str(err.get("msg", "Invalid value")),
                "type": err.get("type", "validation_error"),
            })
        first_err = errors[0]["message"] if errors else "Validation failed"
        loc_str = errors[0]["field"] if errors else "payload"
        detail = f"Validation failed for '{loc_str}': {first_err}"
        return make_problem_response(
            status_code=422,
            title="Unprocessable Entity",
            detail=detail,
            code="VALIDATION_ERROR",
            request=request,
            extra={"errors": errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        code, title = HTTP_STATUS_MAP.get(exc.status_code, (f"HTTP_{exc.status_code}", "HTTP Error"))
        return make_problem_response(
            status_code=exc.status_code,
            title=title,
            detail=detail,
            code=code,
            request=request,
            headers=dict(exc.headers or {}),
        )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        code = exc.title.upper().replace(" ", "_")
        return make_problem_response(
            status_code=exc.status_code,
            title=exc.title,
            detail=exc.detail or exc.title,
            code=code,
            request=request,
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        trace_id = _extract_trace_id(request)
        if isinstance(exc, IntegrityError):
            logger.warning("Database constraint integrity conflict [%s]: %s", trace_id, exc)
            return make_problem_response(
                status_code=409,
                title="Conflict",
                detail="Database constraint violation or conflicting resource state",
                code="CONFLICT",
                request=request,
            )

        # Never leak raw SQL, parameters, table names, or database internals
        logger.error("Database error executing statement [%s]: %s", trace_id, exc, exc_info=True)
        return make_problem_response(
            status_code=500,
            title="Database Error",
            detail="A database error occurred while processing the request. Please try again later.",
            code="DATABASE_ERROR",
            request=request,
        )

    @app.exception_handler(500)
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        trace_id = _extract_trace_id(request)
        # Never leak stack traces to client
        logger.exception("Unhandled application error [%s]: %s", trace_id, exc)
        return make_problem_response(
            status_code=500,
            title="Internal Server Error",
            detail="An internal server error occurred.",
            code="INTERNAL_SERVER_ERROR",
            request=request,
        )
