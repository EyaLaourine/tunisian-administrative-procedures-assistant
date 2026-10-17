"""FastAPI service exposing ingestion, indexing and retrieval to n8n workflows."""

import hmac
import logging
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from backend.agents_api import Agents
from backend.agents_api import require_agent_key
from backend.agents_api import router as agents_router
from backend.logging_setup import configure_logging
from backend.settings import get_settings
from ingestion.manifest import Manifest
from ingestion.pipeline import run_ingestion
from ingestion.registry import load_registry
from rag.embeddings import EmbeddingError, OllamaEmbeddingClient
from rag.indexing import collection_name, run_indexing
from rag.retrieval import RetrievalRequest, RetrievedPassage, retrieve
from rag.vector_store import QdrantStore

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.settings = settings
    app.state.store = QdrantStore(settings.qdrant_url, settings.qdrant_api_key)
    app.state.embedder = OllamaEmbeddingClient(settings.ollama_url, settings.embedding_model, settings.embedding_dim)
    app.state.agents = Agents(settings)
    log.info("backend_started", extra={"fields": {"env": settings.app_env}})
    yield


app = FastAPI(title="Tunisian Administrative Procedures Assistant", version="0.2.0", lifespan=lifespan)
app.include_router(agents_router)


class HealthResponse(BaseModel):
    status: str  # "ok" when every dependency is reachable, otherwise "degraded"
    qdrant: bool
    ollama: bool
    manifest_records: int


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    s = app.state.settings
    qdrant_ok = app.state.store.ping()
    ollama_ok = app.state.embedder.ping()
    records = len(Manifest(s.raw_dir / "manifest.json").records)
    return HealthResponse(
        status="ok" if qdrant_ok and ollama_ok else "degraded", qdrant=qdrant_ok, ollama=ollama_ok, manifest_records=records
    )


@app.get("/sources")
def sources() -> dict:
    """Registry entries (including excluded / not-found candidates and their reasons)."""
    registry = load_registry(app.state.settings.registry_path)
    return {"sources": [e.model_dump(mode="json") for e in registry.sources]}


@app.get("/manifest")
def manifest() -> dict:
    m = Manifest(app.state.settings.raw_dir / "manifest.json")
    return {"records": [r.model_dump(mode="json") for r in m.records.values()]}


class IngestionRequest(BaseModel):
    only: list[str] | None = None


def require_admin(x_admin_key: str | None = Header(default=None)) -> None:
    """Privileged endpoints fail closed: disabled without ADMIN_API_KEY, otherwise the key is required
    (constant-time comparison)."""
    expected = (app.state.settings.admin_api_key or "").strip()
    if not expected:
        raise HTTPException(status_code=403, detail="Administrative endpoints are disabled (ADMIN_API_KEY not configured).")
    if not (x_admin_key and hmac.compare_digest(x_admin_key.encode(), expected.encode())):
        raise HTTPException(status_code=401, detail="Missing or invalid X-Admin-Key header.")


@app.middleware("http")
async def limit_request_size(request, call_next):
    """Reject oversized bodies before they are read (uploads are also checked again by the agents)."""
    from fastapi.responses import JSONResponse
    length = request.headers.get("content-length")
    limit = app.state.settings.max_request_bytes if hasattr(app.state, "settings") else 15 * 1024 * 1024
    if length and length.isdigit() and int(length) > limit:
        return JSONResponse(status_code=413, content={"detail": "Request body too large."})
    return await call_next(request)


@app.post("/ingestion/run", dependencies=[Depends(require_admin)])
async def ingestion_run(req: IngestionRequest | None = None) -> dict:
    summary = await run_in_threadpool(run_ingestion, app.state.settings, req.only if req else None)
    return {"started_at": summary.started_at, "finished_at": summary.finished_at,
            "counts": summary.counts(), "results": summary.results}


@app.post("/index/run", dependencies=[Depends(require_admin)])
async def index_run() -> dict:
    s = app.state.settings
    try:
        report = await run_in_threadpool(run_indexing, s, app.state.embedder, app.state.store)
    except EmbeddingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    counts = {st: app.state.store.count(collection_name(s, st)) for st in report.chunks_per_strategy}
    return {**asdict(report), "collection_points": counts}


@app.post("/retrieve", response_model=list[RetrievedPassage], dependencies=[Depends(require_agent_key)])
async def retrieve_endpoint(req: RetrievalRequest) -> list[RetrievedPassage]:
    try:
        return await run_in_threadpool(retrieve, req, app.state.settings, app.state.embedder, app.state.store)
    except EmbeddingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
