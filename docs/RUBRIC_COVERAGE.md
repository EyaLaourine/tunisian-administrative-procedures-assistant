# Rubric coverage

Audit of 2026-10-16. Every number below comes from a file in `data/evaluation/` or from a test run
recorded in `docs/TEST_RESULTS.md`. No final grade is predicted.

**Evaluation sets and their status.**
- **Development (84):** used for tuning.
- **Regression (15):** known failure types.
- **Held-out (20):** independent for retrieval; **no longer independent** for H09, H14 and H17, which were
  inspected.
- **Test 1 (14):** evaluated twice.
- **Test 2 (12):** evaluated once.

---

## 1. Prompt engineering (20 %)

| Item | Status |
|---|---|
| Requirement | Versioned prompts, documented iterations, grounding, citations, multilingual constraints, refusal |
| Implementation | `prompts/` (4 prompts, 6 versions), `prompts/registry.yaml`, `agents/prompts.py` (loader, `prompt_ref` on every LLM response) |
| Files | `prompts/*/v*.yaml`, `agents/answer.py`, `agents/intent_router.py`, `agents/verification.py`, `docs/PROMPT_ENGINEERING.md` |
| Test evidence | `test_every_prompt_version_parses`, `test_prompt_render_keeps_literal_braces`, `test_llm_fallback_output_is_validated`, `test_verification.py` (28 tests) |
| Measured | grounded_answer v1→v2: accepted 0.667→0.750, language 0.917→1.000; v3: evidence span 1/11→2/11, +7 s, not adopted; FR→AR translation withdrawn after meaning errors |
| Limitations | Small samples (12 questions); combined citation markers "[1, 2]" not parsed; prompts cannot fix ranking errors (M11) |
| Demo | Show `prompts/registry.yaml`, the v1/v2/v3 table, and H14 (an invented figure caught after generation) |
| Missing evidence | Human judgement of answer quality |
| Minimal improvement | None needed for the demo; documentation completed in `docs/PROMPT_ENGINEERING.md` |

## 2. RAG (25 %)

| Item | Status |
|---|---|
| Corpus | 14 registry entries: 13 downloaded and verified from official domains, 12 indexed (1 scan without a text layer), 1 blocked by `robots.txt` (passport application form); SHA-256, URL, retrieval time and official reference in `data/raw/manifest.json`; excluded sources with reasons in `config/sources.yaml` (e.g. idaraty.tn: AI opt-out) |
| Chunking | Structure-aware (272 chunks, median 430 chars) vs recursive (174, median 911) from the same TextBlocks (`rag/chunking.py`) |
| Retrieval | Dense BGE-M3 + Qdrant; agent retriever (routed bilingual expansion, category filter, language bonus); hybrid RRF (raw + expanded dense + BM25) with a cap of 2 chunks per document (`rag/hybrid.py`, production default) |
| Files | `ingestion/`, `rag/`, `agents/retriever.py`, `scripts/evaluate_retrieval.py`, `rag/evaluation.py` |
| Test evidence | `test_evaluation.py`, `test_retrieval_improvements.py`, `test_chunking.py`, `test_extraction.py`, integration retrieval tests |
| Measured (development, 71 labelled) | Hit@5: dense-structure 0.732, dense-recursive 0.817, Phase 2 agent 0.704, hybrid+cap **0.873**; MRR@5 0.575 / 0.642 / 0.577 / **0.675**; R@1 0.465 / 0.528 / 0.493 / 0.549; median ≈ 360–390 ms |
| Measured (held-out, 16 labelled) | Hit@5: dense 0.750, Phase 2 agent 0.562, hybrid+cap 0.750; MRR@5 0.635 / 0.393 / 0.531. **The development gain partly overfitted.** |
| Multilingual | Parallel subset (development): hybrid Hit@5 FR/EN/AR/Derja-Arabic 1.0; Latin-script Derja 0.714 (dense: 0.0) |
| Reliability | Citation validity 100 % in every run; numerical verifier: unsupported numbers 0 on all five sets with the verifier on; FR/AR fee conflict flagged 2/2 |
| Limitations | Small corpus; no official RNE supporting-document checklist; fee-decree questions rank below table rows; Latin-script Derja map tuned on development failures; no reranker |
| Demo | `scripts/demo_ask.py "Quelles pièces fournir pour une première demande de passeport ?"` (verbatim checklist, FR/AR conflict warning, citations) |
| Missing evidence | Human review of labels; larger independent set |
| Minimal improvement | Documented; no further retrieval tuning (would overfit) |

## 3. Multi-agent architecture (25 %)

The agents are **specialised FastAPI endpoints with fixed contracts**, chained by n8n. They are not
autonomous LLM agents: only the Grounded Answer agent (and the router fallback) call an LLM.

| Agent | Endpoint | Input → output | Tools / models | Constraint | Why separate |
|---|---|---|---|---|---|
| Intent Router | `/agents/route` | text → language, category, intent, hints, next agent | keyword rules; Mistral 7B fallback (`intent_router@v1`) | LLM output checked against enums | Cheap, deterministic decision of *which* agent may answer |
| RAG Retriever | `/agents/retrieve` | query + route → cited passages | BGE-M3, Qdrant, BM25, RRF | Category filter; provenance in payload | Retrieval is evaluated on its own (Hit@k) |
| Checklist Builder | `/agents/checklist` | passages → verbatim official sections | Corpus structure; translategemma FR→EN (validated) | No generated requirement | Requirements must be quoted, never generated |
| Grounded Answer | `/agents/answer` | passages → cited answer | Mistral 7B (`grounded_answer@v2`), answerability gate, evidence verifier | Citations and numbers verified | The only generative agent, isolated and verified |
| Form-Filling Helper | `/agents/form-check` | PDF/image → recognised form, field status | PyMuPDF, Tesseract, OpenCV | In memory only, never indexed | Independent modality, testable with official forms |
| Dossier Validator (bonus) | `/agents/dossier-check` | PDF/image → readiness report | reuses Form Helper + Retriever + Checklist Builder | Official requirements only | See section 6 |

- **Orchestration.** `workflows/03_assistant_multi_agent.json`: webhook → "file attached?" → Form Helper; or
  Router → "reply?" → Retriever → "checklist?" → Checklist Builder or Grounded Answer → respond.
- **Recorded traces.** In `docs/traces/`, produced by the real code in-process: per-agent events and timings,
  without user text.
  - FR checklist: route 5 ms → retrieve 590 ms → checklist 6 ms.
  - EN grounded answer: route 5 ms → retrieve 542 ms → answer 43.8 s.
  - Dossier check: form recognition → RAG retrieval (6 passages) → Checklist Builder (no official
    documents list).
- **Justification.**
  - Deterministic parts (routing rules, checklists, forms) can be tested exactly.
  - The generative part is confined to one agent and verified.
  - Errors are isolated per agent: e.g. the test 2 false refusals were traced to the router, not to retrieval.
  - Every answer carries citations from metadata.
- **Costs.** HTTP hops and duplicated context between steps. Routing errors propagate: the LLM fallback
  refuses answerable questions that have no keywords (test 2: 5 of 6).
- **Test evidence.** Integration tests run the n8n webhook end to end (20 tests). Unit tests cover each agent.
- **Missing evidence.**
  - The deployed backend container runs older code: the latest agents are verified in-process, not through
    the containerised n8n chain.
  - Live Telegram is not verified.

## 4. Multimodality (15 %)

| Input | Supported | Evidence |
|---|---|---|
| Digital PDF of the official forms | Yes (geometric check) | Unit tests: blank forms → all fields empty; placeholder in one field → only that field filled |
| Scanned PDF / image (JPEG, PNG, WEBP, TIFF, BMP) | Yes (deskew → Tesseract `ara+fra` → RANSAC homography → ink comparison) | 30/30 synthetic cases (Phase 2); bonus OCR check 6/6 (2 forms × blank, 2 filled, 2 filled rotated 2°, JPEG), run with the current code in a one-off process in the backend container |
| Real photographs | **Not tested** | – |
| Handwriting | **Not tested** (no real filled forms are used) | – |
| Unsupported / unrelated documents | Rejected ("not an official form in my knowledge base") | Unit test with a neutral generated PDF |
| Invalid type / oversize / bad base64 | Rejected with a reason | Unit tests |
| Unreadable fields | Reported as `unreadable`; checkbox and signature sections as `cannot_verify` | Unit test (stubbed helper output) |
| Privacy | In memory only; counts logged, never values; never indexed; n8n stores no executions of workflow 03 | `test_field_values_are_not_reported_or_logged` |

## 5. Demonstration, report and Q&A (15 %)

- **Report.** `report/report.pdf`, at most 8 pages, compiled with pdfLaTeX.
- **Demo materials.** `docs/DEMO_SCRIPT.md`, `docs/DEMO_CHECKLIST.md`, `docs/QA_PREPARATION.md`.
- **Fallback.** `scripts/demo_ask.py --local` (same agent sequence, in-process).
- **Missing:** author names and institution (not in the project files); live Telegram token test; backend
  container rebuild.

## 6. Innovation: Smart Administrative Dossier Validator

| Item | Status |
|---|---|
| Implementation | `agents/dossier_validator.py`, `POST /agents/dossier-check` |
| Supported forms | Official RNE F-001 (natural person) and F-002 (legal entity) |
| Reuse | Form-Filling Helper (recognition, field status), RAG Retriever + Checklist Builder (does an official supporting-document list exist?), official RNE table rows, existing citations and i18n |
| Statuses | Fields: `filled`, `missing`, `unreadable`, `cannot_verify`. Requirements: `supported_by_official_source`, `not_verified`, `official_requirement_unavailable` |
| Official requirements used | Instructions printed on the official forms, quoted verbatim (all data must be completed; missing data leads to rejection; e-mail and mobile number mandatory; missing required documents voids the declaration), and the RNE table rows for the procedure's fee and deadline |
| Key honesty rule | No official RNE supporting-document list exists in the corpus, so the report states that dossier completeness cannot be assessed; nothing is reconstructed by an LLM |
| Tests | `tests/test_dossier_validator.py`: 17 tests (recognition, rejection, filled/missing/unreadable, checklist availability, verbatim official quotes, no validation claims, privacy, 4 languages, Form Helper compatibility); OCR path 6/6 |
| Limitations | Two forms; no handwriting or real-photo evaluation; available through n8n workflow 03 with `mode: "dossier"` (also selectable in Telegram through `/dossier_check`; live Telegram pending a bot token); deployed (2026-10-16), previously not deployed in the running container |
