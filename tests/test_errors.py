from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.api.exception_handlers import json_pointer
from app.config import Settings
from app.errors import AppError
from app.main import create_app


def test_json_pointer_escapes_reserved_characters() -> None:
    assert json_pointer(("body", "a/b", "c~d")) == "/body/a~1b/c~0d"
    assert json_pointer(()) == "/"


def test_app_error_uses_error_document(settings: Settings) -> None:
    application = create_app(settings)

    @application.get("/conflict")
    async def conflict() -> None:
        raise AppError(409, "Conflict", "lot already exists")

    with _client_for(application) as client:
        response = client.get("/conflict")

    assert response.status_code == 409
    assert response.json() == {
        "errors": [
            {"status": "409", "title": "Conflict", "detail": "lot already exists"}
        ]
    }


def test_http_exception_uses_error_document(settings: Settings) -> None:
    application = create_app(settings)

    @application.get("/missing")
    async def missing() -> None:
        raise HTTPException(status_code=404, detail="Farmer not found")

    with _client_for(application) as client:
        response = client.get("/missing")

    assert response.status_code == 404
    assert response.json() == {"errors": [{"status": "404", "title": "Farmer not found"}]}


def test_validation_error_points_at_the_field(settings: Settings) -> None:
    application = create_app(settings)

    class Payload(BaseModel):
        commodity: str

    @application.post("/lots")
    async def create_lot(payload: Payload) -> dict:
        return {"commodity": payload.commodity}

    with _client_for(application) as client:
        response = client.post("/lots", json={})

    assert response.status_code == 422
    error = response.json()["errors"][0]
    assert error["status"] == "422"
    assert error["title"] == "Invalid request"
    assert error["source"]["pointer"] == "/body/commodity"


def test_unhandled_error_hides_internal_detail(settings: Settings) -> None:
    application = create_app(settings)

    @application.get("/explode")
    async def explode() -> None:
        raise RuntimeError("postgres password=super-secret")

    with _client_for(application) as client:
        response = client.get("/explode")

    assert response.status_code == 500
    assert response.json() == {"errors": [{"status": "500", "title": "Internal server error"}]}
    assert "super-secret" not in response.text


def test_unknown_route_uses_error_document(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json()["errors"][0]["status"] == "404"


def _client_for(application: FastAPI) -> TestClient:
    return TestClient(application, raise_server_exceptions=False)
