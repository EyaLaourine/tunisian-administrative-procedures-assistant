# Tunisian Administrative Procedures Assistant

An academic assistant grounded in official Tunisian administrative documents. **The frontend is the Telegram bot interface.** A Python bridge connects Telegram to n8n and FastAPI, with local Ollama models and Qdrant retrieval.

## For Professors - Installation and Testing

Start with [the complete Windows installation guide](docs/INSTALLATION.md) or the [PDF guide](output/pdf/Professor_Installation_Guide.pdf).
Prerequisites: Python 3.11, Git, Docker Desktop/Compose v2 and native Ollama. Download `bge-m3`,
`mistral:latest` and `translategemma:4b`. Default ports: backend 8000, n8n 5678, Qdrant 6343, Ollama 11434.

1. Configure private `.env` from `.env.example`; generate your own n8n encryption key.
2. Install dependencies, reconstruct processed files and start the new Docker stack.
3. Initialize Qdrant only on the new empty installation; import the three JSON exports in `workflows/`.
4. Publish workflows 02 and 03; keep workflow 01 inactive. Exact commands are in the guide.
5. Create your own bot with official `@BotFather` and enter its token privately before starting the bridge.
6. Ask a passport question and a follow-up; test FR/EN/AR/Derja and verify official references.
7. Test an unsupported request such as carte grise, upload a supported test form, and try both Form Check and Dossier Check.
8. Run the automated tests; never upload real identity documents for a demonstration.

The project does not ship with personal credentials. Poor photos may be refused; live Telegram delivery
requires the professor's own bot and manual acceptance. See the guide for safe shutdown and troubleshooting.

## Features

- French, English, Arabic and Tunisian Derja interaction, clarification and conversational context.
- Supported passport, national identity card and RNE questions with official references.
- PDF/image assistance for RNE F-001, RNE F-002, CIN and ordinary passport application templates.
- `/form_check` for potential omissions and `/dossier_check` for informational readiness.
- Controlled refusals and numerical evidence checks.

This is not legal advice or official validation. Coverage and source freshness are limited. Recognition does not prove authenticity or legal completeness. No speech recognition or model fine-tuning is claimed.

## Architecture and stack

```text
Telegram -> Python bridge (long polling) -> n8n /webhook/assistant
                                             |
                                      FastAPI services
                                      /             \
                          Qdrant + hybrid RAG      PDF/OCR/forms
                                      |
                       Ollama: BGE-M3, Mistral, TranslateGemma
```

Python 3.11, FastAPI, Uvicorn, Pydantic and HTTPX provide APIs and integration. BM25 and Reciprocal Rank Fusion complement dense retrieval. PyMuPDF, Tesseract, OpenCV and NumPy process documents; Beautiful Soup extracts HTML. Docker Compose manages services and pytest provides tests. The optional web demo is a fallback, not the frontend presented here.

## Quick start (new installation only)

Follow [the Windows installation guide](docs/INSTALLATION.md) for models, private configuration, initial indexing, workflow publication and Telegram setup. Never run initialization commands against production.

```powershell
Copy-Item .env.example .env
# Privately replace N8N_ENCRYPTION_KEY before startup.
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python scripts/build_processed_corpus.py
docker compose up -d --build
```

These commands alone do not populate Qdrant or publish workflows: complete the guide. Tracked official originals allow offline extraction. A fresh index has 14 documents and 286/186 structural/recursive chunks; historical production has 12 indexed documents and 272/174 points. New form templates did not automatically reindex production.

## Testing

```powershell
.venv\Scripts\python -m pytest -m "not integration" -q
```

Build processed files first. Integration scripts may hard-code localhost ports; use a dedicated test installation. HTTP tests do not establish real Telegram delivery. See [release readiness](docs/GITHUB_RELEASE_READINESS.md) for executed checks and limitations.

## Repository structure

| Path | Purpose |
|---|---|
| `telegram_bridge/` | Telegram commands, menus, polling and uploads |
| `backend/`, `agents/` | APIs, routing, conversation and specialized services |
| `rag/`, `ingestion/` | Extraction, retrieval and controlled indexing |
| `workflows/` | Three canonical n8n exports |
| `prompts/`, `config/` | Versioned prompts, source registry, public TLS intermediate |
| `data/raw/` | Official originals and provenance manifest |
| `data/evaluation/`, `tests/` | Recorded evaluations and tests |
| `scripts/`, `deploy/` | Reproduction and deployment tooling |
| `docs/` | Installation, security and historical evidence |
| `report/`, `presentation/` | Academic report, annexes and presentation |

## Security and scope

Never commit `.env`, tokens, private keys, user uploads or credential exports. The certificate in `config/certs/` is a public intermediate CA. TLS verification stays enabled. Administrative endpoints are disabled without an admin key; optional agent/webhook authentication must be configured consistently with n8n. Avoid printing complete container environments or Compose configuration.

See [security guidance](docs/SECURITY_DEPLOYMENT_GUIDE.md), [agent design](docs/AGENTS.md), [evaluation](docs/EVALUATION.md) and [production evidence](docs/PRODUCTION_DEPLOYMENT_REPORT.md). Academic results are tied to their recorded datasets and environments, not universal accuracy guarantees.
