"""Local demonstration interface: a validating proxy to the REAL n8n workflow 03 plus one static page.

The page never talks to n8n or the backend directly. This app:
  * serves demo_ui/static/index.html (no external assets: works without internet);
  * forwards chat questions and uploads to the active n8n webhook, unchanged in format, after validating
    them (language, length, file type, size, base64); `mode: "dossier"` is sent only when requested;
  * reports real service status by calling n8n /healthz and the backend /health.

It adds no administrative logic and generates no answer: every response comes from n8n -> agents.
Privacy: nothing is stored; request contents, file names and response texts are never logged.

Run (Windows PowerShell, from the repository root):
  .venv\\Scripts\\python.exe -m uvicorn demo_ui.app:app --host 127.0.0.1 --port 8090
"""

import base64
import binascii
import logging
import os
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

N8N_WEBHOOK = os.environ.get("DEMO_N8N_WEBHOOK", "http://127.0.0.1:5678/webhook/assistant")
N8N_HEALTH = os.environ.get("DEMO_N8N_HEALTH", "http://127.0.0.1:5678/healthz")
BACKEND_HEALTH = os.environ.get("DEMO_BACKEND_HEALTH", "http://127.0.0.1:8000/health")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # same limit as the backend (MAX_UPLOAD_BYTES)
ALLOWED_MIME = {"application/pdf", "image/png", "image/jpeg"}  # the formats the bridge contract accepts
TIMEOUT_SECONDS = 600.0
STATIC = Path(__file__).resolve().parent / "static"
RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
# Official blank forms (public documents from the corpus) offered as one-click demo inputs. Fixed allow-list:
# no other file can be read through this endpoint.
SAMPLES = {
    "f001": ("rne-form-f001-natural-person-registration", "RNE F-001 (official blank form, natural person)"),
    "f002": ("rne-form-f002-legal-entity-registration", "RNE F-002 (official blank form, legal entity)"),
}

log = logging.getLogger("demo_ui")
app = FastAPI(title="Demo UI proxy", docs_url=None, redoc_url=None)

Language = Literal["en", "fr", "ar", "derja"]


class AskRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    language: Language | None = None


class UploadRequest(BaseModel):
    filename: str = Field(default="upload", max_length=255)
    mime_type: str
    data_b64: str = Field(min_length=1)
    language: Language | None = None
    mode: Literal["form_check", "dossier"] = "form_check"

    @field_validator("mime_type")
    @classmethod
    def _mime(cls, v: str) -> str:
        if v not in ALLOWED_MIME:
            raise ValueError("unsupported file type (PDF, PNG or JPEG only)")
        return v

    @field_validator("data_b64")
    @classmethod
    def _size(cls, v: str) -> str:
        try:
            raw = base64.b64decode(v, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("invalid file encoding") from exc
        if len(raw) > MAX_UPLOAD_BYTES:
            raise ValueError("file larger than 10 MB")
        return v


def _client(timeout: float = TIMEOUT_SECONDS) -> httpx.Client:
    return httpx.Client(timeout=timeout)


def forward(payload: dict) -> dict:
    """POST the payload to the n8n webhook; errors are reported without echoing request contents."""
    try:
        with _client() as c:
            resp = c.post(N8N_WEBHOOK, json=payload)
    except httpx.HTTPError as exc:
        log.warning("n8n_unreachable", extra={"error": type(exc).__name__})
        raise HTTPException(status_code=502, detail="The n8n workflow is not reachable.") from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"The n8n workflow returned HTTP {resp.status_code}.")
    try:
        return resp.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="The n8n workflow returned an invalid response.") from exc


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html", media_type="text/html; charset=utf-8")


@app.get("/api/status")
def status() -> dict:
    out = {}
    with _client(timeout=5) as c:
        for name, url in (("n8n", N8N_HEALTH), ("backend", BACKEND_HEALTH)):
            try:
                r = c.get(url)
                body = r.json() if "json" in r.headers.get("content-type", "") else {}
                ok = r.status_code == 200 and body.get("status", "ok") == "ok"
                out[name] = {"ok": ok, "detail": body if name == "backend" else {"http": r.status_code}}
            except (httpx.HTTPError, ValueError) as exc:
                out[name] = {"ok": False, "detail": {"error": type(exc).__name__}}
    return out


@app.get("/api/sample/{sample_id}")
def sample(sample_id: str) -> dict:
    if sample_id not in SAMPLES:
        raise HTTPException(status_code=404, detail="Unknown sample.")
    doc_id, label = SAMPLES[sample_id]
    files = sorted((RAW / doc_id).glob("*.pdf"))
    if not files:
        raise HTTPException(status_code=404, detail="Official form not available locally.")
    return {"filename": files[0].name, "label": label, "mime_type": "application/pdf",
            "data_b64": base64.b64encode(files[0].read_bytes()).decode()}


@app.post("/api/ask")
def ask(req: AskRequest) -> dict:
    payload = {"text": req.text}
    if req.language:
        payload["language"] = req.language
    return forward(payload)


@app.post("/api/upload")
def upload(req: UploadRequest) -> dict:
    # Same payload format as the Telegram bridge; "mode" only for dossier validation.
    payload: dict = {"file": {"filename": req.filename, "mime_type": req.mime_type, "data_b64": req.data_b64}}
    if req.language:
        payload["language"] = req.language
    if req.mode == "dossier":
        payload["mode"] = "dossier"
    return forward(payload)
