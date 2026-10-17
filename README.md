# Tunisian Administrative Procedures Assistant

A multi-agent Retrieval-Augmented Generation (RAG) assistant that helps Tunisian citizens understand
official administrative procedures (passport, national ID card, business registration with the RNE),
built **exclusively on documents retrieved from official Tunisian government sources**. It answers in
English, French, Arabic and Tunisian Derja, on Telegram or over HTTP, and checks official forms (PDF or
photo) for empty fields.

> Status: **Phase 1 (foundation) and Phase 2 (agents, n8n orchestration, Telegram, multilingual
> answers, form checking) implemented and tested.** Speech recognition is not implemented.
> Agent design: [docs/AGENTS.md](docs/AGENTS.md). Results: [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md).

The assistant does **not** provide legal advice and never states that a document is legally valid.
Checklists are quoted verbatim from the official texts. Every answer lists its official sources (URL,
official reference). Each source keeps an `applicability` flag that stays `unverified` until a human
confirms the text is still in force.

## Architecture

```
 Telegram ─(long polling)─ telegram-bridge ─┐
 HTTP client ───────────────────────────────┤ POST /webhook/assistant
                                            ▼
                               n8n workflow 03 (orchestrator)
        ┌───────────────┬───────────────┬──────────────────┬───────────────────┐
        ▼               ▼               ▼                  ▼                   ▼
  Intent Router   RAG Retriever   Checklist Builder   Grounded Answer   Form-Filling Helper
  /agents/route   /agents/retrieve /agents/checklist  /agents/answer    /agents/form-check
        └───────────────┴──── FastAPI backend (agents/, rag/) ────────────────┘
                          │                         │
                Qdrant (official corpus)    Ollama on the host: bge-m3, mistral, translategemma
```

Phase 1 workflows remain: `01` (ingest and index, manual or weekly) and `02` (`/webhook/retrieve`).

## Quick start

Prerequisites: Docker Desktop (Compose v2), Ollama on the host, Python 3.11 (for tests/CLI).

```bash
# 1. Configuration
cp .env.example .env          # then set N8N_ENCRYPTION_KEY to a long random string

# 2. Local models (host Ollama)
ollama pull bge-m3
ollama pull mistral
ollama pull translategemma:4b

# 3. Start the stack (Qdrant, backend, n8n)
docker compose up -d --build
curl http://localhost:8000/health          # {"status":"ok","qdrant":true,"ollama":true,...}

# 4. Import, index and publish the n8n workflows (Git Bash on Windows: prefix with MSYS_NO_PATHCONV=1)
docker compose exec n8n n8n import:workflow --separate --input=/workflows
docker compose exec -e N8N_RUNNERS_BROKER_PORT=5690 n8n n8n execute --id TnaaIngestIndex1
docker compose exec -e N8N_RUNNERS_BROKER_PORT=5690 n8n n8n publish:workflow --id=TnaaRetrieveApi1
docker compose exec -e N8N_RUNNERS_BROKER_PORT=5690 n8n n8n publish:workflow --id=TnaaAssistant01
docker compose restart n8n

# 5. Ask the assistant through n8n (send UTF-8 JSON; on Windows prefer a file: -d @question.json)
curl -X POST http://localhost:5678/webhook/assistant -H "content-type: application/json; charset=utf-8" \
  -d '{"text":"Quelles pièces fournir pour renouveler un passeport ?"}'
```

Form check over HTTP: `{"file": {"filename": "f.pdf", "mime_type": "application/pdf", "data_b64": "<base64>"}, "language": "fr"}`.

### Telegram

All commands, menus, language preferences and upload handlers can be tested without Telegram credentials.
The optional bridge runs in its own lightweight image. Without a token, Compose keeps it idle with
`LIVE_CONNECTIVITY_PENDING`; this does not affect backend or n8n and does not claim live connectivity.

For the existing running stack, build/start only the bridge:

```powershell
docker compose --profile telegram up -d --no-deps --build telegram-bridge
```

For a fresh stack after the setup and workflow publication steps above:

```powershell
docker compose --profile telegram up -d --build
```

Commands: `/start`, `/help`, `/language`, `/procedures`, `/passport`, `/birth_certificate`, `/business`,
`/checklist`, `/form_check`, `/privacy`, `/cancel`. Inline menus include language and procedure choices,
Back, Main menu and New question. Selected language persists; New question clears procedure context,
and `/cancel` clears preferences and suppresses a pending answer. Official evidence remains unchanged.

PDF, JPEG, PNG and Telegram photos are processed in memory with size and signature checks. Private
uploads are never stored or indexed. Unknown forms and unreadable files receive distinct explanations;
all form results require manual verification. Source coverage remains limited for birth certificates.

Preferences expire after 30 minutes of inactivity, with at most 1,000 sessions. At most two upstream
requests run simultaneously, one per chat. Cancellation suppresses delivery and further retries but
cannot interrupt processing already running inside n8n/OCR. Update deduplication is process-local;
crash recovery is not exactly once. A fixed container name, local process lock and Telegram conflict
handling discourage competing pollers. No public URL or inbound Telegram port is required.

[Activation guide and live-test checklist](docs/TELEGRAM_ACTIVATION.md) ·
[Telegram implementation and verification report](docs/TELEGRAM_REPORT.md)

| Service | Host port | Notes |
|---|---|---|
| backend (FastAPI) | 8000 | OpenAPI docs at `/docs`; agents under `/agents/*` |
| n8n | 5678 | workflows in [workflows/](workflows/) |
| Qdrant | 6343 | 6333 deliberately avoided (may be used by another local project) |
| Ollama | 11434 (host) | optional containerised Ollama: `--profile ollama-docker` |
| telegram-bridge | — | outbound only; compose profile `telegram` |

All ports are bound to `127.0.0.1` only.

## Local development and tests

```bash
py -3.11 -m venv .venv
.venv/Scripts/pip install -e ".[dev]"        # Linux/macOS: .venv/bin/pip
.venv/Scripts/python -m pytest -m "not integration"   # unit tests (no services needed)
.venv/Scripts/python -m pytest -m integration         # needs the stack, published workflow 03 and host Ollama
.venv/Scripts/python scripts/benchmark.py --runs 3    # local LLM + end-to-end latency benchmark
.venv/Scripts/python -m ingestion                     # run ingestion from the CLI (same code as /ingestion/run)
```

## Repository layout

| Path | Content |
|---|---|
| `backend/` | FastAPI app (`main.py`, `agents_api.py`), settings, structured logging, Dockerfile (includes Tesseract OCR) |
| `ingestion/` | source registry models, robots/AI-opt-out policy, downloader, checksums, manifest, manual import |
| `rag/` | extraction (PDF/HTML structure detection), chunking (recursive + structure-aware), embeddings, Qdrant store, indexing, retrieval |
| `agents/` | intent router, language detection, retriever, checklist builder, grounded answer, form helper, UI strings |
| `prompts/` | versioned prompt library (`registry.yaml` selects the active version of each prompt) |
| `telegram_bridge/` | Telegram Bot API long-polling bridge to the n8n webhook |
| `workflows/` | exported n8n workflows (01 ingest/index, 02 retrieval API, 03 multi-agent assistant) |
| `scripts/` | benchmark |
| `config/sources.yaml` | **official source registry** (approved, excluded and not-found candidates with reasons) |
| `config/certs/` | intermediate CA certificate for an official server with an incomplete TLS chain |
| `data/raw/` | unmodified official originals + `manifest.json` (provenance, SHA-256) + `ingestion_log.jsonl` |
| `data/processed/` | regenerable extraction and chunk outputs (git-ignored) |
| `data/evaluation/` | benchmark output |
| `docs/` | agent design, test results |

## Data policy

Only real documents from official Tunisian sources are used. No synthetic or AI-generated
administrative content enters the knowledge base. Sources whose `robots.txt` opts out of AI agents,
or disallows crawling of a path, are not downloaded automatically. Every source, including excluded and
not-found candidates with the reason, is listed in [config/sources.yaml](config/sources.yaml).
User questions and uploaded files are processed in memory and are never logged, stored or indexed.
