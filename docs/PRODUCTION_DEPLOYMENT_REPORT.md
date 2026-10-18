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

1. **RESOLVED after deployment (section 11): `post-audit-candidate` exposed unguarded admin endpoints.** It ran image
   `post-audit-final` (`7254fcf…`), where `/ingestion/run` and `/index/run` have **no** dependencies (verified
   statically; no request sent).
   - It was published on `127.0.0.1:8001` and mounted the production `data/` directory, **read-only**. (Corrected:
     an earlier version of this report omitted that the mount was read-only.)
   - Its `QDRANT_URL` was `http://qdrant:6333`, which is the production Qdrant on the shared network. A local POST to
     `127.0.0.1:8001/index/run` could therefore have rebuilt production collections.
   - It also held the production `.env` values, including `TELEGRAM_BOT_TOKEN` and `N8N_ENCRYPTION_KEY`.
   - It was removed with approval at 10:58:25 UTC.
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

## 11. Post-deployment security: removal of `post-audit-candidate` (approved)

**Pre-removal checks**

| Check | Result |
|---|---|
| Identity | container `21f7dccf98fa08d3705110c93556ff0b55abdcc7460b62a0c41fb4e63f092660`; image `tunisian-admin-assistant-backend:post-audit-final` (`sha256:7254fcf2…`); no Compose labels; restart policy `no` |
| Ports, network | `127.0.0.1:8001 → 8000`; `tunisian-admin-assistant_internal` (IP 172.19.0.6, no alias) |
| Mounts | bind mounts, all read-only: `tunisian-admin-assistant\data`, `\config` and `\prompts`. These are shared production resources and were left untouched; no volume was involved. |
| Not production | production backend is `981da8424bc9…` (alias `backend`) and the bridge is `d8877372e84d…`; this container had neither alias |
| No production dependency | no production container's configuration or the Compose file references it. Production n8n uses `BACKEND_URL=http://backend:8000`. Its only non-health caller was the test container `post-audit-n8n` (172.19.0.7), last request 2026-10-17 15:32 UTC; 0 requests in the last 2 hours. |
| Production health before | backend, bridge, n8n and Qdrant healthy; 0 restarts |

**Action** (10:58:25 UTC; only this container; no `compose down`; no volume or image removed):

```bash
docker stop post-audit-candidate && docker rm post-audit-candidate
```

**Post-removal verification**
- Port 8001: no listener (`curl` returns 000), and no container publishes 8001.
- Backend `/health`: `{"status":"ok","qdrant":true,"ollama":true,"manifest_records":14}`.
- All 4 production containers are healthy, with unchanged start times and 0 restarts.
- Exactly 1 Telegram bridge container is running.
- n8n `/healthz` returns 200, and Qdrant `/readyz` returns 200.
- Qdrant: 272 / 174 points; only the two official collections.
- The image `post-audit-final` is kept.

**Audit of the five remaining test containers** (static checks only; no admin requests; nothing modified)

| Container | Image | Host port | Unguarded admin routes | Production secrets in environment | Production access |
|---|---|---|---|---|---|
| `rc-candidate` | `backend:rc-20261018b` | 127.0.0.1:8003 | no (`require_admin`, no key, so 403) | none | reads production Qdrant (`qdrant:6333`); read-only mounts of the worktree `data/config/prompts` |
| `final-candidate` | `backend:final-candidate` | 127.0.0.1:8002 | no (`require_admin`, no key, so 403) | none | reads production Qdrant; read-only mounts of the production `data/config/prompts` |
| `rc-n8n` | `n8n 2.41.3` | 127.0.0.1:5681 | n/a | none (own encryption key) | workflows call `rc-candidate:8000` only; no admin paths |
| `final-n8n` | `n8n 2.41.3` | 127.0.0.1:5680 | n/a | none | workflows call `final-candidate:8000` only; no admin paths |
| `post-audit-n8n` | `n8n 2.41.3` | 127.0.0.1:5679 | n/a | none | workflow calls `post-audit-candidate:8000`, which no longer exists, so its webhook now fails (test-only, harmless) |

No remaining test container exposes unprotected administrative endpoints or holds production credentials.

**Residual low risk (resolved in section 12):** the two candidate backends served unauthenticated, read-only
`/agents/*` and `/retrieve` on loopback ports 8002 and 8003, against production Qdrant.

## 12. Cleanup of the five remaining test containers (approved)

**Safety checks before removal** (all passed):

| Container | ID | Image | Host port | Mounts (all bind, read-only; no volumes) |
|---|---|---|---|---|
| `rc-candidate` | `0655101ffd44db31ddcc7e2993d8d2862589d11204a2e6ae68061333f08e0396` | `backend:rc-20261018b` | 127.0.0.1:8003 | worktree `tna-overnight\data`, `\config`, `\prompts` |
| `rc-n8n` | `929220a9ae92be9c8231e41f3284743f518b321fb6c8589d45a1127fa27e32bf` | `n8nio/n8n:2.41.3` | 127.0.0.1:5681 | `deploy/rc_candidate/workflow_02_rc.json`, `workflow_03_rc.json` |
| `final-candidate` | `f11fd350660676b29e1157a007cde2091d6a436435e1b26a8a17fd9f7ab90a12` | `backend:final-candidate` | 127.0.0.1:8002 | production `data`, `config`, `prompts` |
| `final-n8n` | `4157f1d1dd1015e41fe9708d6dd8eecc52f6ae94b584e2c7f2bcb7ead34d9b07` | `n8nio/n8n:2.41.3` | 127.0.0.1:5680 | `deploy/final_candidate/workflow_03_final_candidate_v2.json` |
| `post-audit-n8n` | `fe50693c63eef616651f4caa84f5d70a906e62087862d2186c1c94915e4500a2` | `n8nio/n8n:2.41.3` | 127.0.0.1:5679 | `data/evaluation/post_audit_backup/candidate_workflow.json` |

- **Not part of production:** no Compose project label; restart policy `no`.
- **Network:** all five were on `tunisian-admin-assistant_internal` without aliases.
- **No production dependency:** neither the production containers nor `docker-compose.yml` reference them.
- **Not in use:** the last non-health traffic was my own Phase B comparison request at 10:51:44; there was no n8n log
  activity in the 15 minutes before removal, and no host test process was running.
- **Production health before removal:** backend and bridge healthy, with 0 restarts.

**Action** (11:02:19–11:02:22 UTC; no `compose down`; no image or volume removed):

```bash
docker stop rc-candidate rc-n8n final-candidate final-n8n post-audit-n8n
docker rm rc-candidate rc-n8n final-candidate final-n8n post-audit-n8n
```

**Verification after cleanup**
- **Remaining containers:** only the 4 production containers, plus the unrelated `qdrant` container (project
  `rag-finance-pipeline`), which is untouched and was not restarted. No unexpected container was removed.
- **Network:** the production internal network now contains only `backend-1`, `n8n-1`, `qdrant-1` and
  `telegram-bridge`.
- **Ports:** 8001, 8002, 8003, 5679, 5680 and 5681 have no listener (`curl` returns 000), and no container publishes
  them.
- **Backend:** `/health` returns `{"status":"ok","qdrant":true,"ollama":true,"manifest_records":14}`.
- **Bridge:** healthy, 1 container, 0 409/conflict/poll-failure lines.
- **n8n and Qdrant:** n8n `/healthz` returns 200 and Qdrant `/readyz` returns 200. Production start times are
  unchanged, with 0 restarts.
- **Qdrant points:** 272 / 174; only the two official collections.
- **Workflows:** WF01 inactive (`5193fd21`); WF02 (`f4849a5c`) and WF03 (`af6ad259`) published and unchanged.
- **Kept:** images `backend:rc-20261018b`, `backend:final-candidate`, `backend:post-audit-final` and
  `n8nio/n8n:2.41.3`, and both production volumes.

**Remaining risks after cleanup**
1. The rollback image `backend:rollback-20261018` (`8adaf99`) still has unguarded admin endpoints (warning 2).
2. The admin key still needs rotating before any activation.
3. The upstream RNE formalities table change has not been reviewed.
4. Key backups are DPAPI-only, and Qdrant has no API key.
5. Manual Telegram acceptance is still pending (section 8).
6. Old test images remain on disk. They are not running and can be removed later with `docker image rm`, not prune.
   `post-audit-final` contains the unguarded code and must never be run against the production network.
