# n8n security integration plan

**Audited, not enabled.** Primary candidates contain no keys, no new authentication and no unresolved credential references. [Machine-readable mapping](../deploy/n8n_review/security_mapping.json) specifies all nine backend calls and the two webhook entries. Real credentials must be created privately in n8n after authorization and mapped to actual credential IDs; never put values in JSON, Git, screenshots, logs or reports.

| Workflow | Backend endpoint | Required header in reviewed hardened backend | Planned n8n credential |
|---|---|---|---|
| 01 | POST `/ingestion/run` | `X-Admin-Key` | TNAA Backend Admin |
| 01 | POST `/index/run` | `X-Admin-Key` | TNAA Backend Admin |
| 02 | POST `/retrieve` | `X-Agent-Key` when configured | TNAA Backend Agent |
| 03 | POST `/agents/route` | `X-Agent-Key` when configured | TNAA Backend Agent |
| 03 | POST `/agents/retrieve` | `X-Agent-Key` when configured | TNAA Backend Agent |
| 03 | POST `/agents/checklist` | `X-Agent-Key` when configured | TNAA Backend Agent |
| 03 | POST `/agents/answer` | `X-Agent-Key` when configured | TNAA Backend Agent |
| 03 | POST `/agents/form-check` | `X-Agent-Key` when configured | TNAA Backend Agent |
| 03 | POST `/agents/dossier-check` | `X-Agent-Key` when configured | TNAA Backend Agent |

HTTP Request credential type: `httpHeaderAuth`; parameters `authentication: genericCredentialType`, `genericAuthType: httpHeaderAuth`. Map each node's credentials to the private n8n credential ID/name. The supported Header Auth credential contains the exact header name and private value; do not add literal header values to nodes.

Webhook 02 `/webhook/retrieve` and 03 `/webhook/assistant` may separately use `authentication: headerAuth` and `httpHeaderAuth` credential **TNAA Assistant Entry**, header `X-Assistant-Key`. FastAPI does not enforce that header. Supported bridge/web/CLI callers send it only when `ASSISTANT_WEBHOOK_KEY` is set; inventory every caller before enabling it. Public read-only backend health/source/manifest routes do not require these headers. Telegram's own token is unrelated to all three API keys.

## Exact enforcement and runtime gap

Reviewed source: admin key absent → admin endpoints fail closed with 403; configured key and missing/invalid header → 401. Agent key absent → agent/retrieval endpoints remain open; configured → missing/invalid header 401. Comparisons use constant-time checks. No HTTP rate limiter is implemented by these dependencies; 429 is a possible downstream error, not a claimed application control.

Actual production image lacks `admin_api_key`, `agent_api_key`, `max_request_bytes` settings and the new legal evidence module. Candidate image has them, but both inspected backends have no configured admin/agent key. The live workflows have no credential references and the bridge has no assistant webhook key. Therefore hardened source documentation is **not evidence of live enforcement**. Production backend also receives `N8N_ENCRYPTION_KEY`; least-privilege removal belongs to a separately approved deployment. Its value was never printed.

Reviewed middleware caps declared numeric Content-Length at 15 MB; it is not a complete streaming/no-Content-Length body limiter. Upload processing has additional byte caps (10 MB), OCR limits (three pages, timeout), and memory-only processing. Do not claim complete request-size or denial-of-service protection. n8n workflow 03 disables saved success/error/manual execution data; do not turn execution storage on for uploaded personal data. Existing retention/log behavior outside that workflow needs independent verification.

## Activation order — separate authorization required

1. Privately create n8n Header Auth credentials with exact header names. Back up n8n encryption/storage configuration privately; no export of decrypted values.
2. Coordinate a separately approved hardened backend release. Missing admin key fails closed; configure the same admin key before any later authorized admin operation. Do not run ingestion/indexing to test credentials.
3. Configure backend-call credentials in the approved workflows and verify missing/wrong/correct keys against an isolated backend with mocked admin operations. Production agent enforcement must not be enabled before every agent caller has been configured and verified.
4. Configure bridge, web fallback, CLI and every other webhook client before enforcing `X-Assistant-Key` at n8n. An unauthenticated client would otherwise immediately fail.
5. Verify the hardened backend release and bounded rollback window; only then enforce agent/webhook keys under explicit coordinated approval. Do not change `.env` or recreate containers as part of this preparation.

Rollback must restore matching workflow credential references, backend image/configuration and client header configuration as one coordinated state. Never remove callers' headers while enforcement remains enabled. Restore workflow-only candidates separately if no backend/key release occurred. See the deployment checklist.
