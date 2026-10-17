# Repository / live synchronization review

**Prepared, not synchronized.** Canonical exports remain unchanged in `workflows/`. Approved candidates are staged separately under `deploy/n8n_review/candidates/`. Existing exports under `deploy/final_candidate/` and `deploy/n8n_rollback/` are historical, not substitutes for live backups.

See [structured comparison](../deploy/n8n_review/COMPARISON.md), [manifest](../deploy/n8n_review/review_manifest.json), individual `comparisons/*.json`, and [live drift guard](../deploy/n8n_review/live_integrity.json).

## Authority and differences

- 01: same executable behavior as repository/live, candidate adds layout/notes; keep inactive.
- 02: live active vs repository inactive; preserve live active state. No API or retrieval implementation change.
- 03: repository inactive/17 nodes vs live active/16; retain six `continueErrorOutput` branches and `Respond: agent error` (503), preserving live active state. Functional drift is explicit and requires approval along with layout.
- No auth activation or credential ID changes are included in primary candidates. Credential mapping is a separate plan.
- Server version IDs and timestamps are metadata, not candidate runtime changes. Do not overwrite current server metadata with stale exported values.

## Reproducible read-only tooling

```powershell
# Official CLI export of the three existing IDs; no execution/import/publication.
.venv/Scripts/python scripts/n8n_workflow_review.py --export
# Prepare offline candidates from the original, explicitly selected baseline.
.venv/Scripts/python scripts/n8n_workflow_review.py --prepare --baseline tmp/n8n-review/20261017T220611Z
# New private exports; nonzero exit and changed field names on drift.
.venv/Scripts/python scripts/n8n_workflow_review.py --verify-live --baseline tmp/n8n-review/20261017T220611Z
# Offline structural and mocked security checks; no network or corpus writes.
.venv/Scripts/python -m pytest tests/test_n8n_workflow_review.py tests/test_api_security.py -q
```

Exports are per-workflow, timestamped in ignored `tmp/n8n-review/`. They preserve IDs, node definitions, connections, settings, activation, version IDs and credential references. No credential values are requested/exported. Keep these private and retain the initial baseline; do not overwrite it with an edited definition.

Normalization excludes Sticky Notes, executable node positions/descriptive notes and server-managed bookkeeping. It retains executable names/IDs, parameters, expressions, credentials, `onError`, ordered output connections, settings, activation, pin/static data and unknown top-level runtime fields. Hashes accompany field-level comparisons; hashes alone are not semantic proof. The drift guard additionally compares complete nodes (including layout), versions and publication state.

## Controlled application — requires explicit approval

The script deliberately has **no apply operation**. No import/publish call or live credential write is hidden behind preparation. A reviewed operator must:

1. Re-export all three, run the drift guard, and compare Git/candidate SHA values to the reviewed manifest. Abort on any unexpected change.
2. Use the signed-in n8n editor or the installed official authenticated API to **update the existing workflow IDs**, not create duplicates. Verify the actual API's allowed update fields/version concurrency behavior before use; do not submit full CLI exports blindly.
3. Apply candidate nodes, connections and reviewed settings. Preserve webhooks `retrieve` and `assistant`, node IDs and intended publication. Keep 01 unpublished. Publish updated versions only for previously published 02/03, under the approved change scope.
4. Do not use a CLI import followed by a production restart as a shortcut. Running n8n publication behavior must be checked in the editor without restarting services.
5. Re-export, validate graphs/credential references/activation, and compare normalized runtime plus visual fields to approved candidates. Check editor rendering and read-only health. Application requests/manual Telegram acceptance need an approved test window.
6. Only after confirmed application, synchronize canonical `workflows/*.json` from reviewed, sanitized re-exports in a separate commit. Preserve credential references; never commit credential values or private execution data.

Credential enforcement/backend rollout is a separate release gate, not implied by approval of these workflow layouts. See [deployment/rollback](N8N_DEPLOYMENT_CHECKLIST.md).
