# Controlled deployment and rollback — plan only

No live changes are authorized by this document. Current work prepares three offline candidates, a comparison/credential plan and focused validation. Workflow 01 execution, production reindexing, container deployment and credential activation remain prohibited without their own explicit authorization.

## Gate 1: workflow candidate application

- Obtain explicit approval for all three candidate definitions, including workflow 03's existing repository 503 branches. Explain that this is not entirely layout-only relative to production.
- Confirm branch/commit, candidate files and semantic hashes in `deploy/n8n_review/review_manifest.json`; inspect staged/approved differences.
- Run the read-only `--verify-live` guard against `tmp/n8n-review/20261017T220611Z`; retain new per-workflow exports separately. Abort for any unexpected runtime/layout/version/publication drift. Resolve competing edits with the owner rather than overwriting.
- Record current image IDs, start times, restart counters and n8n versions privately; retain existing volume backups under the owner's storage policy. Workflow exports do not back up credentials or the entire n8n database.
- Use the existing signed-in editor or verified official API update for **the same IDs**. Do not import duplicates, execute workflows, alter webhook paths or invent credential IDs. Do not change `.env`, runtime networking, backend images or client headers in this gate.
- Keep 01 inactive/unpublished; preserve published 02 and 03, publishing the approved updated versions only as part of this authorized change. Re-export and compare both runtime and visual definitions; verify no pin/static data or credential references changed.
- Open all three canvases, Zoom to Fit, inspect labels, text wrapping, wires and branches at practical zoom. Static geometry is insufficient for native visual sign-off.
- Read-only health checks: GET `http://localhost:5678/healthz`, GET `http://localhost:8000/health`; inspect sanitized status metadata only. Health does not prove functional correctness.
- With an approved test window, run representative HTTP/manual acceptance cases. No workflow 01, no private uploads, no unsolicited Telegram messages. Commit canonical sanitized re-exports only after verified synchronization.

## Gate 2: hardened backend / bridge deployment — separately approved

Production is an older image. Do not assume reviewed legal extraction or optional API-key enforcement is available there. Review existing security/release documentation and candidate image provenance before proposing a release. Pin current image IDs for rollback. Check candidate ownership; do not stop or overwrite its containers without approval. No Docker/Ollama restart, firewall change, Qdrant write or unrelated project change is part of this workflow review.

If separately authorized, deploy only the reviewed backend/bridge services necessary for that release, using pinned images and documented Compose configuration. Avoid rebuilding unreviewed source or restarting dependencies. Verify health plus representative source-grounded responses, uploads and user-driven Telegram tests. Do not claim bridge health proves real Telegram message exchange.

## Gate 3: coordinated credential activation — separately approved

Follow [security mapping/order](N8N_SECURITY_INTEGRATION.md). Prepare actual n8n Header Auth credentials privately, configure callers before enforcement, validate isolated missing/wrong/correct key cases, then coordinate backend and webhook enforcement. Workflow 03 currently maps all HTTP errors to 503: a key mismatch may look like temporary unavailability and trigger bounded retries. Treat authentication errors as release blockers, not grounds to remove security silently.

No production admin POST is an acceptable credential test. Never activate ingestion/index schedules. The assistant's official corpus and Qdrant collections must remain untouched.

## Rollback

1. Stop rollout on unexpected responses, publication drift, credential mismatch, duplicate webhook or semantic difference. Do not run ingestion as recovery.
2. For workflow-only changes, update the existing IDs from the exact private baseline exports:
   - `tmp/n8n-review/20261017T220611Z/TnaaIngestIndex1.json`
   - `tmp/n8n-review/20261017T220611Z/TnaaRetrieveApi1.json`
   - `tmp/n8n-review/20261017T220611Z/TnaaAssistant01.json`
3. Preserve 01 inactive and 02/03 active with the corresponding pre-change published definitions. Do not blindly copy server metadata or restore a database over a running instance. Verify allowed update fields/publication behavior on the installed API/editor.
4. Re-export and compare IDs, executable and visual definitions, settings, credentials, active states and webhook paths. New server-managed version IDs may differ after rollback; document that rather than claim byte-identical exports.
5. If a separately approved backend/key release also occurred, restore the recorded prior backend/bridge image IDs **and matching configuration/caller headers** under that release authorization. Workflow rollback alone cannot fix backend auth mismatch. Retain n8n encryption/storage keys privately; do not rotate or expose them.
6. Check health, then approved representative acceptance tests and sanitized errors. Leave all Qdrant data and unrelated services unchanged. Record exact observed results and remaining gaps.
