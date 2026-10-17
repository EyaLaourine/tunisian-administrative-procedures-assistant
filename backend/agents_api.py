"""HTTP endpoints for the Phase 2 agents. n8n calls them in sequence (see workflows/03_*.json).

Privacy: request bodies (user questions, uploads) are never logged; only routing metadata is.
"""

import logging
import time

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from agents.answer import GroundedAnswerer
from agents.answerability import AnswerabilityGate
from agents.verification import EvidenceVerifier
from agents.checklist_builder import ChecklistBuilder
from agents.corpus import Corpus
from agents.dossier_validator import DossierReport, DossierValidator
from agents.form_helper import FormHelper
from agents.intent_router import IntentRouter
from agents.language import detect_language
from agents.llm import OllamaChatClient
from agents.prompts import PromptLibrary
from agents.retriever import routed_retrieve
from agents.schemas import (
    AgentRetrieveRequest, AgentRetrieveResponse, AnswerResult, ChecklistResult, ComposeRequest,
    FormCheckRequest, FormCheckResult, RouteDecision, RouteRequest,
)
from backend.settings import Settings

log = logging.getLogger(__name__)
def require_agent_key(request: Request, x_agent_key: str | None = Header(default=None)) -> None:
    """When AGENT_API_KEY is configured, only callers sending it (the n8n HTTP nodes) may use the agents.
    Unset: open, as before (the port is bound to 127.0.0.1 / the internal Docker network)."""
    expected = (getattr(request.app.state.settings, "agent_api_key", None) or "").strip()
    if expected and not (x_agent_key and hmac.compare_digest(x_agent_key.encode(), expected.encode())):
        raise HTTPException(status_code=401, detail="Missing or invalid X-Agent-Key header.")


router = APIRouter(prefix="/agents", tags=["agents"], dependencies=[Depends(require_agent_key)])


class Agents:
    def __init__(self, settings: Settings):
        self.prompts = PromptLibrary(settings.prompts_path)
        self.llm = OllamaChatClient(settings.ollama_url, settings.llm_model, settings.translation_model or None,
                                    timeout=settings.llm_timeout_seconds)
        self.corpus = Corpus(settings.raw_dir, settings.processed_dir)
        self.router = IntentRouter(self.llm, self.prompts, settings.intent_llm_fallback)
        gate = AnswerabilityGate(settings.processed_dir / "chunks_structure.jsonl")
        verifier = (EvidenceVerifier(self.llm, self.prompts, settings.processed_dir / "chunks_structure.jsonl",
                                     topic_check=settings.evidence_topic_check)
                    if settings.evidence_verification else None)
        self.checklist = ChecklistBuilder(self.corpus, self.llm, self.prompts, gate, verifier)
        self.answerer = GroundedAnswerer(self.llm, self.prompts, gate, verifier, self.corpus)
        self.forms = FormHelper(self.corpus, settings.max_upload_bytes, settings.ocr_languages)
        self.dossier = DossierValidator(self.forms, self.checklist, self.corpus)


def _agents(request: Request) -> Agents:
    return request.app.state.agents


def _timed(event: str, started: float, **fields) -> None:
    log.info(event, extra={"fields": {"ms": round((time.perf_counter() - started) * 1000), **fields}})


@router.post("/route", response_model=RouteDecision)
async def route(req: RouteRequest, request: Request) -> RouteDecision:
    started = time.perf_counter()
    decision = await run_in_threadpool(_agents(request).router.route, req)
    _timed("agent_route", started, intent=decision.intent, category=decision.procedure_category,
           language=decision.language, method=decision.method, next=decision.next_agent)
    return decision


@router.post("/retrieve", response_model=AgentRetrieveResponse)
async def retrieve(req: AgentRetrieveRequest, request: Request) -> AgentRetrieveResponse:
    started = time.perf_counter()
    app = request.app
    res = await run_in_threadpool(routed_retrieve, req.route.retrieval_query or req.query, req.route, req.top_k, app.state.settings,
                                  app.state.embedder, app.state.store)
    _timed("agent_retrieve", started, passages=len(res.passages))
    return res


@router.post("/checklist", response_model=ChecklistResult)
async def checklist(req: ComposeRequest, request: Request) -> ChecklistResult:
    started = time.perf_counter()
    res = await run_in_threadpool(_agents(request).checklist.build, req)
    _timed("agent_checklist", started, found=res.found, doc_id=res.doc_id,
           translated=bool(res.translation and res.translation.get("validated")))
    return res


@router.post("/answer", response_model=AnswerResult)
async def answer(req: ComposeRequest, request: Request) -> AnswerResult:
    started = time.perf_counter()
    res = await run_in_threadpool(_agents(request).answerer.answer, req)
    _timed("agent_answer", started, method=res.method, citations=len(res.citations))
    return res


@router.post("/form-check", response_model=FormCheckResult)
async def form_check(req: FormCheckRequest, request: Request) -> FormCheckResult:
    started = time.perf_counter()
    default_lang = detect_language(req.caption) if req.caption else "fr"
    res = await run_in_threadpool(_agents(request).forms.check, req, default_lang)
    _timed("agent_form_check", started, recognised=res.recognised, method=res.method, missing=len(res.missing))
    return res


@router.post("/dossier-check", response_model=DossierReport)
async def dossier_check(req: FormCheckRequest, request: Request) -> DossierReport:
    """Smart Administrative Dossier Validator: form-field status + official requirements (assistance only)."""
    started = time.perf_counter()
    app = request.app
    default_lang = detect_language(req.caption) if req.caption else "fr"

    def retrieve(query, route):
        return routed_retrieve(query, route, 8, app.state.settings, app.state.embedder, app.state.store).passages

    res = await run_in_threadpool(_agents(request).dossier.validate, req, retrieve, default_lang)
    _timed("agent_dossier_check", started, recognised=res.recognized, missing=len(res.missing_fields),
           checklist_available=res.official_checklist_available)
    return res


@router.get("/prompts")
def prompts(request: Request) -> dict:
    return _agents(request).prompts.list_versions()
