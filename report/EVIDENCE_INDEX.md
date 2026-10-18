# Evidence index for the technical report (state of 18 October 2026)

This index maps every metric and deployment claim in `report/main.tex` to its source. Annex B of the PDF has
the same identifiers.

**Evidence levels:**
- **I:** implemented (code and unit tests).
- **Iso:** isolated evaluation (a separate stack).
- **P:** automated production verification (HTTP through production workflow 03, Telegram API mocked).
- **M:** manual Telegram observation.
- **L:** live read-only inspection.

| Id | Level | Claims in the report | Source |
|---|---|---|---|
| E1 | P | Deployed backend `rc-20261018-g` = `sha256:4d79b517a8902e093d32ac9821eba594942de1b928a10d976fb346c27d735d86`, commit `3d84557`; 15 manifest records; WF01 inactive, WF02/WF03 published; manual Telegram test of this release pending | `docs/PRODUCTION_DEPLOYMENT_REPORT.md` §16 (commit `2c188bc`) |
| E2 | P | Production verification, 18 Oct 2026, 19:17:30–19:22:49 UTC: Phase F+G session 30/30, coverage 60/60, conversational 22/22, language 26/26, defect probes 16/16, smoke 9/9, WF02 retrieval 5/5; forms recognised; 0 test values in backend log | `data/evaluation/production_phaseFG_20261018/` (`summary.txt`, `phasefg.json`, `cov.json`, `conv.json`, `lang.json`, `probes.json`, `smoke.json`, `SHA256SUMS`); original copy in `%USERPROFILE%\tna-backups\phaseG-verification\` (local) |
| E3 | P | Pre-deployment backup and rollback procedure | `%USERPROFILE%\tna-backups\phaseG-20261018T182136Z\` (local; `rollback.txt`, `SHA256SUMS`) |
| E4 | I | Unit tests: 1406 collected, 1399 passed, 7 skipped, 0 failures, 0 errors; 41 integration tests deselected | `data/evaluation/production_phaseFG_20261018/unit_tests_2c188bc.xml` (run on `2c188bc`, whose code is identical to `3d84557`; command `pytest -m "not integration"`) |
| E5 | Iso | Interior CIN/passport recognition; field roles; 72 Interior scan cases (36 per form) all recognised; 22/24 completed scans exact; lowest score 0.508; RNE scan results unchanged | `docs/PHASE_G_INTERIOR_FORMS.md`; `data/evaluation/production_phaseFG_20261018/isolated_scan_matrix_phaseG.txt`; `agents/form_roles.py`; `tests/test_phase_g_forms.py` |
| E6 | M | Owner's manual Telegram session on `rc-20261018-e` (18 Oct 2026, 15:30–16:04 UTC): defects D1–D6; one LLM-generated answer took 96.9 s | `docs/PHASE_F_REAL_TELEGRAM_REGRESSION.md` §1; `tests/fixtures/phase_e_telegram_session.json` |
| E7 | Iso | Development set 84 questions (71 labelled); held-out 20 (16 labelled); Hit@5 0.873 / MRR@5 0.675 (dev); Hit@5 0.750 / MRR@5 0.531 vs dense 0.635 (held-out); chunking comparison | `docs/EVALUATION.md` §1–2, §6; `data/evaluation/eval_set.jsonl`, `heldout_set.jsonl`, `retrieval_results_improved.json`, `retrieval_results_heldout.json` |
| E8 | Iso | Citation validity 145/145 (dev), 31/31 (held-out); unsupported refused 12/12, 3/4; verified evidence span 0.565 | `docs/EVALUATION.md` §3, §6; `data/evaluation/agent_results_dev_final.json`, `agent_results_heldout_final.json` |
| E9 | Iso | 728-case replay on commit `12828f3`: targeted facts 480/480; RNE with context 190/190 (original production 0/190); legal passage 26/30; intent 691/728; citations in manifest 1547/1547; fabricated provision in original production; integration tests 40/40 | `docs/FINAL_REGRESSION_RESULTS.md` §2–3, §12; `data/evaluation/final_candidate_replay_results.jsonl`; `report/tables/final_regression.tex` |
| E10 | Iso | Prompt before/after experiments | Annex C; `data/evaluation/prompt_experiments/` |
| E11 | L | Live configuration (see below) | Commands and outputs below; `config/sources.yaml`; `data/raw/manifest.json`; `docker-compose.yml` |
| E12 | I | Prompt files, registry and runtime use | `prompts/`; `scripts/make_prompt_annex.py`; Annex A |
| E13 | Iso | Latency, final candidate (median of 3 runs), e.g. English checklist 17.1 s | `data/evaluation/final_candidate_latency.json` |
| E14 | Iso | Isolated pre-deployment pass of `rc-20261018-g`: coverage 60/60, conversational 22/22, language 26/26, Phase F+G session 28/29 then 30/30 after correcting a test fixture, probes 16/16, WF02 5/5 | `data/evaluation/production_phaseFG_20261018/isolated_pass_phaseG_summary.txt`, `isolated_phasefg_rerun.log` |

## E11: live read-only inspection (18 October 2026)

No service was changed. The commands only read.

| Command | Output used in the report |
|---|---|
| `curl 127.0.0.1:11434/api/tags`, `/api/version` | Ollama 0.40.4.<br>`mistral:latest`: 7.2B, Q4_K_M, 4.07 GiB.<br>`translategemma:4b`: 4.3B, Q4_K_M, 3.08 GiB.<br>`bge-m3:latest`: 566.7M, F16, 1.08 GiB. |
| `nvidia-smi --query-gpu=name,memory.total` | NVIDIA GeForce RTX 3050 Laptop GPU, 4096 MiB |
| `docker exec <backend> printenv` (key values masked to set/empty) | `LLM_MODEL=mistral:latest`, `EMBEDDING_MODEL=bge-m3`, `EMBEDDING_DIM=1024`.<br>`ADMIN_API_KEY` and `AGENT_API_KEY` empty. |
| Same for the bridge and Qdrant containers | Telegram token set; `ASSISTANT_WEBHOOK_KEY` empty; Qdrant API key empty |
| `docker inspect` (backend, bridge) | User `appuser`, not privileged, no read-only root filesystem, no dropped capabilities |
| `netstat -an` | Listening on 127.0.0.1 only: 5678 (n8n), 6343 (Qdrant), 8000 (backend), 11434 (Ollama) |
| `POST /collections/<c>/points/scroll` (read) on port 6343 | 12 distinct `doc_id`s.<br>`official_docs_structure`: 272 points.<br>`official_docs_recursive`: 174 points. |
| Registry and manifest (Python, read-only) | Registry: 19 entries (15 approved, 2 excluded, 2 not found).<br>Manifest: 15 records; not indexed: `rne-decree-2022-298-2026-upload` (scanned, no text layer), `interior-national-id-application-form`, `interior-passport-application-form`. |
| `workflows/03_assistant_multi_agent.json` settings | `saveDataSuccessExecution: none`, `saveDataErrorExecution: none`, 17 non-note nodes.<br>WF02 has no execution-data override. |
| n8n API `GET /executions` | **403 Forbidden** (key not scoped): whether WF02 executions are stored is **not verified** |

## Code facts used in the report

| Fact | Source |
|---|---|
| Recursive chunks 1000 characters, overlap 150 | `rag/chunking.py` (`recursive_chunks`) |
| Structure-aware chunks: max 1200 characters, min 200 characters | `rag/chunking.py` (`structure_chunks`) |
| RRF k = 60; 20 candidates per list; BM25 k1 = 1.2, b = 0.75 | `rag/hybrid.py` |
| Per-document cap `max(2, round(5 × 0.4))` = 2 | `agents/retriever.py`, `backend/settings.py` (`retrieval_max_per_doc_ratio`) |
| Upload limit 10 MB; request limit 15 MB (413) | `backend/settings.py`, `backend/main.py`, `docker-compose.yml` |
| Admin endpoints fail closed without `ADMIN_API_KEY` | `backend/main.py` (`require_admin`) |
| Bridge sessions expire after 1800 s; httpx logging silenced | `telegram_bridge/bridge.py` |
| Language model fallback only for Latin-script messages of at least 4 words without markers | `agents/language.py` (`resolve_language`) |
