# Authenticated n8n update procedure — preparation only

Current status: the private production API key was subsequently configured and authenticated, then an approved attempt stopped after verified rollback of workflow 01. See [the offline normalization correction](N8N_OFFLINE_NORMALIZATION_FIX.md) before preparing any new release. Earlier credential-absence observations below are historical, not the current credential state. No new retry is authorized by this document.

## Decision and evidence

The installed **n8n 2.41.3 public API supports an update that preserves existing workflow and node IDs**. The earlier editor/CLI import blockers do not apply to this route. No modifying HTTP request was sent to production. Production candidates, authentication settings, backend, bridge, Qdrant and Ollama remain unchanged.

Production API root: `http://localhost:5678/api/v1`. Its [API documentation](http://localhost:5678/api/v1/docs/) responds 200; an unauthenticated workflow GET responds 401. Authentication is header `X-N8N-API-KEY`, as described in [official n8n documentation](https://docs.n8n.io/connect/n8n-api/authentication.md). This key is unrelated to the backend admin/agent keys and the assistant-facing webhook key.

**At initial investigation time, no production API key was available.** The subsequent user-approved key is DPAPI-protected outside Git; earlier zero-record observations remain dated evidence. Never paste it into conversation, URLs, command arguments, exported workflow JSON or Git. A future client should retrieve it privately in memory, send only the header, disable HTTP debugging, and never serialize request headers. Do not treat `N8N_ENCRYPTION_KEY` as an API key.

Primary version-specific evidence is the actual installed code, rather than assumptions based on another n8n version:

| Installed source | Finding |
|---|---|
| `dist/public-api/v1/controllers/workflows.public.controller.js` | GET/PUT existing IDs, `publishIfActive`, publish route, permissions and partial-save errors. |
| `@n8n/api-types/dist/dto/workflows/base-workflow-public.dto.js`, `update-workflow-public.dto.js`, `update-workflow-query.dto.js`, `publish-workflow-public.dto.js` | Actual strict request validation and transformed settings. |
| `dist/workflows/workflow.service.js` | Draft save, version generation, permission checks, forced public update, publication/outbox. |
| `dist/workflow-helpers.js` | IDs generated only if absent; credential normalization; webhook ID resolution and setting cleanup. |
| `dist/workflows/publication/workflow-publication-applier.js` | Trigger teardown/registration, published-version cache advancement and eventual application. |
| `dist/services/api-key-auth.strategy.js` | Header authentication, role/API-key scopes, expiration and disabled-user handling; successful key use may update `lastUsedAt`. |

Source hashes and read-only observations: [api_investigation.json](../deploy/n8n_review/api_investigation.json). Private source copies are under ignored `tmp/n8n-api-review/installed/`. The global publication service is enabled by the installed default; no production override was found. Its outbox poll interval defaults to 15 seconds and explicit publication requests notify a drain. A successful publish response/`activeVersionId` is **not** proof the runtime has applied the version.

## Exact supported operations

| Operation | Endpoint | Required API scope / project permission |
|---|---|---|
| Read current draft and active snapshot | `GET /api/v1/workflows/{id}` | `workflow:read` / `workflow:read` |
| Save reviewed draft, leaving existing published graph | `PUT /api/v1/workflows/{id}?publishIfActive=false` | `workflow:update` / `workflow:update` |
| Publish exact verified saved version | `POST /api/v1/workflows/{id}/publish` body `{"versionId":"<verified saved version>"}` | `workflow:activate` / `workflow:publish` |
| Read retained version for rollback verification | `GET /api/v1/workflows/{id}/versions/{versionId}` | `workflow:read` / `workflow:read` |

Do not call create, unpublish, delete or deprecated activation aliases. The workflow ID is selected by the URL. Existing IDs and explicit executable node IDs are retained by the API; omitted node IDs are generated, so reject missing IDs before sending. Never accept a successful update to the wrong ID.

API-key scopes and project permissions are independent. Official documentation describes scope-selection availability as edition-dependent; do not promise a particular credential UI on this deployment. The isolated API tests proved the installed server accepts fixture keys with explicit scopes, including rejecting publication with an update-only fixture key. A future production key should have only read/update/activate where supported, bounded expiration and an authorized owner/project role. No credential-management/admin/ingestion permissions are needed for workflow updates.

## PUT schema

Required fields: **`name` (string), `nodes` (array), `connections` (object), `settings` (object)**.

The preparation script forwards these plus only already-present `description` (string), `nodeGroups` (array), `staticData` (JSON object/string or null) and `pinData` (object or null). It retains full node parameters, explicit IDs, `onError`, credentials references, positions/notes and ordered connections. Empty state is not silently substituted for omitted state. Current approved candidates have no credentials.

Other accepted update fields are `parentFolderId` and `shared`, but this release omits both: folder changes are outside scope and the public update controller ignores `shared`. `projectId` is not accepted by this update DTO. Node credential references are passed through validation, but backend credential normalization can rewrite invalid/ambiguous references; compare references again after save. No real credential values belong in nodes.

Do **not** send full CLI exports. `id`, `active`, timestamps, `versionId`, `isArchived`, `triggerCount`, `meta`, `tags` and `activeVersion` are read-only; `activeVersionId`, `versionCounter` and other undeclared fields also fail the strict write schema. Publication is handled separately. Settings are strictly validated; `binaryMode` and `credentialResolverId` are stripped by the installed DTO, so the preparation script stops if they occur rather than approving a lossy update. The three approved candidate payloads passed the installed DTO with identical parsed structures.

Example request envelope (body comes from the reviewed file, no secret included):

```text
PUT /api/v1/workflows/TnaaAssistant01?publishIfActive=false
X-N8N-API-KEY: <private in-memory credential>
Content-Type: application/json

{ "name": <reviewed name>, "nodes": <reviewed nodes>,
  "connections": <reviewed connections>, "settings": <reviewed settings> }
```

## Important publication and concurrency behavior

Default PUT behavior is `publishIfActive=true`: an already-published workflow is re-published automatically. Insufficient publication permission can return **403 after the draft has already been saved**, leaving the previous version live. A review block or webhook conflict can likewise prevent publication after a save. Never interpret an HTTP error as proof that nothing changed, and never blindly retry a PUT/POST.

Use explicit **draft save → GET/verify → publish exact version → GET/verify → runtime convergence verification**. Keep workflow 01 inactive and never call its publish endpoint. Keep 02/03 active and their `retrieve` / `assistant` webhook paths unchanged. Their old versions continue serving while drafts are staged. Even with `publishIfActive=false`, changing global settings can cause the service to re-publish the existing active version. This release therefore requires unchanged settings, enforced by preflight.

Public PUT uses `forceSave=true`; it exposes no supported expected-version/checksum precondition in this DTO. Rechecking GET immediately before writing reduces but cannot eliminate races. A confirmed exclusive editing window is a release requirement. Do not send an invented `If-Match`, `versionId` or checksum field and claim compare-and-swap protection.

Publication uses the running server's supported publication service: validates webhook conflicts and triggers, records intended active version/history, then applies via the outbox/applier and refreshes runtime caches. No Docker restart is required. Stable node IDs/path/parameters avoid an intentional webhook URL change, but this is **not a zero-interruption guarantee**. API 200 and active=true alone are insufficient runtime evidence. In a future approved window, verify publication status/convergence and an explicitly approved harmless application probe; do not trigger workflow 01 or send unsolicited Telegram messages. Exact production runtime convergence has not been tested.

## Proposed update sequence — NOT EXECUTED

1. Obtain a new explicit authorization for the production write window and, separately, private API credential creation/configuration if needed. No backend/bridge/security deployment is included.
2. Confirm exclusive edits, branch and approved commit `6021546`; compare candidate bytes to that commit. Fresh GET/export all three IDs; preserve each original draft, active snapshot/version, settings, credentials, webhook contract and publication state. Validate backups and retained published history. Abort on drift from the reviewed baseline.
3. Generate sanitized update/rollback payloads with the offline command below. Confirm active=false for `TnaaIngestIndex1`, active=true for `TnaaRetrieveApi1` and `TnaaAssistant01`. Keep exact node IDs and permitted reviewed additions (workflow 03's error responder/branches).
4. Immediately before each PUT, GET and compare to the recorded precondition. Save each draft with `publishIfActive=false`; on any non-2xx or timeout, GET to determine whether the draft was saved. Stop rather than retry blindly. Verify the entire saved writable body, credentials, IDs, layout and connections; 01 remains unpublished and 02/03 still point to their old active versions. Journal returned version IDs privately.
5. Only after all drafts verify, publish 02 and then 03 using **their exact verified saved version IDs**. Never publish 01 or submit an empty publish body that could select a concurrent draft. Recheck latest draft/version immediately before publication.
6. After each publish, GET the workflow, require the intended active state and active snapshot nodes/connections equal the approved candidate; verify runtime convergence separately. Re-export all three, compare normalized runtime plus complete visual definitions and retained settings/state. Open all three in the editor and Zoom to Fit. Stop for any unexplained credential/settings/node rewrite.
7. Use only approved harmless acceptance probes. Workflow 03's shared error outputs must leave success outputs intact; upstream authentication/validation/rate-limit errors can appear as sanitized HTTP 503. This behavior is a known limitation, not a backend security fix. No production failure simulation, ingestion, index write or unsolicited Telegram action.

## Proposed rollback — NOT EXECUTED

For each affected workflow, verify there is no unrelated concurrent edit. Construct the same strict writable payload from its fresh original backup and PUT it to the **same ID** with `publishIfActive=false`. GET and compare the restored draft to that backup. For originally active 02/03, publish the exact version returned by the verified rollback save; verify active=true, original graph/credentials/webhook contract and runtime convergence. For originally inactive 01, verify active=false with no active version and never publish it. Re-export and compare restored content. New server version IDs are expected; content/state restoration is the criterion.

On ambiguous/failed requests, read actual server state before deciding recovery. A publication-only rollback to the retained original active version can restore service first if that exact history entry is verified, but does not itself restore the latest draft or global settings; complete backup restoration remains necessary. No direct SQLite update, unsafe import, credential reset or container restart is part of rollback.

## Reproduce preparation and isolated tests

```powershell
# Offline plan only; substitute a newly verified export for --current before release.
.venv/Scripts/python -m scripts.n8n_api_plan --baseline tmp/n8n-review/20261017T222445235900Z --current tmp/n8n-review/20261017T223757699329Z
.venv/Scripts/python -m pytest tests/test_n8n_api_plan.py tests/test_n8n_workflow_review.py tests/test_api_security.py -q
# Explicit opt-in: new isolated disposable container only, using the existing exact image.
.venv/Scripts/python scripts/run_n8n_api_sandbox.py --run-disposable
```

The planner contains **no HTTP execution or credential handling**. Generated complete update/rollback payloads remain in ignored `tmp/n8n-api-review/plan.json`. The sandbox uses network mode `none`, no host ports/bind mounts/production volumes, tmpfs database storage, a neutral fixture owner and ephemeral fixture API keys. It removes only its own verified labeled container. Existing candidate and production containers are not edited or restarted. See [results](N8N_API_VALIDATION_RESULTS.md).
