# Second approved n8n synchronization — 18 October 2026 (Africa/Tunis)

**Completed: all three existing live workflows match the approved candidates.** There were five modifying API requests (three draft PUTs and two exact-version publish POSTs), no errors and no rollback. Workflow 01 remained inactive and was never executed. Workflows 02/03 remain published with their original webhook paths and activated registrations.

## Preflight and fresh backups

Verified clean branch `codex/final-n8n-workflows`, HEAD `c86033c529b140fd52883b3154742030b80e7ccb`. All three candidate JSON files remained byte-identical to candidate approval commit `6021546a1bb16166b919d92aa75a655d1bbead60`. Fresh CLI exports and authenticated API GETs matched the explicitly selected post-rollback baseline `tmp/n8n-review/20261017T225339956378Z/`, including workflow 01's restored version ID. No unexpected drift was detected.

Only the root agent was active in this team; no workflow editor was open in the available browser before this attempt. No conflicting editor was observed. The public API's lack of atomic compare-and-swap remains a limitation; immediate per-write and cross-workflow GET comparisons were used. No claim is made that process inspection can exclude every external API client.

Authentication succeeded without exposing the DPAPI-protected key. Read-only key metadata confirmed exactly `workflow:read`, `workflow:update`, `workflow:activate`. No credential or enforcement setting was changed.

Fresh original CLI backups:

- `tmp/n8n-review/20261017T231419059090Z/TnaaIngestIndex1.json`
- `tmp/n8n-review/20261017T231419059090Z/TnaaRetrieveApi1.json`
- `tmp/n8n-review/20261017T231419059090Z/TnaaAssistant01.json`

Fresh authenticated API backups and private release journal: `tmp/n8n-live-release/20261017T231447Z-second/`, with `before-<ID>.json`, verified draft/after snapshots, individual `export-after-<ID>.json`, `release.json` and sanitized local preflight evidence. Each rollback payload was validated before writing. A private helper was prepared to restore earlier verified workflows in reverse order if any later step failed; it was not executed because no failure occurred. No raw exports, private key/configuration or journal was added to Git.

## Final workflow state and version IDs

| Workflow ID | Executable / Sticky Notes | Active | Verified draft version | Verified published version |
|---|---:|---|---|---|
| `TnaaIngestIndex1` | 5 / 6 | No | `db99cce0-57ed-4ead-9545-4b8498892e68` | None |
| `TnaaRetrieveApi1` | 3 / 4 | Yes | `e3ec782c-8186-45b5-9862-8ffd27df0b34` | Same exact version |
| `TnaaAssistant01` | 17 / 10 | Yes | `21e4283f-f49d-495b-88e6-6c74647b669d` | Same exact version |

After each PUT, authenticated GET verified the complete candidate draft before publication. Workflow 01 had no active version, publication outbox record or active trigger. For 02/03, the exact verified draft version was published; API active snapshots matched the candidate graph. Read-only n8n publication metadata confirmed the runtime published-version record, completed matching outbox record and activated persisted webhook trigger with that same version.

Workflow 02 retains `POST /webhook/retrieve`; workflow 03 retains `POST /webhook/assistant`. No credential references were added, removed or remapped. The three workflow IDs and all previously existing executable node IDs were preserved. Workflow 03 adds only the reviewed error responder/branches relative to its previous live execution graph.

## Final export comparisons

Final independent three-workflow CLI exports: `tmp/n8n-review/20261017T231608959554Z/`.

All three passed both the full candidate node/layout/settings comparison and strict normalized comparison. API and CLI state/version IDs agreed. Comparison retained node IDs/names/types/parameters, credentials, all Sticky Notes and positions, ordered connections, workflow settings, workflow IDs and active state. Only explicitly verified empty root metadata (`sourceWorkflowId: null`, null/empty history labels) was normalized; meaningful metadata and unknown differences remained significant.

Workflow 03's six HTTP nodes each have their reviewed `continueErrorOutput` branch to `Respond: agent error`, with HTTP 503. Every original output branch, including both existing IF outputs, and every original executable node parameter set was compared unchanged. Some upstream errors, including authentication/validation/rate-limit errors, can therefore appear as sanitized 503 responses. This is the reviewed behavior, not new backend enforcement. No real production error was induced.

Machine-readable evidence: [second_synchronization_result.json](../deploy/n8n_review/second_synchronization_result.json). Its per-workflow records include backup hashes, counts, draft/publication IDs, strict comparison outcomes and runtime trigger metadata.

## Native rendering and safe checks

All three actual editors were opened, their node/annotation content inspected and native screenshots reviewed after Zoom to Fit. Workflow 01 shows its inactive Publish control; 02/03 show Published. The workflow 03 editor is left open for the user. No Execute, Save, Publish, Tidy Up or node/connection edit was performed in the UI.

The dense workflow 03 graph needs section-level zoom for readable annotation text. Some approved notes retain their preparation-time wording such as “Draft for review only” and “Live n8n remains unchanged,” and refer to the previous 16-node live graph. Those labels are historical review annotations, not the current state described by this report. They were preserved exactly as approved; no extra annotation change was introduced during synchronization. A later cosmetic wording update needs separate review.

Safe health GETs returned 200 for n8n and backend. Production backend/n8n/Telegram and existing final-candidate backend/n8n container IDs, image IDs, start times and restart counters matched preflight. No container was deployed or restarted. No backend/agent/key enforcement, firewall, Qdrant, corpus or Telegram configuration was changed. No ingestion, reindexing, Qdrant write or Telegram message occurred. No production webhook POST/application acceptance test was run.

The preceding 117-test offline correction remains historical validation; this attempt used the approved release code and read-only post-update checks rather than rerunning a production workload. Synchronization does not prove administrative answer correctness, legal completeness, OCR accuracy or real Telegram connectivity.

## Local files and remaining work

Repository changes in this attempt only:

- Added `deploy/n8n_review/second_synchronization_result.json`: sanitized final evidence.
- Added this report, `docs/N8N_SECOND_SYNCHRONIZATION_RESULT.md`.
- Refreshed `deploy/n8n_review/live_integrity.json`: fresh pre-write drift check.

Ignored local preparation/evidence: updated `tmp/n8n-api-review/approved-release-context.json` and `Invoke-N8nApprovedSync.ps1` to select the new release and explicit baseline; added private `Rollback-SecondSync.py`; fresh backup/release/final-export directories above. The encrypted key and other credentials were not modified. Approved candidate files, canonical `workflows/*.json`, backend, agents, RAG, prompts and Compose files remain unchanged. No commit, GitHub push, merge or unrelated project change was performed.

Live-to-approved-candidate synchronization is complete. Further functional text/context/language/citation, PDF/image/form/dossier and user-driven Telegram acceptance is pending separate approval. The hardened backend release and API-key enforcement remain separately unauthorized. Canonical base exports and historical reports are retained; any later repository canonical-export reconciliation or temporal annotation cleanup should be reviewed separately. Stop here; no automatic deployment or acceptance phase follows.
