from fastapi.testclient import TestClient


class _Database:
    def __init__(self, up: bool) -> None:
        self.up = up

    async def ping(self) -> bool:
        return self.up


def test_health_reports_service_metadata(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Agri-Market Intelligence Platform",
        "version": "0.1.0",
        "environment": "test",
    }


def test_ready_when_database_is_up(client: TestClient) -> None:
    client.app.state.database = _Database(up=True)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "up"}}


def test_ready_when_database_is_down(client: TestClient) -> None:
    client.app.state.database = _Database(up=False)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "checks": {"database": "down"}}


def test_openapi_document_is_version_3_1(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    document = response.json()
    assert document["openapi"] == "3.1.0"
    assert document["info"]["title"] == "Agri-Market Intelligence Platform"
    assert "/health" in document["paths"]
    assert "/ready" in document["paths"]
