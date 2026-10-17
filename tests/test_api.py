from fastapi.testclient import TestClient

from backend.main import app


class _Down:
    dim = 1024

    def ping(self) -> bool:
        return False


def test_health_endpoint_reports_degraded_dependencies():
    with TestClient(app) as client:
        app.state.store = _Down()
        app.state.embedder = _Down()
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["qdrant"] is False and body["ollama"] is False
    assert isinstance(body["manifest_records"], int)


def test_sources_endpoint_lists_registry_with_exclusions():
    with TestClient(app) as client:
        resp = client.get("/sources")
    assert resp.status_code == 200
    sources = resp.json()["sources"]
    assert any(s["status"] == "excluded" and s["exclusion_reason"] for s in sources)


def test_retrieve_validates_input():
    with TestClient(app) as client:
        assert client.post("/retrieve", json={"query": "x"}).status_code == 422
        assert client.post("/retrieve", json={"query": "valid query", "strategy": "bogus"}).status_code == 422
