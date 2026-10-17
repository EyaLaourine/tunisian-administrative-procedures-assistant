# Final implementation audit (2026-10-17)

**Type:** independent, evidence-based audit. Audit only: no production code, workflow, container, Qdrant
collection, dataset, prompt or model setting was changed, and no Telegram message was sent.

**Companion documents:**
- `ARCHITECTURE_VERIFICATION.md`: deployed architecture.
- `TECHNICAL_GAP_REGISTER.md`: gaps G-01…G-16 with reproduction steps.
- `ACADEMIC_RUBRIC_COMPLIANCE.md`: rubric and defence questions.

## 1. Executive summary

The Tunisian Administrative Procedures Assistant is a **real, running, local system**:
- **Orchestration:** n8n workflow 03 (16 nodes, active, identical to the repository export) routes every
  request to six specialised FastAPI agent services.
- **RAG:** retrieval runs over 12 indexed official documents (446 chunks, two chunking strategies) in
  Qdrant, with BGE-M3 embeddings, hybrid dense+BM25 fusion, a deterministic answerability gate and a numeric
  verifier.
- **Answers:** checklists are quoted verbatim from official guides. Mistral 7B writes cited answers;
  TranslateGemma translates FR→EN.
- **Uploads:** official RNE forms (PDF/PNG/JPEG/photo) are analysed by template matching with Tesseract OCR,
  and a deterministic Dossier Validator builds a readiness report.
- **Interfaces:** Telegram is **live**. Authentication succeeded, and 4 real text messages were answered on
  2026-10-17. A local web page and a CLI serve as fallbacks.

Four reliability problems were reproduced in production:
- **CRITICAL (G-01):** on the Telegram request path, every RNE fee/deadline question receives an empty
  reply. The same question without dialogue context is answered correctly.
- **CRITICAL (G-02):** a legal question was answered with a fabricated provision and an invented quotation,
  behind a valid official citation. No safeguard caught it.
- **HIGH:** legal answers misattribute articles (G-03) and lose the legal subject across turns (G-05).
- **HIGH:** fixes for most of these exist in the repository, but they are **not deployed**. The repository
  differs from production in 8 files, and there is no version control (G-04).

The reported evaluation (84 + 20 questions) is reproducible from its result files and honestly reports
held-out overfitting. However, it predates the dialogue layer, does not exercise the Telegram request
shape, and its labels are not human-reviewed (G-06). **Citation validity, 100 % in every run, is not
evidence of correctness.** The earlier audit's purposive manual review found 17 incorrect and 8 incomplete
answers among 51 failure-targeted cases.

**Overall status: PARTIALLY VERIFIED.** The architecture and mandatory requirements are met. Answer
correctness is reliable for guide checklists and context-free RNE rows, and unreliable for legal texts and
for RNE on Telegram.

## 2. Verified architecture (summary)

```
Telegram (live) / web fallback / CLI → n8n webhook (workflow 03)
  ├─ upload ─┬─ form-check (OCR/template) ──────────────┐
  │          └─ mode=dossier → dossier-check ───────────┤
  └─ text → route (rules + dialogue, LLM fallback)      │
            ├─ reply (greeting / uncovered / clarify) ──┤→ respond
            └─ retrieve (hybrid) → checklist | answer ──┘
Backend: FastAPI · Qdrant 1.19 · Ollama (bge-m3, mistral 7B Q4, translategemma 4B) on a 4 GB GPU
```

Details, Mermaid diagram, failure paths and design-vs-deployment differences:
`ARCHITECTURE_VERIFICATION.md`.

## 3. Requirement-by-requirement compliance

| Area | Requirement | Status | Evidence / note |
|---|---|---|---|
| A n8n | Deployed workflow; active; nodes | VERIFIED | `TnaaAssistant01` active, 16 nodes, `activeVersionId` = `versionId`; 02 active (3 nodes); 01 inactive |
| A | Definitions match deployment | VERIFIED | Node parameters and connections identical to `workflows/03_*.json` |
| A | Real orchestration, not only forwarding | VERIFIED (limited) | 4 IF branches and inter-agent data hand-off. The branching decision comes from the backend router. |
| A | Error handling | FAILED | No `onError`, no retry, no error workflow (G-10) |
| A | Persistence/privacy | VERIFIED | Execution data not saved (`saveData*: none`) |
| B Prompts | Versioned templates, variables, constraints | VERIFIED | 9 versions, registry, JSON schemas, `prompt_ref` returned |
| B | Runtime vs unused | VERIFIED | Active: intent_router v1, grounded_answer v2, translate_items v1, dialogue_understanding v3. Unused: grounded_answer v1/v3, dialogue v1/v2, evidence_topic (disabled). |
| B | Injection resistance | PARTIALLY VERIFIED | One probe ignored the injection; untrusted-data clauses exist in 2 prompts; no systematic test |
| B | Experimental comparison | PARTIALLY VERIFIED | v1/v2/v3 on 12 items only |
| C RAG | Discovery → download → provenance | VERIFIED | Registry (18 entries), robots/AI opt-out respected, SHA-256 manifest, TLS kept |
| C | Parsing / OCR in ingestion | PARTIALLY VERIFIED | Text-layer PDF + HTML table parsing; scanned decree excluded (no ingestion OCR) |
| C | Chunk → embed → index | VERIFIED | 272 / 174 points; BGE-M3 1024-d cosine |
| C | Retrieval / ranking | VERIFIED | Hybrid RRF k = 60, per-document cap; no reranker |
| C | Grounded generation and citation verification | PARTIALLY VERIFIED | Citation index range and numeric checks only; fabricated content passes (G-02) |
| D Corpus | Indexed vs excluded clearly separated | VERIFIED | 12 indexed; 6 not indexed, each with a reason |
| D | Applicability | VERIFIED as "unverified" | No document is claimed to be in force |
| E Chunking | Two strategies, parameters | VERIFIED | Structure ≤ 1200 characters (min 200) vs recursive 1000/150 |
| E | Reproducible experiments | VERIFIED (files) | `retrieval_results_*.json` match the report numbers (Hit@5 0.873 from `retrieval_results_improved.json`). Not re-executed today. |
| F Agents | Specialised components with contracts | VERIFIED | Six endpoints, Pydantic models |
| F | Autonomous multi-agent behaviour | NOT VERIFIED (not implemented) | Fixed pipeline; no planning or negotiation |
| G Multimodal | PDF / image / photo → field status | VERIFIED | 8/8 upload/dossier integration tests passed today against production n8n (Telegram mocked) |
| G | Handwriting / real photos / audio | UNVERIFIED / not implemented | No dataset; no audio |
| H Models | Local models, roles, timeouts | VERIFIED | bge-m3, mistral 7B Q4_K_M, translategemma 4B; LLM timeout 300 s; LLM failure → passage fallback |
| H | Hardware justification | PARTIALLY VERIFIED | 4 GB GPU; Mistral partly offloaded; latency 23–176 s observed |
| I Evaluation | ≥ 40 questions, held-out, baselines | VERIFIED | 84 + 20 + 41 + 846 coverage cases |
| I | Labels human-reviewed | FAILED | `human_review: pending` on all 84 |
| I | Covers the deployed Telegram path | FAILED | Results predate the dialogue layer (G-06) |
| I | Semantic correctness measured | PARTIALLY VERIFIED | Only narrow fact checks (281/480) and 51 purposive reviews |
| J Reliability | Unsupported-answer refusal | PARTIALLY VERIFIED | Uncovered procedure refused correctly; invented legal content not refused (G-02) |
| J | Numeric verification | VERIFIED (narrow) | Works for figures absent from the passages; blind to article roles |
| K Security | Secrets | VERIFIED | Token only in `.env` (not displayed); httpx logging silenced; services bound to 127.0.0.1 |
| K | Logs / privacy | VERIFIED | Bridge and backend logs contain metadata only; uploads processed in memory |
| K | Input validation | VERIFIED | Type, size, signature and base64 checks in the bridge, proxy and backend |
| K | API authentication | NOT IMPLEMENTED | Backend and webhook unauthenticated (localhost-only binding) |
| K | Host exposure | FAILED (host) | A stray, unrelated Qdrant listens unauthenticated on 0.0.0.0:6333 (G-11) |
| L Telegram | Live connectivity | VERIFIED (text) | `telegram_bridge_started` and 4 `telegram_message_answered` events |
| L | Live uploads / dossier | UNVERIFIED live | Covered by mocked-Telegram integration tests only |
| L | Per-user isolation | VERIFIED (private) / FAILED (groups) | In-process check (G-13) |
| L | Expiry / cancel / language | VERIFIED (unit tests) | 30-minute TTL, `/cancel` clears the session; 92 bridge unit tests |
| M E2E | Text → answer via Telegram | PARTIALLY VERIFIED | Live for checklist and router replies; RNE empty (G-01) |
| M | PDF / image → form check / dossier | VERIFIED (mocked Telegram) | Integration tests |
| M | Multi-turn grounded follow-up | FAILED for the legal subject (G-05); WORKS for passport clarification | Probes |
| N Reproducibility | README, Compose, pinned dependencies, workflow export, model pull | VERIFIED | Pinned Python packages and images; `ollama pull` documented |
| N | Version identity | FAILED | No git; repository ≠ deployed image (G-04) |
| O Completeness | Hard-coded answers / mocks in production | None found | Replies are built from extracted official text or LLM output; mocks exist only in tests |

## 4. Verified implementation vs claims

| Claim | Verdict |
|---|---|
| "Five agents orchestrated by n8n" | True as specialised services; not autonomous agents |
| "Faithfulness 1.0" | True for the lexical metric used (numbers and items present). Not semantic faithfulness (G-02). |
| "Hit@5 0.873 dev, 0.750 held-out" | Matches the result files |
| "Telegram not live / token pending" (report and docs) | Outdated: Telegram is live |
| "Dossier Validator integrated in n8n and Telegram" | True (production workflow and bridge `/dossier_check`) |
| Post-audit fixes (repository code, candidate results 602 cases) | Not in production. The candidate results come from an isolated stack (ports 8001/5679). |

## 5. Critical defects

See `TECHNICAL_GAP_REGISTER.md`:
- **CRITICAL:** G-01, G-02.
- **HIGH:** G-03, G-04, G-05, G-06.

## 6. Deployment status (snapshot, about 14:30 UTC)

All four project services are healthy:
- backend, created 11:30 UTC;
- n8n, container created 2026-10-15 and running for about 3 h; workflow 03 last updated 2026-10-17
  11:16 UTC;
- Qdrant, up 41 h;
- Telegram bridge, live.

An isolated candidate stack (backend :8001, n8n :5679), started by another workstream, was running and
shared Ollama during the audit.

## 7. Reproducibility assessment

**Good:**
- pinned Python dependencies and images;
- Compose file with healthchecks;
- workflow JSON exports;
- `ollama pull` steps;
- ingestion and index commands;
- evaluation scripts with result files;
- tests: 821 unit tests passed today on repository code; integration tests need the stack.

**Gaps:**
- no git history and no tagged release; the deployed image differs from the repository;
- a host Ollama outside Compose (an optional profile exists);
- n8n publication is a manual CLI step;
- the hardware requirement (4 GB GPU, observed partial offload) is not stated as a minimum.

Another developer could rebuild a working system, but not provably the deployed one.

## 8. Prioritised recommendations

1. **Before the demo.** Decide on the candidate fixes:
   - **Deploy:** first run the full regression and the 190-case dialogue group on production.
   - **Do not deploy:** run RNE questions only through the web/CLI path, and say so.
2. Avoid live legal-article questions, or add exact article lookup and refuse when the article is absent
   (G-02).
3. Correct the Telegram-status statements in the docs (G-12). In the defence, state "Telegram live for
   text; uploads tested with mocked Telegram".
4. Stop or bind the stray Qdrant to localhost (G-11). Stop the candidate stack during the demo (G-14).
5. Initialise git and tag the demo state (G-04).
6. After the deadline:
   - re-evaluate with the Telegram request shape;
   - human-review a label sample;
   - add n8n error branches;
   - key sessions per user in groups.
