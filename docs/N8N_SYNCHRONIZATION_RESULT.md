# Controlled synchronization result — 17 October 2026

Historical first blocked attempt. Later API investigation and an approved update/verified rollback are documented in [N8N_FINAL_SYNC_ATTEMPT.md](N8N_FINAL_SYNC_ATTEMPT.md); the subsequent offline fix is documented in [N8N_OFFLINE_NORMALIZATION_FIX.md](N8N_OFFLINE_NORMALIZATION_FIX.md). This document does not describe the latest attempt.

**Stopped before applying. Zero workflows updated. No import or publication attempted.**

The user authorized only the three approved workflow updates, conditional on preserving existing workflow/node IDs, webhook contracts and publication states. Fresh read-only exports matched the original audit in runtime, full nodes/layout, settings and publication version IDs. All three candidate files matched commit `6021546a1bb16166b919d92aa75a655d1bbead60` byte for byte and contained no credential references.

## Fresh rollback material

Private, ignored directory: `tmp/n8n-review/20261017T222445235900Z/`.

| File | Current publication | Executable nodes | Backup validation |
|---|---|---:|---|
| `TnaaIngestIndex1.json` | Inactive/unpublished | 5 | Parsed, correct ID, complete graph, valid connections/routes. |
| `TnaaRetrieveApi1.json` | Active/published; `retrieve` | 3 | Parsed, correct ID, complete graph, valid connections/routes. |
| `TnaaAssistant01.json` | Active/published; `assistant` | 16 | Parsed, correct ID, complete graph, valid connections/routes. |

`PREFLIGHT.json` in that directory records backup SHA-256 values, activation/publication version IDs and the stop reason. Definitions are structurally suitable rollback material; actual restoration was not executed or tested, and requires a supported update channel. No credentials are required to store or validate these exports; none were exposed.

## Blocking compatibility finding

The installed official editor's file-import handler emits `importWorkflowData` without disabling ID regeneration. `NodeView-DuDyK4Rx.js` defaults `regenerateIds` to true, and `useCanvasOperations-DCQ5-dGy.js` assigns new node IDs. The import would therefore fail the explicit preservation requirement. It was not performed.

The installed official CLI supports `--activeState=fromJson`, but its implementation in `dist/commands/import/workflow.js` rejects that option in regular deployment mode. This production instance is in regular mode. Default CLI import deactivates imported workflows, so it was not performed either. No restart, direct database edit, authentication bypass, new API key or security setting change was attempted.

An authenticated update of the existing IDs through a supported API client remains a possible route, but no compatible authenticated API channel was available through the inspected interfaces. This is not a claim that synchronization is impossible; it is a stop under the user's strict preconditions rather than substituting a method with different side effects.

## Results and next gate

- Pre-apply export comparison: passed; no drift detected.
- Approved candidate commit comparison: passed for all three.
- Backup structural validation: passed for all three; private hashes recorded.
- Re-export comparison to applied candidates: not applicable; no application occurred.
- Native editor: existing workflow 01 opened successfully; redesigned candidates were not imported or rendered. Workflows 02/03 were not re-inspected visually in this attempt.
- Workflow 03: existing production graph remains 16 nodes. The reviewed six error branches/shared 503 responder remain candidate-only. Their success-path isolation is structurally tested, not verified in production; the candidate deliberately represents some upstream 401/403/422/429 errors as 503.
- Safe checks in this attempt: read-only CLI export, JSON/graph validation, Git byte comparison, editor/source inspection. No webhook POST, agent request, ingestion, Qdrant write or Telegram message was sent. No functional smoke test was executed.
- Errors/rollback: no application error and no rollback required; compatibility blockers were detected before mutation.

Next work requires a supported authenticated update channel that preserves IDs and running publication without creating credentials or restarting services. Stop here and await the user's next explicit instruction. Backend/bridge deployment, credential enforcement and full production acceptance remain separately unauthorized.
