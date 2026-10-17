# Phase 2 — Multi-agent assistant

## Flow

```
Telegram ──long polling──▶ telegram-bridge ──POST /webhook/assistant──▶ n8n workflow 03
                                   ▲                                         │
                                   └──────────── {text, agent, ...} ◀────────┤
                                                                             │
   file attached? ── yes ──▶ Form-Filling Helper ─────────────────────────▶ respond
        │ no
        ▼
   Intent Router ── next_agent = reply ──────────────────────────────────▶ respond
        │ checklist / answer
        ▼
   RAG Retriever ──▶ checklist? ── yes ──▶ Checklist Builder ────────────▶ respond
                          └─────── no ───▶ Grounded Answer ──────────────▶ respond
```

Every agent is a FastAPI endpoint (`backend/agents_api.py`); n8n chains them (`workflows/03_assistant_multi_agent.json`).
The same webhook serves HTTP clients, which is how the chain is tested without Telegram.

| Agent | Endpoint | Implementation | LLM use |
|---|---|---|---|
| Intent Router | `POST /agents/route` | `agents/intent_router.py`, `agents/language.py` | Only when keyword rules find no procedure (`intent_router@v1`, JSON, validated against enums) |
| RAG Retriever | `POST /agents/retrieve` | `agents/retriever.py` | None (BGE-M3 embeddings + Qdrant) |
| Checklist Builder | `POST /agents/checklist` | `agents/checklist_builder.py`, `agents/corpus.py` | Only FR→EN translation of verbatim items (`translate_items@v1`, validated) |
| Grounded Answer | `POST /agents/answer` | `agents/answer.py` | `grounded_answer@v2`, citations validated |
| Form-Filling Helper | `POST /agents/form-check` | `agents/form_helper.py` | None (Tesseract OCR + OpenCV, local) |

`GET /agents/prompts` lists prompt versions. Every LLM-produced response carries `prompt_ref` (e.g. `grounded_answer@v2`).

## Design decisions

**Deterministic first.** Requirements, fees and deadlines are never generated. The Checklist Builder uses
retrieval only to identify the *document and scenario* (e.g. "passport, first issue or renewal, resident
abroad"), then reads the complete official sections (conditions, documents, place, deadline) verbatim from
`data/processed/extracted/<doc_id>.json`. Chunk boundaries therefore never truncate a checklist.

**Parallel official versions.** The Ministry of the Interior publishes the passport guide in French and
Arabic with identical structure (7 scenarios, same section sequence). The builder aligns them and:
- serves Arabic and Derja users the official Arabic text, and French and English users the French text;
- compares the stamp-duty amounts of both versions and warns when they differ. This is a real case: the
  FR page states 20/60 TND and the AR page 25/80 TND for residents in Tunisia.

**Languages.** EN / FR / AR / Derja are detected deterministically. Derja is detected in Arabic script and in
Latin script with digits, e.g. "chnowa lezmni bech nbaddel el karta". Interface strings are written per
language in `agents/i18n.py`. Official text is never paraphrased.

**Machine translation is limited to FR→EN.** `translategemma:4b` was evaluated on the official national ID
guide. FR→AR output passed format validation but changed meaning: "veuve" (widow) became "العوراء"
(one-eyed woman), and "timbre" became "الطوابق" (floors). Arabic and Derja users therefore receive the
verbatim French text with a note when no Arabic official version exists. FR→EN output is checked to have the
same numbered lines and the same numbers as the source, and otherwise falls back to the original.

**Grounded answers.** Answers that cite nothing, or cite a passage number that does not exist, are
rejected. The agent then quotes the top passages verbatim. Sources are listed once per document, with page
numbers.

**Business registration (RNE).** No official required-documents checklist exists on the RNE site (see
`config/sources.yaml`, status `not_found`). The builder says so explicitly and quotes the matching rows of
the official formalities table (code, fee, deadline) plus links to the official forms F-001 and F-002.

**Uncovered procedures.** Birth certificates are reported as not covered: the only source found
(idaraty.tn) opts out of AI use in robots.txt.

## Form-Filling Helper

Field templates are derived from the official blank forms (`document_type: official_form`): every
dot-leader line is a field, and its label is the adjacent FR and AR text on that row.

1. **Recognition.** The share of template label tokens found in the upload. Tokens unique to one form
   decide between forms that share most labels.
2. **Digital PDFs.** Geometric check: a word that is not printed on the blank form and lies on a dot leader
   marks the field as filled.
3. **Images and scans.**
   - Deskew by projection-profile search, then OCR with Tesseract `ara+fra`.
   - Fit a RANSAC homography from anchor words and warp the upload onto the official form.
   - Compare the ink in each dot-leader band with the blank form rendered at the same scale.
   - OCR text alone is not used to decide filled vs empty: text written on dot leaders is read merged with
     the dots, at near-zero confidence.

Privacy: uploads are decoded in memory, never written to disk, logged, or indexed. Workflow 03 is
configured not to store execution data (`saveDataSuccessExecution/ErrorExecution: none`), because
executions would contain user questions and files.

Known limits: handwriting has not been tested on real filled forms, because no real personal forms are
used. Strongly curved or folded paper and severe perspective may defeat the alignment. The passport
application form (`interior-passport-application-form`) is not in the corpus.

## Telegram

`telegram_bridge/` uses Bot API long polling, so no public URL, tunnel or open port is needed. The token is
read only from `.env`. Errors are logged by exception type only, because httpx messages contain the URL and
therefore the token. Long answers are split at line boundaries to fit Telegram's 4096-character limit.

## Additions after Phase 2

| Component | Endpoint | Implementation | LLM use |
|---|---|---|---|
| Answerability gate | inside `/agents/answer` and `/agents/checklist` | `agents/answerability.py` | None |
| Evidence verifier | inside `/agents/answer` and `/agents/checklist` | `agents/verification.py` | Topic check for EN/Derja only, and only if `EVIDENCE_TOPIC_CHECK=true` (default off); numerical check is deterministic and on |
| Smart Administrative Dossier Validator | `POST /agents/dossier-check` | `agents/dossier_validator.py` | None; reuses the Form-Filling Helper, RAG Retriever and Checklist Builder |

Since 2026-10-16, workflow 03 routes an upload with `"mode": "dossier"` to `/agents/dossier-check` ("Dossier mode?" IF node); uploads without this field keep the unchanged form-check path. The Telegram bridge sends `mode: "dossier"` on uploads after `/dossier_check` or the Dossier Validation button (`docs/TELEGRAM_DOSSIER_MODE.md`); other uploads keep the form check.
Measurements: `docs/EVALUATION.md` (sections 6–7) and `docs/RUBRIC_COVERAGE.md`.
