"""Demo interface proxy (demo_ui/app.py).

Unit tests replace only the HTTP hop to n8n (to assert the exact forwarded payload and error handling);
the integration tests at the end go through the proxy to the REAL n8n workflow 03.
"""

import base64
import glob
import json
import logging
import re

import httpx
import pytest
from fastapi.testclient import TestClient

import demo_ui.app as demo
from backend.settings import REPO_ROOT

F001 = glob.glob(str(REPO_ROOT / "data/raw/rne-form-f001-natural-person-registration/*.pdf"))
PDF_B64 = base64.b64encode(b"%PDF-1.4 placeholder").decode()


@pytest.fixture
def captured(monkeypatch):
    """Records what the proxy sends to n8n and returns a canned n8n-shaped response."""
    sent = {"payloads": [], "status": 200,
            "response": {"text": "reply", "agent": "checklist_builder", "citations": [{"url": "https://x", "title": "t"}]}}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/healthz") or request.url.path.endswith("/health"):
            return httpx.Response(200, json={"status": "ok", "qdrant": True, "ollama": True})
        sent["payloads"].append(json.loads(request.content))
        return httpx.Response(sent["status"], json=sent["response"])

    monkeypatch.setattr(demo, "_client", lambda timeout=demo.TIMEOUT_SECONDS: httpx.Client(transport=httpx.MockTransport(handler)))
    return sent


@pytest.fixture
def client():
    return TestClient(demo.app)


def test_chat_forwards_text_and_language_unchanged(client, captured):
    r = client.post("/api/ask", json={"text": "Quelles pièces fournir ?", "language": "fr"})
    assert r.status_code == 200 and r.json()["citations"][0]["url"] == "https://x"
    assert captured["payloads"] == [{"text": "Quelles pièces fournir ?", "language": "fr"}]
    client.post("/api/ask", json={"text": "chnowa lezmni"})
    assert captured["payloads"][-1] == {"text": "chnowa lezmni"}  # auto-detect: no language field


def test_form_check_upload_keeps_the_existing_payload_format(client, captured):
    client.post("/api/upload", json={"filename": "f.pdf", "mime_type": "application/pdf", "data_b64": PDF_B64, "language": "en"})
    assert captured["payloads"][-1] == {"file": {"filename": "f.pdf", "mime_type": "application/pdf", "data_b64": PDF_B64},
                                        "language": "en"}


def test_dossier_upload_adds_mode_dossier_only(client, captured):
    client.post("/api/upload", json={"filename": "f.pdf", "mime_type": "application/pdf", "data_b64": PDF_B64, "mode": "dossier"})
    assert captured["payloads"][-1]["mode"] == "dossier" and "language" not in captured["payloads"][-1]


@pytest.mark.parametrize("body,fragment", [
    ({"mime_type": "text/plain", "data_b64": PDF_B64}, "unsupported file type"),
    ({"mime_type": "application/zip", "data_b64": PDF_B64}, "unsupported file type"),
    ({"mime_type": "application/pdf", "data_b64": "%%%"}, "invalid file encoding"),
    ({"mime_type": "application/pdf", "data_b64": base64.b64encode(b"x" * (10 * 1024 * 1024 + 1)).decode()}, "larger than 10 MB"),
    ({"mime_type": "application/pdf", "data_b64": PDF_B64, "mode": "approve"}, ""),
    ({"mime_type": "application/pdf", "data_b64": PDF_B64, "language": "de"}, ""),
])
def test_invalid_uploads_are_rejected_before_n8n(client, captured, body, fragment):
    r = client.post("/api/upload", json=body)
    assert r.status_code == 422 and fragment in json.dumps(r.json())
    assert captured["payloads"] == []


def test_invalid_questions_are_rejected(client, captured):
    assert client.post("/api/ask", json={"text": ""}).status_code == 422
    assert client.post("/api/ask", json={"text": "x" * 2001}).status_code == 422
    assert captured["payloads"] == []


def test_n8n_errors_are_reported_without_echoing_inputs(client, captured, monkeypatch):
    captured["status"] = 500
    r = client.post("/api/ask", json={"text": "SECRET-QUESTION-TEXT"})
    assert r.status_code == 502 and "HTTP 500" in r.json()["detail"] and "SECRET" not in r.text

    def down(timeout=demo.TIMEOUT_SECONDS):
        def handler(request):
            raise httpx.ConnectError("refused")
        return httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(demo, "_client", down)
    r = client.post("/api/ask", json={"text": "question"})
    assert r.status_code == 502 and "not reachable" in r.json()["detail"]
    status = client.get("/api/status").json()
    assert status["n8n"]["ok"] is False and status["backend"]["ok"] is False


def test_nothing_from_the_request_is_logged(client, captured, caplog):
    with caplog.at_level(logging.DEBUG):
        client.post("/api/ask", json={"text": "PRIVATE-QUESTION"})
        client.post("/api/upload", json={"filename": "PRIVATE-NAME.pdf", "mime_type": "application/pdf", "data_b64": PDF_B64})
    assert "PRIVATE" not in caplog.text


def test_sample_endpoint_serves_only_the_official_blank_forms(client):
    assert client.get("/api/sample/f003").status_code == 404
    assert client.get("/api/sample/..%2F..%2F.env").status_code == 404
    if F001:
        s = client.get("/api/sample/f001").json()
        assert base64.b64decode(s["data_b64"]) == open(F001[0], "rb").read() and s["mime_type"] == "application/pdf"


def test_page_renders_backend_content_as_text_with_rtl_and_citations(client):
    html = client.get("/").text
    assert "Tunisian Administrative Procedures Assistant" in html
    assert all(lang in html for lang in ('value="en"', 'value="fr"', 'value="ar"', 'value="derja"'))
    # Backend content is only ever inserted through textContent; innerHTML is used only to clear a node.
    assert re.findall(r"innerHTML\s*=\s*([^;]+);", html) == ['""']
    assert "u0600-\\u06FF" in html and 'dir = "auto"' in html  # Arabic-script detection and auto direction
    assert "renderCitations" in html and 'rel = "noopener noreferrer"' in html
    assert "not a certification that a dossier is complete" in html
    assert "http://" not in html.replace("http://www.w3.org", "")  # no external assets; works offline


def test_web_payloads_satisfy_the_telegram_bridge_contract(client, captured):
    """Both interfaces share one n8n request contract; the web fallback must never diverge from Telegram."""
    from telegram_bridge.contracts import AssistantRequest
    client.post("/api/ask", json={"text": "question", "language": "derja"})
    for mode in ("form_check", "dossier"):
        client.post("/api/upload", json={"filename": "f.pdf", "mime_type": "application/pdf", "data_b64": PDF_B64,
                                         "language": "fr", "mode": mode})
    for p in captured["payloads"]:
        assert AssistantRequest.model_validate(p).model_dump(exclude_none=True) == p


# ---------------------------------------------------------------------- real n8n (integration)
@pytest.mark.integration
def test_real_n8n_through_the_proxy(client):
    if not client.get("/api/status").json()["n8n"]["ok"]:
        pytest.skip("n8n not reachable")
    d = client.post("/api/ask", json={"text": "Quelles pièces fournir pour une première demande de passeport ?"}).json()
    assert d["agent"] == "checklist_builder" and any("interieur.gov.tn" in c["url"] for c in d["citations"])
    sample = client.get("/api/sample/f002").json()
    form = client.post("/api/upload", json={**{k: sample[k] for k in ("filename", "mime_type", "data_b64")}, "language": "fr"}).json()
    assert form["agent"] == "form_helper" and len(form["missing"]) == 8
    dossier = client.post("/api/upload", json={**{k: sample[k] for k in ("filename", "mime_type", "data_b64")},
                                               "language": "fr", "mode": "dossier"}).json()
    assert dossier["agent"] == "dossier_validator" and dossier["report"]["dossier"]["completeness_certified"] is False
    # The same live responses must also be accepted by the Telegram bridge (primary interface).
    from telegram_bridge.contracts import AssistantResponse
    for resp in (d, form, dossier):
        AssistantResponse.model_validate(resp)
