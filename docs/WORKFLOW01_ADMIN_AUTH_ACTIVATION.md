# Workflow 01 — admin authentication (Phase 0)

Date: 2026-10-18. Branch: `overnight/finalization`. Scope: prepare n8n workflow 01 ("Ingest and index official
documents", id `TnaaIngestIndex1`) to send `X-Admin-Key` to the backend admin endpoints, **keeping it inactive**.
The production backend was not modified and `ADMIN_API_KEY` is **not** active yet.

**Verdict: PATCHED — INACTIVE — READY FOR FUTURE AUTH ACTIVATION**

## 1. Environment verified before the change

| Item | Value |
|---|---|
| n8n | 2.41.3 (`tunisian-admin-assistant-n8n-1`) |
| WF01 | inactive, `versionId 819f02d9-349d-4567-bdeb-ed3f68092b4f`, `activeVersionId null`, 5 executable nodes + 6 sticky notes |
| WF02 | published `f4849a5c…`, 3 executable / 4 notes |
| WF03 | published `af6ad259…`, 17 executable / 10 notes |
| Executions | 0 running |
| n8n credentials | none before this phase |
| Qdrant (production, host port 6343; port 6333 is an older standalone test container) | `official_docs_structure` 272 green, `official_docs_recursive` 174 green |
| Production backend | image `8adaf99…`. **Correction (2026-10-18, Phase B incident):** this image has **no** admin guard; its `/ingestion/run` and `/index/run` run without any key. An earlier version of this row said they answered 403, which was wrong. See `docs/PRODUCTION_DEPLOYMENT_REPORT.md`. |
| Candidate | `tunisian-admin-assistant-backend:rc-20261018b` (same `require_admin` contract: 403 unset, 401 wrong key) |

## 2. Backup (outside Git)

Directory: `C:\Users\Eya Laourine\tna-backups\phase0-workflow01-20261018T092520Z\`

| File | SHA-256 |
|---|---|
| `TnaaIngestIndex1.cli-export.json` (original, version 819f02d9, inactive) | `1807e1e01d86827f19b1d92dfa11d50b773eba10854308d16e5272276286c441` |
| `TnaaIngestIndex1.after.cli-export.json` (patched, version 5193fd21, inactive) | `3977981fb5179ee6c3c3a923a23567d67ca929a805a2e56853eaf68473a0f3a1` |

Also kept: `api\api-check-before.json`, `api\api-apply-before.json`, `api\api-apply-after.json`, `api-final\`.

Restore check: the original export was imported into a disposable n8n 2.41.3 (`--network none`) and re-exported;
id, name, nodes, connections, settings, active, pinData and staticData were identical.

Rollback, if ever needed: `PUT /api/v1/workflows/TnaaIngestIndex1?publishIfActive=false` with the writable fields
of the original export (as `scripts/n8n_patch_workflow01.py` does on failure), or `n8n import:workflow` of the
original export. Either keeps the workflow inactive.

## 3. Credential

- Created with n8n's native credential system (`n8n import:credentials --projectId e8jabjrbSWw1NMoA`),
  type **Header Auth** (`httpHeaderAuth`), id `TnaaAdminKeyCred`, name **TNAA Backend Admin**, header `X-Admin-Key`.
- Stored encrypted in the n8n database (`U2FsdGVkX1…`; neither the header name nor the value appears in clear),
  owned by the same project as the workflows (`credential:owner`).
- Secret: 43 random URL-safe characters generated locally, stored **only** as a Windows DPAPI blob (current user)
  at `%USERPROFILE%\.tnaa-private\admin-api-key.dpapi`. It is the value the backend will later use as
  `ADMIN_API_KEY`. It was passed to n8n through process stdin, never through arguments, files in the repository,
  logs, sticky notes or workflow JSON.
- Secret-absence checks (all negative): patched export, API snapshots, n8n `database.sqlite` + WAL (plaintext),
  n8n container logs, disposable test logs, repository working tree.

**Incident (disclosed):** during the second import attempt a PowerShell quoting failure left a temporary file
`/tmp/tnaa_raw` containing the secret inside the production n8n container (mode 0600, owner `node`) for about two
minutes. It was detected, deleted and confirmed absent; no process read it and it never left the container. The
final import used stdin with a `finally` cleanup; zero temporary files remained. If this exposure is considered
unacceptable, generate a new secret before activation and update both the credential and `.env` (one value, two
places).

Unrelated leftover: earlier Codex n8n-review export files remain in the production n8n container's `/tmp`. They
contain workflow JSON only (no secrets) and were left untouched.

## 4. Patch

Applied with `scripts/n8n_patch_workflow01.py apply` (public API, `publishIfActive=false`; it never calls publish
or activate). Preconditions: live version 819f02d9, inactive, identical to the backup.

| | Before | After |
|---|---|---|
| versionId | `819f02d9-349d-4567-bdeb-ed3f68092b4f` | `5193fd21-3215-495d-8ac4-4d34c592c2fc` |
| active / activeVersionId | false / null | false / null |

Nodes modified (only these two, only these fields):

| Node | Change |
|---|---|
| Download official documents | `parameters.authentication = genericCredentialType`, `parameters.genericAuthType = httpHeaderAuth`, `credentials.httpHeaderAuth = {id: TnaaAdminKeyCred, name: TNAA Backend Admin}` |
| Build chunks and index (both strategies) | same |

Diff of the re-exported workflow: top-level only `updatedAt`, `versionCounter`, `versionId`. Node ids, positions,
URLs, methods, bodies, timeouts, options, sticky notes, connections and settings are identical. `workflow_history`
holds both versions. The proposed file `deploy/proposed/01_ingest_and_index_admin_key.json` (regenerated by
`make_workflow_01_admin_key.py`) has nodes identical to the live export.

Intentional difference: the canonical `workflows/01_ingest_and_index.json` stays **without** credential references.
`tests/test_api_security.py::test_committed_workflows_contain_no_credentials` and the n8n review tests pin the
canonical files; the authenticated variant lives in `deploy/proposed/`. Re-importing the canonical file would drop
the authentication; use the proposed file instead.

## 5. Verification and authentication tests

- WF01: inactive and unpublished after the change and at the final check.
- WF02 / WF03: version ids, published state and node counts unchanged.
- Executions: none during the patch and verification steps (see the deviation below for the later test run).
  **No ingestion or indexing ran; WF01 was never executed on production n8n.**
- Qdrant: 272 / 174 green, unchanged; no writes.
- Production containers (backend, n8n, bridge, qdrant): same images, not restarted.
- Unit tests: `1097 passed, 5 skipped, 41 deselected`.
- **Deviation (disclosed):** the final pre-commit run used plain `pytest`, which also ran the 41 integration tests
  (`1138 passed, 5 skipped`). Their effects on the running stack were:
  - `test_qdrant_roundtrip` created a temporary `test_<uuid>` collection on the production Qdrant instance, wrote
    2 points and deleted it. The official collections were not touched: they stayed at 272 / 174 green, and only
    those two collections exist.
  - Fixture questions and official form files went through the production WF03 webhook and the backend `/agents/*`
    endpoints (read-only). That produced 46 WF03 executions, all soft-deleted by n8n because WF03 saves no
    execution data.
  - Telegram was fully mocked (`httpx.MockTransport`), so no message was sent.
  - None of these tests calls `/ingestion/run`, `/index/run` or WF01. WF01's only execution ever is id 1, from
    2026-10-15.
  - No user data was involved.

Isolated functional test (never against production endpoints): the **live-exported** patched workflow was run in a
disposable n8n 2.41.3 on an internal Docker network (no internet, no production services), with the credential
built from the DPAPI secret, against `deploy/proposed/admin_echo.py` as the `backend` host. That mock accepts
`POST /ingestion/run` and `/index/run` only with the expected key, and downloads and indexes nothing.

| Case | Mock expects | Result |
|---|---|---|
| A | the stored secret | both calls 200, `Run summary` produced, exit 0 |
| B | a different value | 401, workflow fails, exit 1 |

The secret did not appear in any disposable log or output. Containers and the network were removed afterwards.

## 6. Future activation (NOT done; requires approval during the rc-20261018b deployment)

1. Complete production backup Phase A and approve deployment Phase B.
2. Set the key in the git-ignored `.env` from the DPAPI secret (never printed; the previous `.env` is copied to
   `%USERPROFILE%\tna-backups\env\`):
   `powershell -NoProfile -File deploy/Set-AdminApiKeyEnv.ps1`
3. Recreate only the backend with the already-validated image (no build, no pull):
   `docker compose up -d --no-deps --no-build --pull never backend`
4. Verify without side effects. **First confirm that the running image is `rc-20261018b` or later** (`docker inspect`); images
   without `require_admin` (such as `8adaf99`) execute admin POSTs. Only on such a verified image, a `POST /index/run` with
   **no** header must return **401** (not 403); the guard rejects it before the handler runs. Do not send a
   request with the real key to production admin endpoints as a test.
5. WF01 stays inactive. It is run manually only when an ingestion is deliberately approved. Before that run,
   confirm in the n8n UI that both HTTP nodes show the credential **TNAA Backend Admin**.
6. Rollback: remove `ADMIN_API_KEY` from `.env` (or restore the `.env` copy) and recreate the backend the same way.
   Admin endpoints then return 403 again; the n8n credential can stay.

Remaining before any future ingestion: steps 1–5, an approved ingestion window, and a Qdrant snapshot taken
immediately before it.

## 7. Files

- `scripts/n8n_patch_workflow01.py`: check/apply, with automatic restore on any unexpected change.
- `deploy/proposed/make_workflow_01_admin_key.py`, `deploy/proposed/01_ingest_and_index_admin_key.json`:
  credential id `TnaaAdminKeyCred`.
- `deploy/proposed/admin_echo.py`: isolated mock; supports `ADMIN_API_KEY_FILE`.
- `deploy/Set-AdminApiKeyEnv.ps1`: future `.env` step; not executed.
