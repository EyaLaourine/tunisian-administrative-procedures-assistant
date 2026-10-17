# n8n API investigation validation results

Historical investigation results. Later milestones: private API authentication succeeded, workflow 01 was subsequently updated and restored after a verifier mismatch, and the verifier was corrected offline. Current retry gates and test counts are in [N8N_OFFLINE_NORMALIZATION_FIX.md](N8N_OFFLINE_NORMALIZATION_FIX.md). The tests below were not rerun against a live instance during that offline correction.

## Actual tests

**30 checks passed in an actual disposable n8n instance**, using the same image ID as production and only neutral fixture workflows/credentials. This was actual HTTP API/webhook testing inside the isolated container, not production testing or merely a mocked API. The fixture workflows do not invoke administrative agents, ingestion, Qdrant, Ollama or Telegram.

Evidence: [api_sandbox_results.json](../deploy/n8n_review/api_sandbox_results.json), including test names, fixture-source hash, exact image ID, isolation and cleanup evidence. No fixture API-key values or session cookies are saved. The final disposable container was removed.

Verified operations/behaviors:

- API key authentication rejects an unauthenticated read.
- Installed DTO accepts a neutral payload and rejects read-only/undeclared fields and missing required name; actual HTTP rejects writable `active` with 400.
- Creation and update preserve explicit node IDs; PUT preserves the same workflow ID, ordered connections, webhook path and a valid fixture credential reference (on a disabled HTTP node; it was not used to authenticate an upstream request).
- Updating an inactive fixture leaves it unpublished.
- `PUT ...?publishIfActive=false` saves a new draft while the old webhook response remains live.
- Explicit publish of the saved version changes the actual webhook response and published graph.
- `publishIfActive=true` supports automatic republication with sufficient permissions.
- An update-only fixture key causes 403 **after** the draft save when automatic publication is requested; the old webhook response remains live.
- Backup-body PUT plus explicit publish restores the original graph and actual webhook response.
- PUT to a missing ID returns 404 rather than creating a duplicate workflow.
- A separate neutral error-routing fixture verifies actual n8n `continueErrorOutput`: successful upstream HTTP 200 reaches the success responder; upstream 401, 429 and 503 each reach a sanitized 503 responder. This validates the routing mechanism, not full workflow 03's production behavior or all six agents.

The initial expanded runner failed because `/healthz` became ready before API routes were mounted. Its readiness probe was corrected to wait for the actual API's unauthorized response; the complete final isolated test run then passed. This was a test-runner startup issue, not a production failure. Earlier disposable instances were also removed; no existing container was stopped.

**72 focused pytest tests passed, 0 failed, 0 skipped**, six dependency deprecation warnings. Command: `.venv/Scripts/python -m pytest tests/test_n8n_api_plan.py tests/test_n8n_workflow_review.py tests/test_api_security.py -q`. These cover offline payload allowlisting, contract/ID/credential drift rejection, publication snapshot verification, lossy settings rejection, existing graph checks and mocked backend security. They are separate from the 30 isolated API checks and must not be presented as 102 end-to-end production tests.

All three approved candidate payloads were additionally parsed by the installed real `UpdateWorkflowPublicDto` without changing their JSON structures. Parsing was performed in a short-lived Node process, without initializing the n8n application or connecting to its database. The candidates themselves were not imported/executed in the sandbox.

## Read-only production observations

- GET workflow without API key: 401; GET local API documentation: 200.
- No usable API key in inspected local configuration; zero key records in the production database, queried with `readOnly:true`. No production key created or activated.
- Fresh exports `tmp/n8n-review/20261017T223757699329Z/` match `tmp/n8n-review/20261017T222445235900Z/` for full nodes/layout, runtime, settings, IDs and publication versions. Approved candidate files still match commit `6021546`.
- Production workflow 01 remains inactive/5 nodes; 02 active/3; 03 active/16. Candidate 03 remains 17 nodes with the reviewed 503 error branches; not deployed.
- Sandbox runner confirms the production n8n container ID, image, start time and restart counter unchanged. No modifying production HTTP request, production workflow execution or Qdrant write occurred.

## Remaining gates

The supported API method is validated, including fixture publication and rollback. **Live synchronization is not yet ready to execute**: production has no API credential, an exclusive edit window is needed because public PUT lacks compare-and-swap, and a new explicit write approval is required. Creating/configuring a production API key is a separate approval, not part of these fixture tests. Backend API keys and assistant-webhook enforcement remain untouched.

Production-specific checks still pending: authenticated production read/scope/project access; actual candidate native rendering; live publication-applier convergence; candidate success/error routes against the older backend; any explicitly approved HTTP/manual Telegram acceptance. No zero-downtime guarantee is inferred from successful fixture publication. A valid citation alone still does not prove an administrative answer correct.

New files in this task: `scripts/n8n_api_plan.py`, `scripts/run_n8n_api_sandbox.py`, `tests/test_n8n_api_plan.py`, `tests/n8n_api_sandbox.cjs`, `deploy/n8n_review/api_investigation.json`, `deploy/n8n_review/api_sandbox_results.json`, and these two documents. Existing `deploy/n8n_review/live_integrity.json` was refreshed by a read-only export guard. Existing uncommitted `docs/N8N_SYNCHRONIZATION_RESULT.md` and its prior report status were preserved. No commit/push was made in this investigation.
