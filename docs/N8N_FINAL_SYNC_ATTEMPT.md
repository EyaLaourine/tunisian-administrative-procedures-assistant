# Approved synchronization attempt — stopped after verified rollback

## Outcome

Synchronization is **not complete**. The controlled process attempted workflow 01, detected an unexpected normalized-export difference, stopped immediately and restored that workflow. Workflows 02 and 03 received no modifying requests. No workflow was published/unpublished or executed. Two production HTTP writes occurred: the candidate draft PUT for 01 and its rollback PUT.

The existing production definitions are restored/untouched: workflow 01 inactive with 5 executable nodes, 02 published with 3, 03 published with 16. All have zero Sticky Notes in their final state. Workflow 03's reviewed 17-node error graph remains candidate-only.

## Preflight and backups

Branch `codex/final-n8n-workflows`, HEAD `6021546a1bb16166b919d92aa75a655d1bbead60`; all three candidate files matched that commit byte for byte. Fresh CLI exports and authenticated API GETs agreed with the audited definitions. The private key had exactly `workflow:read`, `workflow:update`, `workflow:activate`; no value was exposed. No other agent was present in the current agent team and no conflicting editor warning was observed. Immediate per-write GET comparisons guarded against observed drift; the public API still has no atomic compare-and-swap guarantee.

Fresh pre-change official CLI backups:

- `tmp/n8n-review/20261017T224927121512Z/TnaaIngestIndex1.json`
- `tmp/n8n-review/20261017T224927121512Z/TnaaRetrieveApi1.json`
- `tmp/n8n-review/20261017T224927121512Z/TnaaAssistant01.json`

Fresh authenticated API snapshots, release journal, attempted/rollback snapshots and exports are in ignored `tmp/n8n-live-release/20261017T225152Z/`. These include `before-<ID>.json`, `release.json`, `draft-TnaaIngestIndex1.json`, `export-after-TnaaIngestIndex1.json`, `rollback-TnaaIngestIndex1.json` and `export-rollback-TnaaIngestIndex1.json`. Backup hashes are recorded in the journal. The actual restoration of 01 was verified, not merely planned.

## Failure diagnosis

The approved 01 draft was saved successfully and authenticated GET plus re-export checks confirmed exact candidate nodes, notes, positions, connections and settings. The subsequent broader normalized comparison failed because the new normalizer did not account for CLI-exported server metadata:

- `versionMetadata: {"name": null, "description": null}` appears after a new version is saved; the candidate has no such field.
- `sourceWorkflowId: null` is also present in the export and absent from the candidate.

Installed official `dist/commands/export/workflow.js` explicitly adds `versionMetadata`. The verifier treated these server fields as unexpected runtime data. This is a defect in the newly added normalization coverage. It triggered the required conservative stop and rollback. Existing focused tests had not covered this post-save CLI export case; their passing results did not establish equivalence for that case.

No retry or metadata-filter correction was applied to production after the failure. A narrowly reviewed offline correction and test for these explicit server fields is required before any separately approved retry. Do not suppress unknown runtime differences generally.

## Verified final state

| Workflow ID | Final executable / notes | Final state | Draft version | Published version |
|---|---:|---|---|---|
| `TnaaIngestIndex1` | 5 / 0 | Restored, inactive | `fb8306c5-14a0-44e0-9f21-de7ed1892fe9` | None |
| `TnaaRetrieveApi1` | 3 / 0 | Untouched, active | `0867dd24-169e-4a5a-9f28-248658bf67e8` | Same |
| `TnaaAssistant01` | 16 / 0 | Untouched, active | `92f81ea7-3e60-4564-8c23-4dcc5eba5494` | Same |

All original executable node IDs, complete node definitions/positions, connections, settings, credential references and webhook paths were restored or remained unchanged. The 01 rollback necessarily generated a new server version ID; its original content and inactive publication state are the restoration criteria. Its restored content was checked by API GET and official CLI export, then rechecked in a final three-workflow export.

Final read-only exports: `tmp/n8n-review/20261017T225339956378Z/`. Read-only publication metadata confirms 01 has no published version/outbox/triggers; 02/03 retain their original runtime published versions and activated webhook trigger records. Machine-readable final evidence: [synchronization_result.json](../deploy/n8n_review/synchronization_result.json).

## Tests, rendering and restrictions

Before writing: **76 focused pytest tests passed, 0 failed, 0 skipped**, six dependency warnings, including mocked recovery tests for draft-verification failure and publication failure. JUnit: ignored `tmp/n8n-api-review/release-tests.xml`. The normalization gap above is explicitly outside that passing coverage.

The original workflow 03 editor was inspected before writing, showing the existing 16-node published graph. Workflow 01's restored editor was opened for read-only inspection afterward. Redesigned candidate native rendering was not accepted: the release stopped and rolled back before that gate. No production webhook POST or functional agent/Telegram acceptance was performed. Future candidate rendering, publication and application acceptance remain pending.

Production and existing candidate container IDs, image IDs, start times and restart counters were checked unchanged. No backend/bridge deployment, Docker/Ollama restart, firewall change, business security-key enforcement, Qdrant write, ingestion or Telegram message occurred. The API credential remains DPAPI-protected outside Git.

## Exact local changes in this attempt

- Added `scripts/n8n_controlled_sync.py`: guarded preflight, one-workflow update, publication convergence checks, re-export comparison and verified rollback.
- Added `tests/test_n8n_controlled_sync.py`: mocked failure/rollback and drift/normalization checks.
- Added `deploy/n8n_review/synchronization_result.json`: sanitized final live/rollback evidence.
- Added this document, `docs/N8N_FINAL_SYNC_ATTEMPT.md`.
- Refreshed `deploy/n8n_review/live_integrity.json` during the pre-write export guard.
- Ignored local files: `tmp/n8n-api-review/Invoke-N8nApprovedSync.ps1`, `approved-release-context.json`, fresh backup/release directories and test XML.
- Corrected ignored `tmp/n8n-api-review/Configure-N8nApiKey.ps1` to trim the encrypted file's terminal newline before DPAPI decoding; the encrypted credential itself was not changed. The same fix is in the ignored invocation wrapper.

Previously pending API-investigation files remain uncommitted and unchanged by this attempt, except the explicitly listed export guard. No commit, push, merge or canonical `workflows/*.json` update was made. Stop here; no further live retry is authorized after this failed attempt.
