# Production backup and deployment preflight (Phase A)

Date: 2026-10-18 (backups taken at 10:26 UTC). Branch: `overnight/finalization`.

Scope: verified backups and deployment preflight only. Nothing was deployed or restarted. Workflow 01 was not
activated, no ingestion ran, and no n8n credential or workflow was changed.

## 1. Production inventory (read-only checks)

Compose project `tunisian-admin-assistant`. Working directory and config file:
`C:\Users\Eya Laourine\tunisian-admin-assistant\docker-compose.yml`. That checkout is at `be787ca` with a clean
working tree.

| Service | Container | Image ID | Started (UTC) | Restarts | Health |
|---|---|---|---|---|---|
| backend | `tunisian-admin-assistant-backend-1` | `8adaf99471c5…` (`:latest`) | 2026-10-17 11:30 | 0 | healthy |
| telegram-bridge | `tunisian-admin-telegram-bridge` | `7eafea6e792d…` (`:latest`) | 2026-10-17 11:30 | 0 | healthy |
| n8n | `tunisian-admin-assistant-n8n-1` | `fdce8f852ac7…` (`n8nio/n8n:2.41.3`) | 2026-10-17 11:16 | 0 | healthy |
| qdrant | `tunisian-admin-assistant-qdrant-1` | `057ee3a8da76…` (`qdrant/qdrant:v1.19.0`) | 2026-10-15 20:54 | 0 | healthy |

- **Network and volumes:** network `tunisian-admin-assistant_internal`; volumes
  `tunisian-admin-assistant_n8n_data` and `tunisian-admin-assistant_qdrant_data`. The backend bind-mounts
  `./data`, `./config:ro` and `./prompts:ro`.
- **Health:**
  - backend `/health`: `{"status":"ok","qdrant":true,"ollama":true,"manifest_records":14}`;
  - n8n `/healthz` and `/healthz/readiness`: 200;
  - Qdrant `/readyz`: 200;
  - Ollama 0.40.4 on `127.0.0.1:11434` with `bge-m3`, `mistral` and `translategemma:4b`.
- **Qdrant (production, host port 6343):** `official_docs_structure` 272 points and `official_docs_recursive` 174
  points, both green, 1024-d cosine. These are the only collections, so no temporary collection remains.
  - Port 6333 belongs to an unrelated container `qdrant` (Compose project `rag-finance-pipeline`), which was not
    touched.
  - No Qdrant API key is configured; the port is bound to 127.0.0.1 only.
- **Workflows (n8n API):**

  | Workflow | State | Version | Nodes |
  |---|---|---|---|
  | `TnaaIngestIndex1` (01) | inactive, `activeVersionId` null | `5193fd21` | 5 + 6 notes; both HTTP nodes reference `TnaaAdminKeyCred` |
  | `TnaaRetrieveApi1` (02) | published | `f4849a5c` | 3 + 4 notes |
  | `TnaaAssistant01` (03) | published | `af6ad259` | 17 + 10 notes |

- **Telegram:** a single poller, `tunisian-admin-telegram-bridge`.
  - The backend never polls Telegram; only `backend/settings.py` declares the token field.
  - No host Python process runs `telegram_bridge` or `pytest`.
- **Earlier integration-test run (41 tests):** no unintended production change was found.
  - The temporary Qdrant `test_<uuid>` collection is gone, and the official counts are unchanged.
  - The 46 WF03 executions are soft-deleted (`deletedAt` set; WF03 saves no execution data) and none is in
    progress.
  - No file in the production `./data` mount changed. WF01's only execution ever is id 1, from 2026-10-15.
- **Side test containers** (not production; none was touched): `rc-candidate`, `final-candidate`,
  `post-audit-candidate`, `rc-n8n`, `final-n8n` and `post-audit-n8n`.
  - All are attached to `tunisian-admin-assistant_internal`.
  - None holds the aliases `backend`, `n8n`, `qdrant` or `telegram-bridge`, so production name resolution is
    unaffected.
  - See the risks in section 10.

## 2. Backups

Root: `C:\Users\Eya Laourine\tna-backups\phaseA-20261018T102604Z\` (outside Git, 72 MB, 20 files). Only the
Windows account `Eya Laourine` and SYSTEM can access it. `SHA256SUMS.all` covers every file, and
`sha256sum -c SHA256SUMS.all` passes.

### Qdrant (`qdrant\`)

Snapshots were created through the Qdrant API and downloaded. The size and SHA-256 equal the values Qdrant
reported, and point counts were identical before and after.

| Collection | Points | Snapshot file | Size (bytes) | SHA-256 |
|---|---|---|---|---|
| `official_docs_structure` | 272 | `official_docs_structure-2291018569016737-2026-10-18-10-26-05.snapshot` | 4 432 384 | `1d184d2cc2be9464f0f5d86c6630e2260be962c6a1fa767a0a60d4c50e78c2ef` |
| `official_docs_recursive` | 174 | `official_docs_recursive-2291018569016737-2026-10-18-10-26-05.snapshot` | 3 361 792 | `47b92fb65dd7180d791eead824907139984e740ac6df68a896f89d3795be650d` |

The same snapshot files also remain in the production Qdrant volume (`/qdrant/snapshots`), as a second copy.

### n8n (`n8n\`)

| File | Content | SHA-256 |
|---|---|---|
| `database.sqlite` | consistent copy made with `VACUUM INTO` on a read-only connection; `integrity_check` = ok | `801cbc7c01da5e85ff2a2173f5f93ae3386f05a40025ec44ac55f4d16615f49c` |
| `workflows.all.json` | `n8n export:workflow --all` | `1281e86b3de1b5f59ef5d1fd118979116703c90bc2998b3e414d4d37676f2106` |
| `workflow.TnaaIngestIndex1.json` | 01, inactive, `5193fd21-3215-495d-8ac4-4d34c592c2fc` | `80de7d69631b14bad5c477ff142920b08cc9dc5d77fd0fcdc11fd9b9bdf6e307` |
| `workflow.TnaaRetrieveApi1.json` | 02, published, `f4849a5c-a045-4ff3-a757-23912814e11e` | `25cba5b8923dcf6fb217a623feb00dc325508495a44603fadb07fa4289f6e76a` |
| `workflow.TnaaAssistant01.json` | 03, published, `af6ad259-9044-4947-82da-a584a0fce72c` | `e5dd6cdfe1df3d0c440d691a162571f82745e8630e8aaafed85b70724541ad5f` |

- **Database contents:** 3 workflows; workflow history (01: 5 versions, 02: 2, 03: 3); the encrypted credential
  `TnaaAdminKeyCred`; 1 user; 1 API key record.
- **Sensitivity:** treat the database copy as sensitive, because it holds the user's password hash and the API key
  record.
- **Temporary files:** the export files written in the container's `/tmp` were removed after copying.

**Encryption material (separate from the database backup).** `N8N_ENCRYPTION_KEY` is stored with Windows DPAPI
(current user) at `%USERPROFILE%\.tnaa-private\n8n-encryption-key.20261018T102604Z.dpapi`.
- The key in `.env`, the key in the running container and the key in the volume's `config` file are identical.
- The DPAPI round trip was verified. Key fingerprint (SHA-256 prefix): `ccd953deb79a`.
- A DPAPI copy of the full production `.env` is at `%USERPROFILE%\.tnaa-private\env.20261018T102604Z.dpapi`.
- **Limitation:** DPAPI files can be decrypted only by this Windows user on this machine. For disaster recovery,
  also keep `N8N_ENCRYPTION_KEY` in your password manager. Without it, the n8n credential cannot be decrypted.

### Docker rollback tags

Both tags are new; no existing tag was moved.

| Tag | Image ID | Equals running container |
|---|---|---|
| `tunisian-admin-assistant-backend:rollback-20261018` | `sha256:8adaf99471c5e5064a09e14ab0e08d56dbbf7e4fd8376c319962b37c5ae4dde0` | yes |
| `tunisian-admin-assistant-telegram:rollback-20261018` | `sha256:7eafea6e792df1e0b8646c7f62b72555fe4343c6283d5f09adf0682bb6d84ea1` | yes |

### Configuration and files (`compose\`, `files\`)

- `compose\docker-compose.yml`, SHA-256 `d39b75b31f71b80b25914d60b93f53412b705ec8d86be782edd4ef251a1b509b`.
- `compose\env.names-only.txt`: variable names only, values redacted. The names are `APP_ENV LOG_LEVEL DATA_DIR
  SOURCES_REGISTRY QDRANT_URL QDRANT_API_KEY QDRANT_COLLECTION_PREFIX OLLAMA_URL EMBEDDING_MODEL EMBEDDING_DIM
  LLM_MODEL HTTP_USER_AGENT HTTP_TIMEOUT_SECONDS MAX_DOWNLOAD_BYTES DEFAULT_CRAWL_DELAY_SECONDS MAX_UPLOAD_BYTES
  N8N_ENCRYPTION_KEY N8N_HOST_PORT GENERIC_TIMEZONE QDRANT_HOST_PORT BACKEND_HOST_PORT TELEGRAM_BOT_TOKEN`.
  `ADMIN_API_KEY`, `AGENT_API_KEY` and `ASSISTANT_WEBHOOK_KEY` are absent, so they are empty.
- `compose\inspect.<container>.json`: `docker inspect` of the 4 production containers, with every environment value
  redacted.
- `files\data-config-prompts.tar`: `data/`, `config/` and `prompts/` of the production checkout (127 files,
  46 786 560 bytes), SHA-256 `8fb9b517305f418f82d46cec5509239db7e6d53be7c279892732652218b7ced8`. It contains official
  documents, extracts, evaluation data and samples only; there are no user uploads.

## 3. Restore verification (isolated, disposable services; nothing restored into production)

| Backup | Test | Result |
|---|---|---|
| Qdrant snapshots | fresh `qdrant:v1.19.0` on a Docker `--internal` network, started with `--snapshot <file>:<collection>` for both files; every point compared (id, payload, vector) with a read-only scroll of production | 272/272 and 174/174 points, identical ids, payloads and vectors, both green, 1024-d cosine |
| n8n database + encryption key | fresh `n8n 2.41.3` with `--network none`; the database copy plus the key (written through stdin as `~/.n8n/config`); `export:workflow --all` compared with the backup export | 3 workflows; name, nodes, connections, settings, active, versionId, activeVersionId, pinData and staticData all equal; 01 inactive, 02/03 active |
| Credential decryption | `export:credentials --decrypted` inside the disposable container; only SHA-256 hashes compared, and the file deleted immediately | `TnaaAdminKeyCred` (X-Admin-Key) decrypts with the backed-up key and equals the stored admin secret |
| File integrity | `sha256sum -c SHA256SUMS.all` | 20/20 OK |

All disposable containers and networks were removed. The production credential's encrypted blob is unchanged; its
hash equals the backup.

### Recovery steps (if ever needed)

- **Qdrant**, for one collection:
  `curl -X PUT "http://127.0.0.1:6343/collections/<name>/snapshots/upload?priority=snapshot" -F "snapshot=@<file>"`
  - Alternatively, start Qdrant with `--snapshot <file>:<name>`.
  - Then check the counts (272 / 174).
- **n8n:**
  1. `docker compose stop n8n`.
  2. Copy `database.sqlite` into the `tunisian-admin-assistant_n8n_data` volume as `/home/node/.n8n/database.sqlite`,
     owned by `node`, after removing `database.sqlite-wal` and `-shm`.
  3. Make sure `.env` still has the same `N8N_ENCRYPTION_KEY` (DPAPI copy above).
  4. `docker compose up -d --no-deps n8n`.
  5. Check that 01 is inactive and 02/03 are published.
  - **Lighter option for workflows only:** `n8n import:workflow --input=<workflow.*.json>`. Imported workflows are
    inactive, so 02/03 must then be published again.
- **Files:** `tar --force-local -xf data-config-prompts.tar` in the checkout.

## 4. Release candidates

| Image | ID | Provenance check |
|---|---|---|
| `tunisian-admin-assistant-backend:rc-20261018b` | `sha256:6124980fa90552a86b633d644335771e5039ebe0522f7f1d76f3f828898aaa92` | All 62 files the Dockerfile copies are hash-identical to `overnight/finalization` HEAD: `requirements.txt` plus `backend`, `ingestion`, `rag`, `agents`, `prompts` and `telegram_bridge`. No code changed after `06e8887`, the validated commit. |
| `tunisian-admin-assistant-telegram:final-candidate` | `sha256:517755a5ad39343ab2f3e0c7f2efc7e46df6831ae6c8aa7917a1d5c59165c23c` | 10 files checked. 9 equal HEAD; `backend/settings.py` equals commit `1068cb3`. The only difference from HEAD (`a5aef27`) is the host-side default `ollama_url` (`localhost` → `127.0.0.1`), which the bridge does not use. Bridge code is unchanged since `1068cb3`. |

The images have no provenance labels, so provenance was established by hashing their contents against git.

**Configuration drift.** The checks used `docker compose config --hash` against each container's label, then a
field-by-field comparison by key name:
- **n8n and qdrant:** hashes match the running containers.
- **Backend:** differs only in its environment.
  - The running container still carries the old full `.env`, including `N8N_ENCRYPTION_KEY`, `TELEGRAM_BOT_TOKEN`
    and the `*_HOST_PORT` variables, which it does not use.
  - The current file passes only the backend's own variables, plus `ADMIN_API_KEY` and `AGENT_API_KEY` (empty).
  - Shared values are identical; binds, ports, `extra_hosts` and restart policy are equal.
  - The healthcheck comes from the image's `HEALTHCHECK`.
  - Recreating the backend therefore also removes two secrets from it.
- **Bridge:** differs only by the added empty `ASSISTANT_WEBHOOK_KEY`.
- **Release branch versus the production checkout:**
  - identical `docker-compose.yml`, `config/`, `prompts/` and `workflows/`;
  - `data/` differs only by added evaluation files;
  - `.env.example` documents the three security variables.
- **Overrides:** no `docker-compose.override.*` or `compose.override.*` file exists.

**Compose project and service names** used below: project `tunisian-admin-assistant` (`name:` in the file),
services `backend` and `telegram-bridge` (profile `telegram`). The backend service has no `image:` key, so it uses
`tunisian-admin-assistant-backend:latest`; the bridge uses `tunisian-admin-assistant-telegram` (`:latest`).

## 5. Deployment compatibility

- **WF03 (`af6ad259`) and WF02 (`f4849a5c`):** these are the versions that `docs/N8N_WORKFLOW_COMPATIBILITY.md`
  validated against `rc-20261018b`: compatible, no change required. They are unchanged since.
- **WF01:** inactive. Its authentication is configured (`docs/WORKFLOW01_ADMIN_AUTH_ACTIVATION.md`), but with
  `ADMIN_API_KEY` empty the admin endpoints answer 403 (`require_admin` fails closed on an empty or blank value).
- **`AGENT_API_KEY` and `ASSISTANT_WEBHOOK_KEY`:** unset in `.env`. Compose passes them as empty strings, which the
  code treats as disabled:
  - `require_agent_key` stays open;
  - the bridge sends no `X-Assistant-Key`.
- **n8n changes:** none are required for the backend/bridge release.

## 6. Administrative credential: rotation required before activation

The admin secret briefly existed in a file inside the n8n container during Phase 0, so treat it as exposed and
rotate it before `ADMIN_API_KEY` is ever activated. Nothing was rotated or activated in Phase A.

**Procedure:** `deploy/Rotate-AdminApiKey.ps1`. It was tested only against a disposable n8n restored from this
backup, with `--network none`.
1. It generates 32 random bytes (43 base64url characters).
2. It stores them with DPAPI in `%USERPROFILE%\.tnaa-private\admin-api-key.dpapi`, keeping the old file as
   `admin-api-key.retired-<UTC>.dpapi`.
3. It overwrites the credential `TNAA Backend Admin` (same id, name, type and header) with
   `n8n import:credentials --input=/dev/stdin`. The plaintext never touches a file, an argument or a log, which fixes
   the cause of the Phase 0 incident.

Isolated test results:
- the import succeeded;
- the encrypted blob changed;
- the decrypted value equals the new DPAPI secret and differs from the current one;
- `/tmp` was empty and the secret was absent from the container logs;
- every test artifact was removed.

Order at activation time (a future, separately approved step):
1. `powershell -NoProfile -File deploy\Rotate-AdminApiKey.ps1`
2. `powershell -NoProfile -File deploy\Set-AdminApiKeyEnv.ps1`
3. `docker compose up -d --no-deps --no-build --pull never backend`
4. Check that `POST /index/run` without a header returns 401.

Until step 3, the backend ignores the credential. Admin endpoints stay disabled (403), so the rotation itself has no
production effect.

## 7. Phase B commands (prepared, NOT executed)

Run these from `C:\Users\Eya Laourine\tunisian-admin-assistant` in Git Bash. Keep `.env` unchanged for the initial
deployment.

**1. Deploy the backend** (about 10–30 s of interruption; WF03 returns its 503 error branch meanwhile):

```bash
docker image inspect tunisian-admin-assistant-backend:rc-20261018b --format '{{.Id}}'   # expect sha256:6124980fa905...
docker tag tunisian-admin-assistant-backend:rc-20261018b tunisian-admin-assistant-backend:latest
docker compose -p tunisian-admin-assistant up -d --no-deps --no-build --pull never backend
```

**2. Check backend health:**

```bash
docker inspect tunisian-admin-assistant-backend-1 --format '{{.Image}} {{.State.Health.Status}} {{.RestartCount}}'  # 6124980f..., healthy, 0
curl -s http://127.0.0.1:8000/health                                   # {"status":"ok","qdrant":true,"ollama":true,...}
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8000/index/run   # 403 (admin disabled; nothing runs)
docker exec tunisian-admin-assistant-backend-1 printenv | cut -d= -f1 | grep -cE '^(TELEGRAM_BOT_TOKEN|N8N_ENCRYPTION_KEY)$'  # 0
```

**3. Test the published n8n endpoints** (UTF-8 JSON sent from Python):

```bash
.venv/Scripts/python -c "import httpx;r=httpx.post('http://127.0.0.1:5678/webhook/retrieve',json={'query':'pièces à fournir passeport','top_k':3},timeout=120);print(r.status_code,len(r.json()))"   # 200 3
.venv/Scripts/python -c "import httpx;r=httpx.post('http://127.0.0.1:5678/webhook/assistant',json={'text':'Quelles pièces fournir pour renouveler un passeport ?','language':'fr'},timeout=900);print(r.status_code,str(r.json())[:300])"  # 200, checklist with citations
```

**4. Deploy the Telegram bridge** (up to 60 s; Compose stops the old poller before starting the new one, so only
one poller runs):

```bash
docker image inspect tunisian-admin-assistant-telegram:final-candidate --format '{{.Id}}'   # expect sha256:517755a5ad39...
docker tag tunisian-admin-assistant-telegram:final-candidate tunisian-admin-assistant-telegram:latest
docker compose -p tunisian-admin-assistant --profile telegram up -d --no-deps --no-build --pull never telegram-bridge
```

**5. Check bridge health:**

```bash
docker inspect tunisian-admin-telegram-bridge --format '{{.Image}} {{.State.Status}} {{.RestartCount}}'   # 517755a5..., running, 0
docker ps --format '{{.Names}} {{.Image}}' | grep -c telegram        # 1 (single poller)
# health turns "healthy" after the first poll cycle (start_period 60 s):
docker inspect tunisian-admin-telegram-bridge --format '{{.State.Health.Status}}'
docker logs --since 5m tunisian-admin-telegram-bridge 2>&1 | grep -iE "error|conflict|traceback" | head   # empty
```

**6. Acceptance tests** (read-only Q&A through WF03; they do not write to Qdrant):

```bash
cd "C:/Users/Eya Laourine/tna-overnight"
mkdir -p "C:/Users/Eya Laourine/tna-backups/phaseB-acceptance"
"C:/Users/Eya Laourine/tunisian-admin-assistant/.venv/Scripts/python" scripts/defect_probes.py http://127.0.0.1:5678/webhook/assistant "C:/Users/Eya Laourine/tna-backups/phaseB-acceptance/probes.json"   # 16/16
"C:/Users/Eya Laourine/tunisian-admin-assistant/.venv/Scripts/python" scripts/multilingual_eval.py --url http://127.0.0.1:5678/webhook/assistant --out "C:/Users/Eya Laourine/tna-backups/phaseB-acceptance/multilingual.json"   # 0 failures
```

Then the owner sends the demo messages on Telegram: French, Arabic and Derja text, one PDF, and one image. Do
**not** run `pytest -m integration` against production (it creates a temporary Qdrant collection).

**7. Rollback** (each step is independent):

```bash
docker tag tunisian-admin-assistant-backend:rollback-20261018 tunisian-admin-assistant-backend:latest
docker compose -p tunisian-admin-assistant up -d --no-deps --no-build --pull never backend
docker tag tunisian-admin-assistant-telegram:rollback-20261018 tunisian-admin-assistant-telegram:latest
docker compose -p tunisian-admin-assistant --profile telegram up -d --no-deps --no-build --pull never telegram-bridge
curl -s http://127.0.0.1:8000/health; docker inspect tunisian-admin-telegram-bridge --format '{{.Image}}'
```

- **Workflows and Qdrant:** the release changes neither, so no rollback is needed for them (backups in section 2).
- **Environment after rollback:** the rolled-back containers will get the current least-privilege environment, not
  the old full `.env`. This was checked against the settings the old image (`8adaf99`) declares. Each is either
  passed by Compose or absent from `.env` today, so it is already at its default. The only exception is
  `TELEGRAM_BOT_TOKEN`, which the backend never uses. Behaviour is therefore unchanged.

## 8. Risks and open points

1. **Side test containers on the production network:** `rc-candidate`, `final-candidate`, `post-audit-candidate`
   and the three `*-n8n` containers. `post-audit-candidate` holds `TELEGRAM_BOT_TOKEN` in its environment. It does
   not poll, but it is an unnecessary copy of a secret. Recommendation: remove them after Phase B (they are not
   production):
   `docker rm -f rc-candidate rc-n8n final-candidate final-n8n post-audit-candidate post-audit-n8n`.
2. **Admin key rotation:** pending (section 6). This is required only before activating `ADMIN_API_KEY`, not for
   Phase B.
3. **DPAPI-only key backups:** bound to this Windows user and machine. Store `N8N_ENCRYPTION_KEY` in a password
   manager too.
4. **Integration tests against the live stack:** `pytest` without `-m "not integration"` uses production services
   (see the Phase 0 deviation). Use `-m "not integration"` or isolated services.
5. **No Qdrant API key:** Qdrant is bound to loopback only; this is unchanged by this release.
6. **Bridge provenance:** the bridge image was built from `1068cb3`, not HEAD. The only differing file is irrelevant
   to the bridge (section 4).
7. **Live Telegram acceptance:** not yet done. It is part of Phase B.

No blocker was found.

**READY FOR PHASE B DEPLOYMENT**
