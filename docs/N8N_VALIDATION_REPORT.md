# Workflow preparation validation — 17 October 2026

Scope: offline visual candidates and read-only deployment audit; no live imports, publication changes, workflow execution, backend/bridge deployment, ingestion or reindexing. No Telegram messages sent. Candidate environments remain untouched.

## Observed checks

- Initial Git: clean `master`, HEAD `a5aef273e7d7d4d888efbb92645f15c219bbf48a`; dedicated branch `codex/final-n8n-workflows` created. Existing validated source and canonical workflows unchanged.
- Three official CLI exports preserved separately in ignored timestamped storage. Second export compared full nodes/layout, execution settings, IDs, publication versions and runtime semantics: no drift. Evidence: [live_integrity.json](../deploy/n8n_review/live_integrity.json).
- All three candidates parse and pass structural validation: unique IDs/names, valid references/connections, reachable executable branches, unchanged selected-baseline semantics, existing backend routes, expected webhook paths, no literal key headers or token patterns.
- Installed n8n 2.41.3 Sticky Note v1 schema/palette inspected. Geometry checks cover executable node boxes and note frames. Candidates have not been imported or rendered natively.
- Localized workflow 03 error JSON expression evaluated with Node in an isolated sandbox for FR/EN/AR/Derja and language fallback; status 503 and sanitized error contract checked. This is expression/graph testing, not execution by n8n.
- Existing API security tests use FastAPI TestClient without lifespan, no Qdrant/Ollama connections; bridge header tests use MockTransport. Admin operations are never executed.

## Reproduction

```powershell
.venv/Scripts/python -m pytest tests/test_n8n_workflow_review.py tests/test_api_security.py -q --junitxml=tmp/n8n-review/focused-tests.xml
.venv/Scripts/python scripts/n8n_workflow_review.py --verify-live --baseline tmp/n8n-review/20261017T220611Z
```

Final focused run: **55 passed, 0 failed, 0 skipped**, six dependency deprecation warnings. Infrastructure/secret-scan evidence is recorded in [validation.json](../deploy/n8n_review/validation.json). The first focused run found one overlapping annotation frame; its height was corrected, candidates regenerated and the complete focused suite rerun. No production code changed to improve scores.

## Interpretation and remaining gates

Readiness: **conditionally ready for explicitly approved workflow application**. Not a security-enforced release sign-off. The older production backend does not contain all reviewed hardened/legal features; credentials are not configured. Primary workflow candidates preserve existing callers and contain only a separate credential activation plan.

Still unverified: native candidate rendering/import/publication, actual n8n error execution and malformed-success handling, real credential interoperability, candidate/live answer correctness and groundedness, full language/context regression, PDF/image/OCR acceptance, Telegram real message exchange and duplicate prevention under failure. No new claim of document/question coverage, correctness percentage, or legal completeness is made. These require approved, evidence-recorded acceptance rather than inferring success from citations or health.

Known gaps: workflow 03 collapses HTTP status specificity into 503; workflows 01/02 have no custom error responder; Content-Length middleware is not a full streamed body limiter; optional keys are not live enforcement. Retained existing behavior is documented rather than silently changed.

See [architecture](N8N_THREE_WORKFLOW_ARCHITECTURE.md), [visual scope](N8N_VISUAL_REDESIGN.md), [security](N8N_SECURITY_INTEGRATION.md), [sync](N8N_WORKFLOW_SYNC.md), [deployment/rollback](N8N_DEPLOYMENT_CHECKLIST.md), [acceptance](N8N_ACCEPTANCE_TESTS.md), and [demo](N8N_DEMO_GUIDE.md).

## Exact changed-file inventory

All 22 files are new; no pre-existing backend, agent, RAG, prompt, corpus, evaluation ground truth, Compose, environment or canonical workflow file changed. Paths are relative to `%USERPROFILE%\tunisian-admin-assistant`.

| Path | Purpose |
|---|---|
| `deploy/n8n_review/candidates/01_ingest_and_index.json` | Native visual candidate, inactive. |
| `deploy/n8n_review/candidates/02_retrieve_api.json` | Native visual candidate, preserves live active state. |
| `deploy/n8n_review/candidates/03_assistant_multi_agent.json` | Native visual candidate, retains repository error branches and live active state. |
| `deploy/n8n_review/COMPARISON.md` | Human-readable runtime/visual/security drift summary. |
| `deploy/n8n_review/comparisons/TnaaIngestIndex1.json` | Field-level workflow 01 differences. |
| `deploy/n8n_review/comparisons/TnaaRetrieveApi1.json` | Field-level workflow 02 differences. |
| `deploy/n8n_review/comparisons/TnaaAssistant01.json` | Field-level workflow 03 differences. |
| `deploy/n8n_review/review_manifest.json` | Baseline paths, versions, selected authority and semantic hashes. |
| `deploy/n8n_review/security_mapping.json` | Nine backend calls and webhook credential activation plan, no values. |
| `deploy/n8n_review/live_integrity.json` | Second-export drift guard result. |
| `deploy/n8n_review/runtime_integrity.json` | Sanitized unchanged-container checks, health and read-only collection counts. |
| `deploy/n8n_review/validation.json` | Focused test totals, private-value scan summary and unexecuted gates. |
| `scripts/n8n_workflow_review.py` | Read-only export/drift guard, offline layout generator and structural validator; no apply code. |
| `tests/test_n8n_workflow_review.py` | Offline graph, layout, error-expression, mapping and drift-guard tests. |
| `docs/N8N_THREE_WORKFLOW_ARCHITECTURE.md` | Actual components, contracts, model/deployment boundaries and diagram. |
| `docs/N8N_VISUAL_REDESIGN.md` | Native note schema, palette, counts, scope and visual acceptance limits. |
| `docs/N8N_WORKFLOW_SYNC.md` | Reproducible comparisons and controlled application process. |
| `docs/N8N_SECURITY_INTEGRATION.md` | Exact header mapping, runtime gaps, coordinated enforcement and rollback. |
| `docs/N8N_DEPLOYMENT_CHECKLIST.md` | Separate workflow/backend/key gates and precise rollback plan. |
| `docs/N8N_ACCEPTANCE_TESTS.md` | Language, context, official grounding, multimodal, security and failure test matrix. |
| `docs/N8N_DEMO_GUIDE.md` | Fifteen-minute demonstration and English narration. |
| `docs/N8N_VALIDATION_REPORT.md` | Observed validation, limits and this inventory. |
