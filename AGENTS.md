# AGENTS.md

Guidance for AI coding assistants working in this repository.

## Non-negotiable rules

1. **Real official data only.** Never add synthetic, invented or AI-generated administrative content
   to `data/raw/`, `config/sources.yaml`, the vector store, prompts or evaluation sets. Test fixtures
   use neutral placeholder text and never describe a procedure.
2. **Never fabricate metadata.** `language`, `publication_date` and `official_reference` in
   `config/sources.yaml` are filled only from the document itself; otherwise `unknown` / `null`.
   `applicability` stays `unverified` unless a human confirms the text is in force.
3. **Respect source policies.** Do not bypass robots.txt, AI opt-outs, CAPTCHAs or logins. Do not
   disable TLS verification; add missing intermediate certificates to `config/certs/` instead.
4. **English-only artifacts.** Code, comments, docs, logs, prompts and commit messages are English.
   User-facing answers and official documents keep their own language (FR / AR / Derja).
5. **Privacy.** Never log user queries, uploaded file contents or personal data. Private uploads are
   never indexed into the public knowledge base.
6. **Honest reporting.** Do not mark unexecuted tests as passed; do not claim services run unless verified.

## Commands

```bash
docker compose up -d --build                 # qdrant, backend, n8n
.venv/Scripts/python -m pytest -v            # tests (integration tests need the stack + host Ollama)
.venv/Scripts/python -m ingestion [--only ID]
curl -X POST localhost:8000/index/run
```

In Git Bash on Windows, prefix `docker compose exec ... /workflows` commands with `MSYS_NO_PATHCONV=1`.
`n8n execute` inside the running container needs `-e N8N_RUNNERS_BROKER_PORT=5690`.

## Layout and conventions

- `ingestion/` -> `data/raw/` (originals stored as `<doc_id>/<sha12>_<basename>`, never overwritten).
- `rag/extraction.py` produces `TextBlock`s; both chunkers in `rag/chunking.py` consume the same blocks.
- Qdrant collections: `official_docs_structure`, `official_docs_recursive` (cosine, 1024-d BGE-M3).
- Agents (`agents/`) are FastAPI endpoints under `/agents/*`; n8n workflow 03 chains them. Checklists are
  read verbatim from `data/processed/extracted/`; LLMs only translate FR->EN (validated) and write
  grounded answers (citations validated). See `docs/AGENTS.md`.
- Prompts are versioned in `prompts/<name>/<version>.yaml`; never edit a version in place, add a new
  one and switch `prompts/registry.yaml`.
- Send non-ASCII test queries as UTF-8 JSON from Python or a file; Git Bash `curl -d` may mangle them.
- Deterministic Python over LLM calls wherever the logic is rule-based.
- Settings come from environment variables (`backend/settings.py`); secrets only in `.env`.
