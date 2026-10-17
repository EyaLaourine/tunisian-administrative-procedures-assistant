# Test results

Recorded on 2026-10-15 on the development machine:
- Windows 11, AMD Ryzen (Family 25 Model 80), 28 GB RAM
- NVIDIA RTX 3050 Laptop GPU, 4 GB VRAM
- Docker Desktop; Ollama on the host

## Automated tests

| Suite | Command | Result |
|---|---|---|
| Unit (no services) | `.venv/Scripts/python -m pytest -m "not integration"` | **94 passed** |
| Integration (stack + host Ollama) | `.venv/Scripts/python -m pytest -m integration` | **11 passed** (146 s) |

Unit tests read the real extracted official corpus and the real official forms where relevant. They skip
when those files are missing. Fixtures use neutral placeholder text only.

The integration tests run through the real n8n webhook (workflow 03):
- the FR passport checklist, including the FR/AR fee-discrepancy warning;
- Derja served from the official Arabic page;
- English with translation;
- the RNE fee table (C 012, 50 TND);
- grounded answers with citations;
- out-of-scope and uncovered procedures;
- the form check on a PDF and on a scanned image;
- the Telegram bridge with a mocked Telegram API calling the real n8n chain.

## Form-Filling Helper on images (OCR path)

The official RNE forms F-001 and F-002 were rasterised and then distorted. Fields were "filled" with the
neutral placeholder text `PLACEHOLDER 12`. The test covers:
- 3 fill states: blank, 2 fields filled, all fields filled;
- 5 image conditions: 200 dpi, 120 dpi, 1° rotation, 3° rotation, perspective warp;
- JPEG compression at quality 70.

| Version | Correct (form recognised and exact set of empty fields) |
|---|---|
| OCR text (words on the dot leader) | 0/8 (unrotated set) |
| Ink comparison, per-axis alignment | 8/8 unrotated, after fixing a sampling-aliasing bug (4/8 before); failed with 1° rotation |
| Ink comparison, RANSAC homography | 29/30 (F-002 at 3° misrecognised as F-001) |
| + deskew before OCR (current) | **30/30** |

This test does not cover real handwriting or real photographs of paper forms.

## Local LLM benchmark

Produced with `scripts/benchmark.py --runs 3` (raw output: `data/evaluation/benchmark.json`).

| Model | GPU share (4 GB VRAM) | Cold load | Warm generation |
|---|---|---|---|
| mistral:latest (7.2B Q4_K_M) | 40 % | 5.4 s | 11.7 tok/s |
| translategemma:4b (Q4_K_M) | 46 % | 11.4 s | 21.3 tok/s |

End-to-end latency through n8n (3 runs, median):

| Path | Agent | Median |
|---|---|---|
| FR passport checklist | checklist_builder | 2.6 s |
| Derja passport checklist (official AR text) | checklist_builder | 2.5 s |
| EN passport checklist (validated FR→EN translation) | checklist_builder | 21.4 s |
| RNE fee question (official table) | checklist_builder | 2.5 s |
| Free question (LLM grounded answer) | grounded_answer | 37.3 s |
| Out of scope (router LLM fallback) | intent_router | 4.8 s |

The deterministic paths are dominated by query embedding (BGE-M3) and model swapping in 4 GB of VRAM.
LLM paths are slower because both generation models are partly offloaded to CPU.

### Correction (2026-10-16): host-side latency artefact

The latencies above were measured with a new HTTP connection per request to `localhost`. On this Windows
host, `localhost` first tries IPv6 (`::1`), and the published Docker ports listen on `127.0.0.1` only. Each
new connection therefore waits about **2.1 s** before falling back:

| Endpoint | `localhost` | `127.0.0.1` |
|---|---|---|
| Qdrant `/collections` | 2335 ms | 232 ms |
| n8n `/healthz` | ~2300 ms | ~240 ms |

Re-measured end to end through n8n with a reused connection, the deterministic paths take **about 0.2 s**
(FR passport checklist 0.18–0.22 s; RNE fee question 0.18–0.20 s), not 2.5 s.

A separate effect observed while an evaluation ran: when generation models occupy the 4 GB GPU, the
embedding model is evicted, and single requests then took 27–112 s. Container-to-container calls (backend →
Qdrant) are not affected by the IPv6 issue. Phase 3 measurements use `127.0.0.1` (see `docs/EVALUATION.md`).

## Not verified

- A live Telegram conversation: no bot token was configured. The bridge was verified against the real
  Telegram API only up to authentication (an invalid token gives HTTP 401, with no token in the output).
  Message handling was verified with a mocked Telegram API.
- Quality evaluation of the grounded answers beyond citation validation: no labelled evaluation set has
  been built yet.

## Phase 3 (2026-10-16)

| Suite | Command | Result |
|---|---|---|
| Unit | `.venv/Scripts/python -m pytest -m "not integration"` | **138 passed** |
| Integration (deployed stack, Phase 2 backend image) | `.venv/Scripts/python -m pytest -m integration` | **11 passed** |
| Full | `.venv/Scripts/python -m pytest` | **149 passed** (124 s) |
| API compatibility of the new code | in-process `TestClient` against live Qdrant/Ollama: `/agents/route` → `/agents/retrieve` → `/agents/checklist` | 3/3 requests HTTP 200, response schema unchanged |

Retrieval and answer-quality evaluation: see `docs/EVALUATION.md`.

## Final reliability update (2026-10-16)

| Suite | Command | Result |
|---|---|---|
| Full suite (unit + integration, including the n8n chain end to end) | `.venv/Scripts/python -m pytest` | **202 passed** (182 unit, 20 integration; 212 s) |

The integration tests ran against the deployed stack, which still runs the Phase 2 backend image. The
backend was not rebuilt because a Telegram bridge container that shares the backend image was running.
The new code was evaluated in-process (`docs/EVALUATION.md` §6).

## Evidence verifier (2026-10-16)

| Suite | Command | Result |
|---|---|---|
| Full suite (unit + integration, including the n8n chain) | `.venv/Scripts/python -m pytest` | **230 passed** (210 unit, 20 integration; 227 s) |
| Verifier regression tests | `.venv/Scripts/python -m pytest tests/test_verification.py` | 28 tests: H14/H17-type, driving licence, valid passport / ID / RNE, supported numbers, source conflict, multilingual, unsupported procedures, disabled topic check |

## Rubric optimisation and Dossier Validator (2026-10-16)

| Suite | Result |
|---|---|
| Full suite `.venv/Scripts/python -m pytest` | **247 passed** (227 unit, 20 integration; 213 s), 0 failed |
| Dossier Validator `tests/test_dossier_validator.py` | 17 passed (official blank forms F-001/F-002 and placeholder-filled test fixtures) |
| Dossier Validator OCR path (one-off process with the current code in the backend container, which has Tesseract; service not modified or restarted) | 6/6 exact field statuses: F-001 and F-002 × {blank, 2 fields filled, 2 filled + 2° rotation}, JPEG |

**Where each part ran:**
- **Integration tests** used the deployed n8n + backend container, which still runs the pre-verifier backend
  image.
- **The verifier and the Dossier Validator** were exercised in-process (unit tests, `scripts/demo_ask.py
  --local/--dossier`, `docs/traces/`), not through the deployed container.

## Backend deployment (2026-10-16, 17:58 local)

| Step | Result |
|---|---|
| Preflight | Docker 29.7.2 running; `docker compose --profile telegram config --quiet` OK; backend and Telegram bridge use separate images (`tunisian-admin-assistant-backend`, `tunisian-admin-assistant-telegram`); Qdrant, n8n, host Ollama healthy |
| Previous backend | Container ran image `2eae87971cb3`, whose layers were no longer in the image store, so `docker commit` failed. The running filesystem was exported and re-imported as `tunisian-admin-assistant-backend:before-rebuild` (`9ced218bc097`, verified to import). The former `latest` (`619abd7db38f`) is also kept as `:latest-before-rebuild`. |
| Build | `docker compose build backend` succeeded: new image `c9c054bde1f9`. Contents verified: dossier validator, verifier, hybrid retrieval, OpenCV, Tesseract. |
| Deploy | Bridge stopped; `docker compose up -d --no-deps --no-build --force-recreate --wait backend`: healthy, clean startup log; n8n, Qdrant and volumes untouched |
| Health (HTTP) | `/health` ok (Qdrant true, Ollama true); n8n → `http://backend:8000/health` 200; Qdrant 272 points; `/agents/dossier-check` listed |
| Runtime settings (in container) | `retrieval_mode=hybrid`, `evidence_verification=True`, `evidence_topic_check=False` |
| Functional checks (`scripts/deployment_check.py`) | **15/15** against n8n and the deployed backend (`data/evaluation/deployment_check.json`) |
| Tests | Unit **227 passed**; integration **20 passed**, 0 skipped (n8n → new backend; it served 92 agent requests) |
| Telegram bridge | Restarted unchanged (image `4fd5cb72bfef`): healthy, 0 restarts, `LIVE_CONNECTIVITY_PENDING` (no token); reaches n8n and the backend (HTTP 200). No messaging tested. |
| Rollback | Not needed; not performed |

**Rollback procedure (if ever needed).**
1. `docker tag tunisian-admin-assistant-backend:before-rebuild tunisian-admin-assistant-backend:latest`
2. `docker compose up -d --no-deps --no-build --force-recreate backend`

## n8n integration of the Dossier Validator (2026-10-16)

| Step | Result |
|---|---|
| Rollback copy | Active workflow 03 exported from the n8n database before the change (`deploy/n8n_rollback/03_active_before_dossier.json`, versionId `05d10ca6…`, identical to the repository file) |
| Change | `workflows/03_assistant_multi_agent.json`: new IF node "Dossier mode?" on the upload branch (`body.mode == "dossier"`) → HTTP node "Dossier Validator" (`/agents/dossier-check`) → "Respond: dossier check". Uploads without `mode` keep the unchanged "Form-Filling Helper" path. 13 → 16 nodes. |
| Deployment | `n8n import:workflow` (workflow 03 only) → `publish:workflow` → n8n restarted. Export from n8n after restart: active, versionId `20d0d2b5…`, 16 nodes, "Dossier mode?" present. Workflow 02 still active. |
| Pre-deployment check | New dossier tests run against the old active workflow: **failed as expected**, which shows the JSON file alone does not change n8n |
| Tests after deployment | Integration **26 passed** (20 existing + 6 new: unchanged form-check contract, dossier report, scan-like image in Arabic, unrelated document, bridge-contract compatibility, text questions unaffected by `mode`); unit **227 passed** |
| Live checks | `scripts/deployment_check.py` **15/15**; trace `docs/traces/trace_dossier_via_n8n_fr.txt` |
| Telegram bridge | Healthy, 0 restarts, `LIVE_CONNECTIVITY_PENDING`; reaches n8n (HTTP 200) after the n8n restart; code and image unchanged |

**Rollback procedure.**
1. Copy `deploy/n8n_rollback/03_active_before_dossier.json` into `workflows/`.
2. Run `n8n import:workflow --input=/workflows/<file>`.
3. Run `n8n publish:workflow --id=TnaaAssistant01`.
4. Restart n8n.
