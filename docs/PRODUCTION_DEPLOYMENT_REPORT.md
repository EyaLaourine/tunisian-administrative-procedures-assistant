# Production deployment report (Phase B)

Date: 2026-10-18 (all times UTC). Branch: `overnight/finalization`. Plan and backups:
`docs/PRODUCTION_BACKUP_AND_PREFLIGHT.md`, `C:\Users\Eya Laourine\tna-backups\phaseA-20261018T102604Z\`.

**Verdict: DEPLOYED — AUTOMATED CHECKS PASSED — AWAITING MANUAL TELEGRAM ACCEPTANCE**

End-to-end Telegram acceptance is **not** claimed until the owner has tested the bot (section 8).

## 1. Summary

| | Old | New |
|---|---|---|
| Backend (`backend`) | `sha256:8adaf99471c5e5064a09e14ab0e08d56dbbf7e4fd8376c319962b37c5ae4dde0`, container `28862b4efec1` | `sha256:6124980fa90552a86b633d644335771e5039ebe0522f7f1d76f3f828898aaa92` (`rc-20261018b`), started 10:50:21 |
| Telegram bridge (`telegram-bridge`) | `sha256:7eafea6e792df1e0b8646c7f62b72555fe4343c6283d5f09adf0682bb6d84ea1`, container `2571b2a7b3c2` | `sha256:517755a5ad39343ab2f3e0c7f2efc7e46df6831ae6c8aa7917a1d5c59165c23c` (`final-candidate`), container `d8877372e84d`, started 10:52:20 |

- **Phase B timing:** started 10:38:58 (pre-checks). The backend was deployed at 10:50:18 and the bridge at 10:52:17.
  The final verification ran at 10:53:24.
- **Services recreated:** only `backend` and `telegram-bridge`. n8n (started 2026-10-17 11:16), Qdrant (2026-10-15)
  and Ollama were not restarted, nor was any container of another project.
- **Rollback:** not needed, so none was performed.

**An incident happened during the pre-checks and is fully disclosed in section 2.** It ran an unauthorized ingestion
and reindex on production. Qdrant content came out identical to Phase A, and `data/` was restored to Phase A before
deployment.

## 2. Incident: unauthorized ingestion and reindex on the old backend

**What happened.** While recording a baseline, I sent `POST /ingestion/run` and `POST /index/run` (no body, no header,
10 s client timeout) to the then-running backend `8adaf99`. I expected HTTP 403. That image has **no** admin guard
(`/ingestion/run` and `/index/run` have no dependencies), so both requests ran.

| Time (UTC) | Event |
|---|---|
| 10:38:58 | Phase B pre-checks start (all preconditions passed) |
| ≈10:39:05 | Baseline requests: `GET /health/live`, `GET /health/ready` (404) and the two POSTs; the client timed out after 10 s, but the server kept going |
| 10:39:15 | Ingestion starts re-downloading the 14 official sources; `rne-formalities-procedure-table` has changed upstream (`upstream_content_changed`), and a new file `0c41e7364ccf_formalites.html` is written |
| 10:39:15–10:39:36 | RNE documents re-downloaded (same content, already stored) |
| ≈10:39:05–10:39:48 | **Impact window: reindex.** `official_docs_recursive` rebuilt (174 points at 10:39:39); `official_docs_structure` rebuilt (observed at 0 points just before it finished, 272 at 10:39:48). Retrieval through the assistant could be incomplete during this window. |
| 10:39:49–10:41:11 | Ingestion continues with the Ministry of Interior sources (slow site). `interior-passport-application-form` is blocked by robots.txt as configured. At 10:41:11 `data/raw/manifest.json` and `ingestion_log.jsonl` are rewritten. |
| ≈10:40–10:41 | Incident detected and reported; deployment paused. My first diff ran before 10:41:11 and showed only the HTML file. |
| 10:43:51 | HTML file archived (verified). The second diff then showed the manifest and log changes, so I paused again. |
| 10:48 | With approval: manifest and log archived, then restored from Phase A, and the new HTML file removed |
| 10:48–10:50 | Consistency verification (section 3) passed |

**Root cause**
1. `docs/WORKFLOW01_ADMIN_AUTH_ACTIVATION.md` (Phase 0) stated, without verification, that the production backend
   answered 403 on its admin endpoints. I relied on that statement instead of inspecting the deployed image's code
   before sending a state-changing request.
2. I used state-changing POSTs as a "baseline" on production. A guard check must be static, or run in an isolated
   container.

**Corrections made**
- `docs/WORKFLOW01_ADMIN_AUTH_ACTIVATION.md` now says that `8adaf99` has no admin guard.
- `docs/PRODUCTION_BACKUP_AND_PREFLIGHT.md` no longer contains any admin POST check during deployment. Any future
  401 check must first confirm the running image has `require_admin`.
- Both documents state that only `/health` exists (`/health/live` and `/health/ready` are 404 in `8adaf99` and
  `rc-20261018b`).

**Impact**
- **Network:** 14 HTTP fetches to official sources through the normal pipeline (robots.txt respected).
- **Qdrant:** both collections were rebuilt, with an impact window of about 45 s at most. The rebuilt content is
  identical to Phase A (below).
- **Files:** `data/raw` changed in three files, restored as described below. No user data was involved, n8n was not
  touched, and Workflow 01 was not executed.

**Recovery verification**
- **Qdrant:** both collections were compared point by point with the Phase A snapshots, restored into a disposable
  Qdrant on an internal network. The production side was read with a read-only scroll.
  - Result: 272/272 and 174/174 points, identical ids, payloads and vectors, 0 differing points.
  - Verified three times: after the incident, before deployment and after deployment.
- **Incident archive:** `…\phaseA-20261018T102604Z\incident-phaseB-20261018T104351Z\`. `SHA256SUMS` verifies, and
  each copy was compared byte for byte with the production file before any change.

  | Archived file (as found after the incident) | SHA-256 |
  |---|---|
  | `data/raw/rne-formalities-procedure-table/0c41e7364ccf_formalites.html` (161 466 bytes, new upstream version) | `0c41e7364ccf35ec6afcfeb1ca4e2a82b6fa3a354c50af4d3cf4495c70eb2f10` |
  | `data/raw/manifest.json` (pointed the formalities table to the new file; 14 new timestamps; 4 Interior URLs `http` → `https`) | `3c83b625641269cd61766b097a6b2a49f4be14e406d4666dc3fb99ad7ee944db` |
  | `data/raw/ingestion_log.jsonl` (one appended line) | `f6af566b165e480040a7b1c1ba2676a741cc7300414e4d27673aa81e8059c724` |

- **Restore steps:**
  1. Archive checksum verified (`data-config-prompts.tar`, `8fb9b517…`).
  2. Both files extracted to a temporary directory and compared with the Phase A extraction.
  3. Copied next to the originals and swapped in by rename.
  4. The restored manifest points to `540ebb5abd46_formalites.html`; that file exists with SHA-256
     `540ebb5abd469b01e0dce7e731559750d18bf7be0b463a0b6720ac822a48c45c`.
  5. Only then was `0c41e7364ccf_formalites.html` removed.
- **Proof of restoration:**
  - `diff -r` of `data/`, `config/` and `prompts/` against the Phase A archive shows **no differences** (127 files).
  - The manifest has 14 records, and all 13 file references resolve. The 14th, the robots-blocked form, has no
    file, as in Phase A.
  - The ingestion log equals Phase A, and `/health` reports `manifest_records: 14`.
  - No ingestion or indexing log event has occurred since 10:41:11.

## 3. Verified production state before deployment (10:48–10:50)

- **Backups:**
  - the Phase A backup set verifies (20/20 checksums);
  - rollback tags `backend:rollback-20261018` = `8adaf99…` and `telegram:rollback-20261018` = `7eafea6…`;
  - candidates `rc-20261018b` = `6124980f…` and `final-candidate` = `517755a5…` (provenance in the Phase A report).
- **Compose:**
  - project `tunisian-admin-assistant`, working directory `C:\Users\Eya Laourine\tunisian-admin-assistant`;
  - services `qdrant`, `backend`, `n8n` and `telegram-bridge`;
  - the n8n and Qdrant config hashes equal their running containers.
- **Services:**
  - all healthy; Qdrant on host port 6343, while 6333 is the unrelated `rag-finance-pipeline` container;
  - one Telegram poller;
  - WF01 inactive (`5193fd21`), WF02 published (`f4849a5c`), WF03 published (`af6ad259`).
- **Isolated admin-guard check of `rc-20261018b`** (`--network none`, no data mount, empty `ADMIN_API_KEY`, in-process
  `TestClient`): both admin routes depend on `require_admin` and return 403 "Administrative endpoints are disabled".

## 4. Actual deployment commands

Run from `C:\Users\Eya Laourine\tunisian-admin-assistant`; `.env` was not modified.

```bash
docker tag tunisian-admin-assistant-backend:rc-20261018b tunisian-admin-assistant-backend:latest
docker compose -p tunisian-admin-assistant up -d --no-deps --no-build --pull never backend
# backend recreated 10:50:18-10:50:21, healthy at 10:50:28

docker tag tunisian-admin-assistant-telegram:final-candidate tunisian-admin-assistant-telegram:latest
docker compose -p tunisian-admin-assistant --profile telegram up -d --no-deps --no-build --pull never telegram-bridge
# bridge recreated 10:52:17-10:52:20 (old poller stopped first), healthy at 10:52:57
```

Compose output for each was `Recreate → Recreated → Starting → Started` for that single container only.

## 5. Backend verification (no POST to admin endpoints)

| Check | Result |
|---|---|
| Running image | `6124980f…`, healthy, 0 restarts |
| `GET /health` | `{"status":"ok","qdrant":true,"ollama":true,"manifest_records":14}` |
| `GET /health/live`, `/health/ready` | 404 (not implemented in this release; expected) |
| Admin protection (static, inside the running container) | `/ingestion/run` and `/index/run` depend on `require_admin`; `require_admin` fails closed on an empty key; runtime settings: admin key not configured, agent key not configured |
| `ADMIN_API_KEY`, `AGENT_API_KEY` | empty |
| Least-privilege environment | `TELEGRAM_BOT_TOKEN` and `N8N_ENCRYPTION_KEY` are no longer in the backend's environment |
| Backend errors since deploy | 0 ERROR/CRITICAL or traceback lines; 0 ingestion or indexing events |

## 6. n8n smoke tests (workflows 02 and 03, read-only)

Script: `scripts/phaseb_smoke.py` (10 webhook calls); results in
`C:\Users\Eya Laourine\tna-backups\phaseB-20261018\smoke.json`. Expected patterns come from the validated probe
sets. Final run (10:51:59–10:52:01): **9/9 passed**.

| Case | Result |
|---|---|
| WF02 retrieval, `top_k` 3 | 200, 3 passages, each with a citation URL, a 64-hex SHA-256 and text |
| WF02 body without `query` (error handling) | 500 "Error in workflow", the documented pre-existing behaviour (backend 422 behind it) |
| WF03 Arabic (passport duplicate) | answer contains `نظير` |
| WF03 Tunisian Derja (passport duplicate) | answer contains `نظير من جواز سفر` |
| WF03 legal citation, French (beneficial owner) | `Source : … Banque centrale de Tunisie` |
| WF03 legal citation, Arabic (law 2018-52, article 16) | `المصدر: … الفصل 16` |
| WF03 unknown article (error handling) | "je préfère ne pas deviner" |
| WF03 French checklist (two turns) | turn 1 asks "Tu résides en Tunisie ou à l'étranger ?"; turn 2 "En Tunisie" gives `checklist_builder` with "Pièces à fournir" and sources |
| WF03 conversation context (two turns) | the follow-up is answered from the returned context (`intent_router`, the identity card guide) |

**Note on the first run (10:51:20, 8/9 passed).** My single-turn French checklist expectation was wrong: the
assistant first asks where the person lives. The isolated previous release (`final-n8n`) and the isolated rc
(`rc-n8n`) give the same clarification, so this is not a regression. The case was corrected to two turns and the
suite re-run. The two n8n `AxiosError … 422` log lines (10:51:25 and 10:52:00) are the intentional WF02
missing-query test.

## 7. Telegram bridge and final verification (10:53:24)

- **Bridge:**
  - one container on the bridge image (old container replaced, not duplicated); healthy, 0 restarts;
  - log contains `telegram_bridge_started`, and **0** lines matching 409, conflict or poll failure since start;
  - from inside the bridge, `http://n8n:5678/healthz` and `http://backend:8000/health` both return 200;
  - the webhook URL is `http://n8n:5678/webhook/assistant`, and `ASSISTANT_WEBHOOK_KEY` is not set;
  - no Telegram message was sent automatically.
- **Other services:** the backend `/health` is OK. n8n `/healthz` returns 200. Qdrant `/readyz` (port 6343) returns
  200. Ollama 0.40.4 is available.
- **Workflows:** WF01 is inactive (`5193fd21`); WF02 (`f4849a5c`) and WF03 (`af6ad259`) are published and unchanged.
- **Qdrant:** `official_docs_structure` 272 and `official_docs_recursive` 174, the only collections. Point-by-point
  identical to the Phase A snapshots.
- **Files and activity:** `data/` equals Phase A, with no unexpected raw files. No ingestion or indexing has run since
  10:41:11.
- **Other projects:** the unrelated container `qdrant` was not restarted.

## 8. Manual Telegram acceptance (owner, at https://t.me/TunisAdminGuideBot) — PENDING

Send each message in a fresh chat, or after `/start`, and check the expected behaviour.

| # | Message | Expected |
|---|---|---|
| 1 | `Quelles pièces fournir pour renouveler un passeport ?` | Asks whether you live in Tunisia or abroad; answering `En Tunisie` gives the passport checklist ("Pièces à fournir") with an official source |
| 2 | `ما هي الشروط من أجل استخراج نظير من جواز السفر بالنسبة إلى التونسيين المقيمين بالتراب التونسي؟` | Arabic answer about a passport duplicate (`نظير`) with a source |
| 3 | `نحب نطلع نظير من الباسبور وأنا ساكن في تونس، شنوة يلزم؟` | Answer in Arabic script about the passport duplicate, with a source |
| 4 | After a checklist answer: `Et si mon cas ne correspond pas à ce texte ?` | Follow-up handled from the conversation (points to the official guide), not a new unrelated answer |
| 5 | `Quelles autorités compétentes peuvent obtenir les informations sur le bénéficiaire effectif ?` | Legal answer ending with `Source : …` (decree on beneficial owners), mentioning the Banque centrale de Tunisie |
| 6 | `Comment obtenir une carte grise ?` | Polite refusal: procedure not covered by the official corpus (rule-based), with no invented steps |

Also check that replies arrive only once (no duplicate poller) and that messages stay under Telegram's length limit.
**Please report the results; end-to-end acceptance remains pending until then.**

## 9. Warnings and remaining risks (not deployment blockers)

1. **`post-audit-candidate` (old test container) exposes unguarded admin endpoints.** It runs image
   `post-audit-final` (`7254fcf…`), where `/ingestion/run` and `/index/run` have **no** dependencies (verified
   statically; no request sent).
   - It is published on `127.0.0.1:8001`, mounts the **production** `data/` directory, and its `QDRANT_URL` is
     `http://qdrant:6333`, which is the production Qdrant on the shared network. It also holds `TELEGRAM_BOT_TOKEN`.
   - A local POST to `127.0.0.1:8001/index/run` would rebuild production collections, the same incident as above.
   - Recommendation, as soon as you approve (this phase forbids removing the six old containers):
     `docker rm -f post-audit-candidate`, and the other five test containers afterwards.
   - `rc-candidate` and `final-candidate` are guarded (`require_admin`).
2. **Rollback image is vulnerable.** `backend:rollback-20261018` (`8adaf99`) has unguarded admin endpoints. A
   rollback would restore availability but reintroduce the vulnerability.
   - No verified network or proxy control exists yet.
   - If a rollback is ever needed: restore availability, keep port 8000 loopback-only, never POST to admin paths, and
     report it as insecure until a control is verified.
3. **Admin key:** still pending rotation before any activation (Phase A, section 6); it was not rotated or activated.
4. **Upstream change not reviewed:** the RNE formalities table (`rne-formalities-procedure-table`) has changed on the
   official site. The new version is archived, not ingested.
5. **DPAPI-only key backups and no Qdrant API key:** unchanged from Phase A.

## 10. Rollback status

None performed; none required. The procedure is in `docs/PRODUCTION_BACKUP_AND_PREFLIGHT.md`, section 7, subject to
warning 2.
