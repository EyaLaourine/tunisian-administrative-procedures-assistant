"""API security: privileged endpoints fail closed, optional agent key, request size limit, client headers.

The FastAPI app is exercised with TestClient *without* its lifespan (no Qdrant/Ollama connection); handlers that
would need services are never reached because the security checks run first. The key values below are test
fixtures, not credentials.
"""

import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

import backend.main as main

KEY = "test-fixture-admin-key"


@pytest.fixture
def client():
    main.app.state.settings = SimpleNamespace(admin_api_key=None, agent_api_key=None, max_request_bytes=1024)
    return TestClient(main.app)  # no context manager: lifespan (service connections) is not started


@pytest.mark.parametrize("path", ["/ingestion/run", "/index/run"])
def test_privileged_endpoints_are_disabled_without_configured_key(client, path):
    r = client.post(path, headers={"X-Admin-Key": "guess"})
    assert r.status_code == 403 and "disabled" in r.json()["detail"]


@pytest.mark.parametrize("path", ["/ingestion/run", "/index/run"])
@pytest.mark.parametrize("header", [None, "wrong-key", ""])
def test_privileged_endpoints_reject_missing_or_invalid_key(client, path, header):
    main.app.state.settings.admin_api_key = KEY
    r = client.post(path, headers={"X-Admin-Key": header} if header is not None else {})
    assert r.status_code == 401 and KEY not in r.text


def test_valid_admin_key_passes_the_check():
    main.app.state.settings = SimpleNamespace(admin_api_key=KEY)
    main.require_admin(KEY)  # no exception


@pytest.mark.parametrize("path", ["/agents/route", "/agents/retrieve", "/agents/answer", "/agents/form-check",
                                  "/agents/dossier-check", "/retrieve"])
def test_agent_api_requires_key_when_configured(client, path):
    main.app.state.settings.agent_api_key = KEY
    assert client.post(path, json={}).status_code == 401
    assert client.post(path, json={}, headers={"X-Agent-Key": "wrong"}).status_code == 401
    # with the key, the request passes authentication and reaches validation (422: empty body)
    assert client.post(path, json={}, headers={"X-Agent-Key": KEY}).status_code == 422


def test_agent_api_stays_open_when_no_key_is_configured(client):
    assert client.post("/agents/route", json={}).status_code == 422  # validation, not 401


def test_oversized_request_body_is_rejected_before_parsing(client):
    r = client.post("/agents/form-check", content=b"x" * 2048, headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_bridge_sends_the_assistant_key_only_when_configured():
    from telegram_bridge.bridge import TelegramBridge
    seen = []

    def handler(request):
        if str(request.url) == "http://n8n.test/webhook/assistant":
            seen.append(request.headers.get("x-assistant-key"))
            return httpx.Response(200, json={"text": "ok", "agent": "intent_router"})
        return httpx.Response(200, json={"ok": True, "result": {}})

    for key in (None, KEY):
        bridge = TelegramBridge("123:TEST", "http://n8n.test/webhook/assistant", 1024,
                                client=httpx.Client(transport=httpx.MockTransport(handler)), webhook_key=key)
        bridge.stop.wait = lambda _: False
        bridge.handle_message({"chat": {"id": 1, "type": "private"}, "from": {"id": 1}, "text": "bonjour passeport"})
    assert seen == [None, KEY]


def test_settings_never_print_secrets():
    from backend.settings import Settings
    s = Settings(admin_api_key="a" * 20, agent_api_key="b" * 20, assistant_webhook_key="c" * 20,
                 telegram_bot_token="1:" + "d" * 30)
    text = repr(s)
    assert not any(ch * 20 in text for ch in "abcd")


def test_committed_workflows_contain_no_credentials():
    from pathlib import Path
    for path in Path("workflows").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        nodes = data if isinstance(data, list) else data.get("nodes", [])
        assert "credentials" not in json.dumps(nodes).lower(), path.name
