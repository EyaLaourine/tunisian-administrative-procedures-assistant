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

## 13. Phase C: automatic language detection release (2026-10-18)

**Verdict: PHASE C DEPLOYED — AWAITING MANUAL TELEGRAM ACCEPTANCE**

Release: commit `525830e` (branch `fix/auto-language`); design and isolated validation in
`docs/AUTO_LANGUAGE_DETECTION_FIX.md`. No failure occurred and no rollback was needed.

### Timeline (UTC)

| Time | Step |
|---|---|
| 12:20:10 | Phase C preflight start |
| 12:20:37–12:22 | Backups, restore tests, secret scan (all gates passed) |
| 12:22:59 | Prompt files applied to the production checkout |
| 12:23:09 → 12:23:19 | Backend recreated → healthy |
| 12:23:20–12:23:35 | Read-only smoke test, 9/9 (gate for the bridge) |
| 12:23:41 → 12:24:00 → 12:24:37 | Bridge recreated (old poller stopped first) → started → healthy |
| 12:24:51–12:25:42 | AUTO-language end-to-end checks on production, 17/17 |
| 12:25:57 | Final verification |

### Images

| Service | Before | After |
|---|---|---|
| Backend | `rc-20261018b` `sha256:6124980fa90552a86b633d644335771e5039ebe0522f7f1d76f3f828898aaa92`, container `981da8424bc9` | `rc-20261018-lang` `sha256:cec1028a82e51f48a392a03321eb2694255263357756bc20bb11b0ed0c81d96c`, container `d9ff913e5d78` |
| Telegram bridge | `final-candidate` `sha256:517755a5ad39343ab2f3e0c7f2efc7e46df6831ae6c8aa7917a1d5c59165c23c`, container `d8877372e84d` | `rc-20261018-lang` `sha256:c247749d5f7ffdf75fac02fe33e2df58830b73a9ecf7ede718f1432ccc6b7415`, container `3f73414a7eb7` |

- **Provenance:** both candidates were re-verified before deployment; all copied files (63 and 10) are
  hash-identical to `525830e`.
- **Untouched:** n8n (started 2026-10-17 11:16), Qdrant (2026-10-15), Ollama and the unrelated `qdrant` container
  were not restarted.

### Preflight and backups

Backup folder: `C:\Users\Eya Laourine\tna-backups\phaseC-20261018T122037Z\` (17 files; only the Windows account and
SYSTEM have access; `SHA256SUMS.all` covers 16 files and verifies).

| Backup | Details | Restore verification |
|---|---|---|
| Qdrant `official_docs_structure` | 272 points, `…-2026-10-18-12-20-38.snapshot`, 4 420 096 bytes, SHA-256 `79f0d76a71430d0abbdb1998e31f1c136774f56131e181c23c3f4fac0b9e9310` (equals the server checksum) | Restored into a throwaway Qdrant: 272/272, identical ids, payloads and vectors |
| Qdrant `official_docs_recursive` | 174 points, `…-2026-10-18-12-20-38.snapshot`, 3 365 888 bytes, SHA-256 `19400cef01471addaa85a8d46d619b7ba2b8b25637dbde67c5a5521023a194a2` | 174/174 identical |
| n8n database | `VACUUM INTO` copy, `integrity_check` ok, SHA-256 `d7f033b869d20d5428df76a9ed0be81d7bc2756e174b448e23db7b2b16151797` | Throwaway n8n with `--network none`: 3 workflows equal field by field; the credential decrypts with the backed-up key (unchanged DPAPI backup of Phase A, still equal to the current `.env` key) |
| n8n workflows | `workflows.all.json` plus one file per workflow (01 inactive `5193fd21`, 02 `f4849a5c`, 03 `af6ad259`) | Same as above |
| Data, config, prompts | `files/data-config-prompts.tar`, 127 files, SHA-256 `c31b290287a937f206915b745eba9e368eeaaac14a617e858da940efdb54e48d` | Extracted and compared with production: identical |
| Rollback configuration | `rollback-prompts/registry.yaml` (pre-release registry, SHA-256 `6979e2ca310e5c68efcf644fe8ad5dae7c63bb10e37809733c62f9c6b98efc08`), `compose/docker-compose.yml`, environment variable names only, redacted `docker inspect` of backend and bridge | n/a |

**Secret scan** (values never printed): the admin secret, the n8n encryption key and the Telegram token were
searched in the Git history of the release branches, tracked files, backup metadata and the last 3 hours of
backend, bridge and n8n logs. **0 exposures.** `QDRANT_API_KEY`, `ADMIN_API_KEY`, `AGENT_API_KEY` and
`ASSISTANT_WEBHOOK_KEY` are unset.

### Configuration change

Only the two prompt files required by the release were changed in the production checkout
(`C:\Users\Eya Laourine\tunisian-admin-assistant`). Both are byte-identical to `525830e`:

- `prompts/language_identification/v1.yaml`: new file;
- `prompts/registry.yaml`: one added line, `language_identification: v1`.

`config/`, `docker-compose.yml`, `.env`, `data/` and `workflows/` were unchanged. The production checkout now shows
these two files as uncommitted changes against its branch `codex/final-n8n-workflows` (`be787ca`). This is
intentional, and they equal the release commit.

### Commands executed

```bash
docker tag tunisian-admin-assistant-backend:rc-20261018-lang tunisian-admin-assistant-backend:latest
docker compose -p tunisian-admin-assistant up -d --no-deps --no-build --pull never backend
docker tag tunisian-admin-assistant-telegram:rc-20261018-lang tunisian-admin-assistant-telegram:latest
docker compose -p tunisian-admin-assistant --profile telegram up -d --no-deps --no-build --pull never telegram-bridge
```

### Verification

**Health and configuration**
- Backend: `/health` returns `{"status":"ok","qdrant":true,"ollama":true,"manifest_records":14}`; healthy,
  0 restarts, 0 ERROR or traceback lines.
- Prompts: the new prompt `language_identification@v1` loads, and `language_model_unavailable` was never logged.
- Admin protection (static check inside the running container; no admin request sent): `/ingestion/run` and
  `/index/run` depend on `require_admin`, which fails closed; the admin and agent keys are not configured.

**Telegram bridge**
- Exactly 1 bridge container; the old one was replaced, not duplicated.
- Healthy, 0 restarts, 0 lines matching 409, conflict or poll failure.
- Reaches `n8n:5678/healthz` and `backend:8000/health` (200); no webhook key set.
- The language keyboard offers Auto first.

**n8n, Qdrant and data**
- n8n: `/healthz` returns 200. WF01 inactive (`5193fd21`); WF02 (`f4849a5c`) and WF03 (`af6ad259`) published and
  unchanged.
- Qdrant: `/readyz` returns 200. 272 / 174 points, point-for-point identical to the Phase C snapshot; only the two
  official collections exist.
- Data: `data/` is identical to the Phase C archive, with 14 manifest records and no untracked files.
- Activity: no ingestion or indexing event; Workflow 01 not executed; no Telegram message sent by the tests.

**Smoke tests** (read-only; evidence in `C:\Users\Eya Laourine\tna-backups\phaseC-verification\`)
- `scripts/phaseb_smoke.py` against production workflows 02 and 03: **9/9**.
  - Covered: retrieval citations, WF02 error handling, Arabic and Derja duplicate questions, French and Arabic legal
    citations, unknown-article handling, two-turn French checklist, conversation context.
  - The n8n `AxiosError … 422` log line at 12:23:33 comes from the intentional WF02 missing-query test.
- AUTO-language end to end against production workflow 03, run through the released bridge code (hash-identical to
  the image) with the Telegram API mocked: **17/17 turns**.
  - Covered: FR→AR with procedure isolation (the 4 declared photos are not reused for the duplicate); Latin-script
    Derja with "fi tounes" and "merci" follow-ups; an Arabic-script Derja clarification; a Derja preference with a
    French question (answered in French), "ok", then Auto; refusals in French and in Derja; an RNE code.

### Rollback (not needed; prepared)

Restore only the immediately previous protected release, never `8adaf99`:

```bash
docker tag tunisian-admin-assistant-backend:rc-20261018b tunisian-admin-assistant-backend:latest
docker compose -p tunisian-admin-assistant up -d --no-deps --no-build --pull never backend
docker tag tunisian-admin-assistant-telegram:final-candidate tunisian-admin-assistant-telegram:latest
docker compose -p tunisian-admin-assistant --profile telegram up -d --no-deps --no-build --pull never telegram-bridge
```

**Prompts:** restore `rollback-prompts/registry.yaml` from the Phase C backup to `prompts/registry.yaml`. The extra
`prompts/language_identification/` folder is harmless to `rc-20261018b`, but can be removed for exact consistency.
No Qdrant, n8n or data rollback is required.

### Remaining risks

1. **Manual Telegram acceptance is pending.** The owner checks, without using `/language`:
   - French → Arabic → Derja → English → French;
   - a Latin-script Derja question;
   - "في تونس" or "oui" after a clarification;
   - `/language` → Derja → a French question (answered in French, menus in Derja) → **Auto**.
2. The limitations in `docs/AUTO_LANGUAGE_DETECTION_FIX.md`, section 9:
   - French-only official sources are quoted in French;
   - Latin-script Derja is answered in Arabic script;
   - a bare "oui" or "merci" is routed as before.
3. Unchanged from earlier phases:
   - the admin key still needs rotation before any activation;
   - the RNE formalities table change upstream has not been reviewed;
   - key backups are DPAPI-only;
   - Qdrant has no API key;
   - the `rollback-20261018` image (`8adaf99`) is vulnerable and must not be used.

## 14. Phase D: conversational understanding (backend only, 2026-10-18)

**Verdict: PHASE D DEPLOYED — AWAITING MANUAL TELEGRAM ACCEPTANCE**

Release: commit `5a2f195` (branch `fix/conversational-understanding`); tests and fixture labelling are in `5deea2c`.
Design, root cause and isolated validation are in `docs/CONVERSATIONAL_UNDERSTANDING_FIX.md`. No failure occurred
and no rollback was needed.

### Validation gates

1. **Real transcript: not available.** A workspace search on 2026-10-18 found the four key phrases only in my own
   test files and session history. As instructed, the regression fixture
   (`tests/fixtures/phase_c_acceptance_session.json`) stays **reconstructed**. It now carries
   `evidence_status: RECONSTRUCTED`, a per-turn `text_origin`, and `logged_origin` (production routing metadata
   only):
   - `reported_by_owner`: the exact phrases you quoted: "oui", "merci", "نحب نبدّل الباسبور، شنوة يلزمني؟",
     "Chnowa lezemni bech njadded passport?";
   - `acceptance_checklist`: the other turns.

   No part of it is presented as verbatim production evidence.
2. **Assertion review.** The earlier small-talk tests compared replies with the implementation's own strings, so I
   added **18 requirement-based tests** that check properties only:
   - gratitude gets a one-line acknowledgement of at most 90 characters, in the right script and language, that is
     neither the welcome nor the refusal, with context kept;
   - an affirmation never produces a refusal or a retrieval;
   - an ambiguous change gets a question, with no retrieval and no inherited case;
   - a clear renewal (Latin- and Arabic-script Derja, French, English) stays a renewal;
   - after the clarification, official checklist items appear verbatim from the corpus, with citations.

   Results:
   - unit suite: **1264 passed**, 5 skipped;
   - language tests: 63/63;
   - conversational tests: 104/104.

   Isolated end to end on the identical image (no image file changed since `5a2f195`): conversational 22/22,
   language 26/26, probes 16/16, multilingual identical to baseline (49/49 records).
3. **Production preflight:**
   - backend `rc-20261018-lang` `cec1028a82e5` and bridge `rc-20261018-lang` `c247749d5f7f`, all services healthy;
   - Qdrant 272/174 with only the official collections;
   - data, config and prompts identical to the Phase C archive (prompts equal release `525830e`);
   - rollback image `rc-20261018-lang` present; the candidate's 64/64 files hash-identical to the commit;
   - workflows 01 inactive, 02 and 03 published; Phase C backup set intact.

   **Warning, not a blocker:** the running bridge had logged 5 `telegram_poll_failed` warnings (`TelegramAPIError`
   ×4, `RemoteProtocolError` ×1) at 12:32 and 12:58. They are transient Telegram network errors that recovered
   automatically (messages were answered afterwards, 0 restarts). They are not polling conflicts: a 409 raises
   `PollingConflict` and stops the bridge, and the 409 count is 0. The previous bridge showed the same pattern.
4. **Minimal backup** for this backend-only change, at
   `C:\Users\Eya Laourine\tna-backups\phaseD-20261018T131058Z\` (only your Windows account and SYSTEM have access):
   - `data-config-prompts.tar` (128 files, SHA-256 `cc5186678f2932692163416f20696819ba925a49ffae1cbfa86dabb459913b1c`;
     extracted and identical to production);
   - redacted `inspect.backend-before.json`;
   - `rollback.txt`.

   Qdrant and n8n are not touched by this change. Their Phase C backups (`phaseC-20261018T122037Z`) were
   re-verified and stay valid.

### Deployment

| Time (UTC) | Step |
|---|---|
| 13:10:28 | Preflight start |
| 13:11:11 → 13:11:21 | Backend recreated → healthy |
| 13:11:37–13:12:21 | Smoke test 9/9; conversational end to end 22/22 |
| 13:13:11 | Final verification |

```bash
docker tag tunisian-admin-assistant-backend:rc-20261018-conv tunisian-admin-assistant-backend:latest
docker compose -p tunisian-admin-assistant up -d --no-deps --no-build --pull never backend
```

| Service | Before | After |
|---|---|---|
| Backend | `rc-20261018-lang` `sha256:cec1028a82e51f48a392a03321eb2694255263357756bc20bb11b0ed0c81d96c`, container `d9ff913e5d78` | `rc-20261018-conv` `sha256:d9d9f8ca7962ce6135317a6e7ae9b2e7bd24eb0bfc9d9cd6cd2d00caa84e133c`, container `336b9ea3c8d1` |
| Telegram bridge | `rc-20261018-lang` `c247749d5f7f`, container `3f73414a7eb7` | **unchanged** (same container, started 12:24:00) |

n8n, Qdrant, Ollama and the unrelated `qdrant` container were not restarted. No prompt, workflow, configuration or
data file was changed.

### Verification

- **Backend:** `/health` returns `{"status":"ok","qdrant":true,"ollama":true,"manifest_records":14}`; healthy,
  0 restarts, 0 errors.
- **Admin protection:** checked statically inside the running container. Both admin routes depend on
  `require_admin` (fail-closed), and the admin and agent keys are not configured. No admin request was sent.
- **Bridge:** healthy, 1 container, 0 polling conflicts.
- **n8n:** `/healthz` returns 200. WF01 inactive (`5193fd21`); WF02 (`f4849a5c`) and WF03 (`af6ad259`) published
  and unchanged.
- **Qdrant:** `/readyz` returns 200. Point-for-point identical to the Phase C snapshot (272/174, ids, payloads,
  vectors); only the two official collections exist.
- **Data:** `data/`, `config/` and `prompts/` identical to the Phase D backup; 14 manifest records; no ingestion or
  indexing.
- **Smoke tests** (read-only; evidence in `C:\Users\Eya Laourine\tna-backups\phaseD-verification\`):
  - `scripts/phaseb_smoke.py`: **9/9**. The n8n `AxiosError 422` at 13:11:40 is the intentional WF02 missing-query
    test.
  - Conversational end to end through production workflow 03, with the released bridge code and the Telegram API
    mocked (no real message): **22/22**. Covered:
    - the reconstructed session ("oui" → short reply, not the refusal; "merci" → brief thanks, not the welcome;
      "نحب نبدّل الباسبور" → clarification);
    - yes/no against a pending question (re-ask);
    - Derja ambiguity resolved with "تجديد";
    - "يعطيك الصحة", "thanks", "merci, et pour les frais ?" and a farewell.

### Rollback (prepared; not needed)

```bash
docker tag tunisian-admin-assistant-backend:rc-20261018-lang tunisian-admin-assistant-backend:latest
docker compose -p tunisian-admin-assistant up -d --no-deps --no-build --pull never backend
```

This returns to the Phase C protected backend `cec1028a82e5`. No prompt or data rollback is needed, and
`8adaf99` must never be used.

### Remaining limitations

1. The regression fixture is **reconstructed**, not verbatim (gate 1). Provide the transcript to replace its texts.
2. **Manual Telegram acceptance is pending:**
   - "oui" after an answer, and after a clarifying question;
   - "merci" / "يعطيك الصحة";
   - "نحب نبدّل الباسبور، شنوة يلزمني؟" then "تجديد";
   - "Chnowa lezemni bech njadded passport?";
   - a farewell.
3. A courtesy word inside a substantive message is ignored, not acknowledged separately. A bare "oui" with nothing
   pending gets a generic follow-up offer.
4. Transient Telegram network warnings occur occasionally, as before, and recover automatically.
5. Unchanged from earlier phases:
   - French-only sources are quoted in French;
   - Latin-script Derja is answered in Arabic script;
   - the admin key still needs rotation before any activation;
   - the RNE upstream change has not been reviewed;
   - key backups are DPAPI-only;
   - Qdrant has no API key.

## 15. Phase E: multilingual UX fixes (backend only, 2026-10-18)

**Verdict: PHASE E DEPLOYED — AWAITING MANUAL TELEGRAM ACCEPTANCE**

Release: commit `d994df7` (branch `fix/phase-e`). Root causes, coverage matrix and isolated validation are in
`docs/PHASE_E_FULL_FUNCTIONAL_VALIDATION.md`. No failure occurred and no rollback was needed.

### Preflight (15:08:21 UTC; all gates passed)

- **Candidate:** `rc-20261018-e` `sha256:69d7a7faab1bd9b474bde6c16f3ffe2c31b276a622b28a30c88cbdeea42ec1de`. Its
  64/64 image files are hash-identical to `d994df7`, and no image file has changed since.
- **Production:**
  - backend `rc-20261018-conv` `d9d9f8ca7962` (container `336b9ea3c8d1`) and bridge `rc-20261018-lang`
    `c247749d5f7f` (container `3f73414a7eb7`), both healthy;
  - 1 bridge container, 0 polling conflicts;
  - WF01 inactive (`5193fd21`), WF02 (`f4849a5c`) and WF03 (`af6ad259`) published;
  - Qdrant 272/174 with only the official collections;
  - data, config and prompts identical to the Phase D backup.
- **Rollback image:** `rc-20261018-conv` present.
- **Backups:** the Phase C and Phase D sets re-verified.
- **Warning, not a blocker:** the running bridge had logged 12 `telegram_poll_failed` warnings since 12:24 UTC.
  All are transient Telegram network errors (`TelegramAPIError`, `RemoteProtocolError`), with 0 restarts and 0
  conflicts; the healthcheck requires a successful poll within 20 minutes, and it stayed healthy.
- **Minimal backup**, at `C:\Users\Eya Laourine\tna-backups\phaseE-20261018T150851Z\` (only your Windows account
  and SYSTEM have access):
  - `data-config-prompts.tar`, 128 files, SHA-256
    `cc5186678f2932692163416f20696819ba925a49ffae1cbfa86dabb459913b1c`. It is identical to the Phase D archive,
    confirming no data, configuration or prompt change, and extracts identical to production.
  - redacted `inspect.backend-before.json` and `rollback.txt`.

### Deployment

| Time (UTC) | Step |
|---|---|
| 15:09:04 → 15:09:14 | Backend recreated → healthy |
| 15:09:36–15:11:44 | Smoke test 9/9; Phase E end-to-end verification 30/30 |
| 15:12:07 | Final verification |

```bash
docker tag tunisian-admin-assistant-backend:rc-20261018-e tunisian-admin-assistant-backend:latest
docker compose -p tunisian-admin-assistant up -d --no-deps --no-build --pull never backend
```

| Service | Before | After |
|---|---|---|
| Backend | `rc-20261018-conv` `sha256:d9d9f8ca7962ce6135317a6e7ae9b2e7bd24eb0bfc9d9cd6cd2d00caa84e133c`, container `336b9ea3c8d1` | `rc-20261018-e` `sha256:69d7a7faab1bd9b474bde6c16f3ffe2c31b276a622b28a30c88cbdeea42ec1de`, container `629c78df05ac` |
| Telegram bridge | `rc-20261018-lang` `c247749d5f7f`, container `3f73414a7eb7` | **unchanged** (same container, started 12:24:00) |

n8n, Qdrant, Ollama and the unrelated `qdrant` container were not restarted. No prompt, workflow, configuration or
data change was made.

### Post-deployment verification

- **Backend:** `/health` returns `{"status":"ok","qdrant":true,"ollama":true,"manifest_records":14}`; healthy,
  0 restarts, 0 errors.
- **Admin protection:** checked statically in the running container. `/ingestion/run` and `/index/run` depend on
  `require_admin` (fail-closed), and the admin and agent keys are not configured. No admin request was sent.
- **Bridge:** unchanged and healthy, 1 container, 0 polling conflicts.
- **n8n:** `/healthz` returns 200; WF01 inactive, WF02 and WF03 published, all versions unchanged.
- **Qdrant:** `/readyz` returns 200. Point-for-point identical to the Phase C snapshot (272/174, ids, payloads,
  vectors); only the official collections exist.
- **Data:** `data/`, `config/` and `prompts/` identical to the Phase E backup; 14 manifest records; no ingestion or
  indexing.
- **Privacy:** the placeholder value from the uploaded test files appears 0 times in backend logs.
- **LLM use:** 0 LLM route-classifier calls during the whole verification.

**Smoke and regression tests**, read-only, with Telegram mocked and no real message sent (evidence in
`C:\Users\Eya Laourine\tna-backups\phaseE-verification\`):
- `scripts/phaseb_smoke.py` against production WF02 and WF03: **9/9**. The n8n `AxiosError 422` at 15:09:41 is the
  intentional WF02 missing-query test.
- Phase E end to end through production WF03, with the released bridge code: **30/30 turns**. Covered: passport,
  CIN, RNE (codes, documents, guidance, forms), document checks (PDF, OCR image, missing fields, unreadable,
  corrupt, unsupported) and a legal question without an act.

| Phase E fix | Production result |
|---|---|
| 1. `يعطيك الصحة` (in a French conversation) | "يعيشك، مرحبا بيك! كان عندك سؤال آخر، أنا هوني." (rules; conversation language kept) |
| 2. `yaatik saha` | the same Derja acknowledgement |
| 3. "je veux savoir le lieu de depot" after a passport answer | place section with official sources; **no fee-discrepancy warning**. The warning still appears for "et les frais ?". |
| 4. "Je veux changer ma carte d'identité" | clarification: "Quel cas vous concerne : première carte, renouvellement, changement de données, ou remplacement après perte, vol ou détérioration ?"; "oui" re-asks; "perte" resolves |
| 5. "Que contient le formulaire F-001 ?" | routed by rules to `business_registration` / answer (no out-of-scope refusal). A specific printed-content question returns official extracts; the generic question gets the "not found, no guess" reply. |
| Corrupt PDF | "Je n'ai pas pu lire ce fichier : le PDF est endommagé ou illisible…" (no English fragment) |

Isolated regression evidence from the identical image, before deployment:
- unit suite 1327 passed;
- coverage 60/60, Phase D conversational 22/22, language 26/26;
- probes 16/16, WF02 5/5;
- multilingual evaluation identical to baseline (49/49);
- error recovery 2/2.

### Rollback readiness

The rollback image is present (`rc-20261018-conv` = `d9d9f8ca7962`) and was not needed:

```bash
docker tag tunisian-admin-assistant-backend:rc-20261018-conv tunisian-admin-assistant-backend:latest
docker compose -p tunisian-admin-assistant up -d --no-deps --no-build --pull never backend
```

- **Other rollback:** no data, prompt or workflow rollback is needed.
- **Backups:** the Phase C full backups and the Phase E minimal backup are verified.
- **Never** use `8adaf99` or other unguarded images.

### Remaining limitations

1. **Manual Telegram acceptance is pending:**
   - "يعطيك الصحة" and "yaatik saha" in a French conversation;
   - "je veux savoir le lieu de depot" after a passport answer;
   - "Je veux changer ma carte d'identité" then "perte";
   - "Que contient le formulaire F-001 ?";
   - a corrupt or unreadable file.
2. **Form content questions:** printed-content questions are answered only when they match a printed block;
   otherwise the reply is "not found, no guess".
3. **Unavailable passport form:** a question about the robots-blocked passport application form gets the passport
   clarification, without stating that the form is unavailable.
4. **Conflict detection:** extracted values are not checked against each other (not implemented).
5. **Navigation buttons:** after a courtesy message in another language, the buttons stay in the conversation
   language (bridge behaviour, unchanged).
6. **Transient Telegram network warnings:** these keep occurring and recover automatically.
7. **Unchanged from earlier phases:**
   - the Phase C session fixture is reconstructed;
   - French-only sources are quoted in French;
   - the admin key still needs rotation before any activation;
   - the RNE upstream change has not been reviewed;
   - key backups are DPAPI-only;
   - Qdrant has no API key.


## 16. Phases F + G: real Telegram fixes and Interior CIN/passport forms (backend + data, 2026-10-18)

**Verdict: PHASES F + G DEPLOYED — ALL PRODUCTION CHECKS PASSED**

- **Release:** image built from commit `3d84557` (branch `fix/phase-g`), which contains the Phase F commits `ccd1cdc` and `476daff`. Branches were not pushed or merged.
- **Design and validation:** `docs/PHASE_F_REAL_TELEGRAM_REGRESSION.md` and `docs/PHASE_G_INTERIOR_FORMS.md`.
- **Outcome:** no rollback was needed.

### Preflight (all gates passed; repeated at 18:55 UTC)

- **Production before:** backend `rc-20261018-e` `sha256:69d7a7faab1b…`, healthy, 0 restarts, 14 manifest records.
- **Candidate image:** `rc-20261018-g` `sha256:4d79b517a8902e093d32ac9821eba594942de1b928a10d976fb346c27d735d86`.
  - Revision label `3d8455733a22`.
  - 66/66 image files hash-identical to the commit; no secret-like files.
  - `/ingestion/run` and `/index/run` fail closed.
- **Data:** production `manifest.json` and `sources.yaml` were byte-identical to the pre-Phase G commit, and prompts were identical.
- **Change set:** exactly four items, `config/sources.yaml`, `data/raw/manifest.json` and the two template folders.
- **Candidate manifest:** 15 records, every file hash and size verified, both new entries consistent with the registry.
- **Services:**
  - WF01 inactive (`5193fd21`), WF02 (`f4849a5c`) and WF03 (`af6ad259`) published;
  - one bridge container, 0 polling conflicts;
  - Qdrant 272/174 points.
- **Wording review:**
  - administration fields are never reported;
  - conditional fields are labelled "if applicable";
  - signature and checkboxes are listed for manual checking;
  - the bridge's "no legal validity" notice appears in FR, EN, AR and Derja;
  - no field is called legally mandatory, and form validity is not asserted.
- **Backup** at `C:\Users\Eya Laourine\tna-backups\phaseG-20261018T182136Z\` (owner and SYSTEM only):
  - `data-config-prompts.tar`, 128 files, SHA-256 `cc5186678f29…`, identical to the Phase E archive; it extracts identical to production;
  - compose file, service and image states, redacted backend inspect, workflow states, Qdrant metadata, `rollback.txt`, `SHA256SUMS`.
  - The first permission change on the backup left its files unreadable. They were reset to inherit the folder ACL (owner and SYSTEM), and the checksums were verified afterwards.

### Deployment

| Time (UTC) | Step |
|---|---|
| 19:09:06 | `docker tag …:rc-20261018-g …:latest`; `docker compose -p tunisian-admin-assistant up -d --no-deps --no-build --pull never backend` → container `fa3fe6bd1c59`, healthy, 14 records |
| 19:09–20:16 local | Paused: auto mode refused the file copies ("Production Deploy"). The backend ran Phase G code with Phase E data, which is equivalent to the Phase F behaviour. |
| 19:16–19:17 | Template folders copied, hashes verified; `sources.yaml` and then `manifest.json` written to `.tmp` and renamed. `/health` → 15 records (manifest reloaded on mtime, no restart). |
| 19:17:30–19:22:49 | Production verification |

Image first, then data: the Phase E code never ran with the new forms.

| Item | Before | After |
|---|---|---|
| Backend | `rc-20261018-e` `69d7a7faab1b`, container `629c78df05ac` | `rc-20261018-g` `4d79b517a890`, container `fa3fe6bd1c59` |
| `config/sources.yaml` | 14 approved entries | + `interior-national-id-application-form` (= `3d84557`) |
| `data/raw/manifest.json` | 14 records, passport form without file | 15 records (= `3d84557`) |
| `data/raw/interior-national-id-application-form/1ccece129f68_01.pdf` | – | sha256 `1ccece12…d2fe63` |
| `data/raw/interior-passport-application-form/7e667ead4386_02.pdf` | – | sha256 `7e667ead…98168d` |
| Bridge, n8n, Qdrant, Ollama, prompts, RNE templates | | **unchanged** |

### Production verification (actual production results)

Run with `verify_prod_g.sh`:
- only user-level webhook calls, never admin endpoints;
- Telegram API mocked inside a throwaway container, so no real chat received anything;
- synthetic documents with neutral placeholder text, plus the blank official forms.

Evidence is in `C:\Users\Eya Laourine\tna-backups\phaseG-verification\` (`SHA256SUMS`).

| Check | Production result |
|---|---|
| Phase F + G session (bridge → WF03 → backend) | **30/30** |
| Coverage | **60/60** |
| Conversational | **22/22** |
| Language (FR/AR/Derja/EN) | **26/26** |
| Defect probes | **16/16** |
| Phase B smoke (WF02 + WF03) | **9/9** |
| WF02 retrieval with valid official citations | **5/5**, median 438 ms |
| `/health` | ok, `manifest_records: 15` |
| n8n | WF01 inactive, WF02/WF03 published, same versions |
| Qdrant | point-for-point identical to the Phase C snapshot (272/174, 0 differences) |
| Bridge | same container `3f73414a7eb7` and image `c247749d5f7f`, started 12:24:00, 0 restarts, 0 conflicts |
| Data | only the four intended items differ from the backup |
| Backend log (771 lines) | 0 placeholder text, 0 base64, 0 form labels, 0 errors |

The data comparison in the script first reported "31 unexpected differences". This was a script error: `tar` read the `C:/` path as a remote host, so the archive was never extracted. Redone with `/c/`, it found exactly the four intended changes.

**Forms recognised in production:**
- CIN (01.pdf):
  - blank: 10 applicant fields listed, 3 "if applicable", "7 champs réservés à l'administration ont été ignorés";
  - required-only completed copy: none missing;
  - scanned JPEG PDF and photo: recognised by OCR, none missing.
- Passport (02.pdf):
  - blank: 10 / 4 / 14 ignored;
  - fully completed copy: none missing;
  - blank photo: recognised by OCR.
- RNE F-001 (PDF, partially filled PDF) and F-002 (OCR image): recognised.
- Unrelated PDF and blank image: refused, with the four supported forms listed. Corrupt PDF: the localised "unreadable" message.

**Phase F behaviour in production:**
- Derja "قداش تاخو وقت؟" and Arabizi → processing time; "قداش نخلص؟" → fees.
- "Je veux immatriculer une entreprise" and fees without a legal form → the legal form is asked.
- SARL → row RNE C 012 with its official fee.
- F-001 and F-002 content questions → printed content.
- Passport and CIN form download → official links (`uploads/imprimes/02.pdf`, `01.pdf`).
- An article question after a SARL turn does not inherit the SARL context.

### Rollback readiness

Not needed. The procedure is prepared in `phaseG-20261018T182136Z\rollback.txt`, in the reverse order, data first:
1. Extract `config/sources.yaml` and `data/raw/manifest.json` from `data-config-prompts.tar`.
2. Remove the two template folders.
3. `docker tag tunisian-admin-assistant-backend:rc-20261018-e tunisian-admin-assistant-backend:latest`, then the same `compose up` command.
4. Expect 14 records.

The rollback image `rc-20261018-e` = `69d7a7faab1b` is present. **Never** use `8adaf99` or other unguarded images.

### Remaining limitations

1. **Not yet tested manually:** the Phase F and G behaviour has not been checked by hand in the real Telegram chat.
2. **OCR margin:** scanned passports scored as low as 0.508 against the 0.5 threshold in isolated tests, so poor photos may still be refused. Short entries on wide lines in 150-dpi scanned PDFs can be falsely reported empty (CIN: 3 fields in 2 of 36 isolated cases; RNE has the same pre-existing limitation).
3. **Interpretations:** the conditional field roles and the passport "حرر بـ … في" role are interpretations of the printed labels. The forms print only the signature as mandatory.
4. **Provenance:** byte identity of the stored forms with the server files cannot be verified, because robots.txt disallows fetching them. Language and date stay unknown, and applicability is unverified.
5. **Search index:** the two forms are not in the Qdrant index; no ingestion or indexing was run.
6. **Unchanged from Phase E:** transient Telegram network warnings, admin key rotation, DPAPI-only key backups, Qdrant without an API key.
