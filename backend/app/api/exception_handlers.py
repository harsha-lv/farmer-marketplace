import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.utils import is_body_allowed_for_status_code
from starlette.exceptions import HTTPException
from starlette.responses import Response

from app.errors import AppError, error_document

logger = logging.getLogger(__name__)


def json_pointer(location: tuple) -> str:
    parts = [str(part).replace("~", "~0").replace("/", "~1") for part in location]
    return "/" + "/".join(parts) if parts else "/"


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_document(exc.status_code, exc.title, exc.detail),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> Response:
        if not is_body_allowed_for_status_code(exc.status_code):
            return Response(status_code=exc.status_code, headers=exc.headers)
        title = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_document(exc.status_code, title),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = []
        for err in exc.errors():
            errors.append(
                error_document(
                    422,
                    "Invalid request",
                    str(err.get("msg", "Invalid value")),
                    json_pointer(tuple(err.get("loc", ()))),
                )["errors"][0]
            )
        return JSONResponse(status_code=422, content={"errors": errors})

    @app.exception_handler(Exception)
    async def unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error: %s", exc.__class__.__name__)
        return JSONResponse(
            status_code=500,
            content=error_document(500, "Internal server error"),
        )
