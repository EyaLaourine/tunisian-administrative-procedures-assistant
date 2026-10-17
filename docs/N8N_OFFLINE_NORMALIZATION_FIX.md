# Offline n8n export normalization correction — 18 October 2026

**Offline correction and Git cleanup only. No production access, workflow execution, container operation, credential access or synchronization retry occurred in this task.** Prior live evidence remains historical; no claim of current live readiness was inferred from these offline tests.

## Root cause and exact reproduction

The failed release path was `main → export_one → verify_saved → runtime_equal`. `verify_saved` confirmed the candidate's nodes/layout, connections and settings, but `runtime_equal` reused the review-only `semantic` projection. Unknown root fields were retained, including the new CLI history metadata. The captured post-save export included `versionMetadata: {"name": null, "description": null}` and `sourceWorkflowId: null`, absent from the candidate. That created a false mismatch and the required rollback.

The old projection was also insufficient by itself for release visuals: it omitted node positions and Sticky Notes. The surrounding `verify_saved` gate previously checked them; the corrected release comparison now checks them directly as well.

Real captured inputs, read without contacting n8n:

- Approved `deploy/n8n_review/candidates/01_ingest_and_index.json`, still byte-identical to commit `6021546`.
- `tmp/n8n-live-release/20261017T225152Z/draft-TnaaIngestIndex1.json`.
- `tmp/n8n-live-release/20261017T225152Z/export-after-TnaaIngestIndex1.json`.
- Original API snapshot and verified rollback API/CLI snapshots in the same private ignored directory.

The frozen old comparison returns false for both candidate/export and captured draft/export. The corrected comparison returns true for both; the complete mocked one-workflow release path now verifies that captured case with exactly one PUT, no rollback and no publication. These are offline simulations, not a live retry.

[normalization_evidence.json](../deploy/n8n_review/normalization_evidence.json) contains hashes and the two actual captured metadata values, plus comparison results. It contains no raw backup, workflow execution or credential value. The portable regression uses that captured metadata projection with the approved candidate; two additional tests use the actual ignored snapshots. On a checkout without those private snapshots, those two tests explicitly skip; the portable regressions still run. This machine's final run had no skips.

## Narrow metadata rules and semantics

Only the **root** fields below are normalized, without modifying inputs:

| Representation | Treatment |
|---|---|
| Missing `sourceWorkflowId` vs `sourceWorkflowId: null` | Equivalent absence of lineage. |
| Non-null `sourceWorkflowId` | Retained and compared; lineage is meaningful. |
| Missing `versionMetadata`, `versionMetadata: null`, or exactly `{"name":null,"description":null}` | Equivalent empty history-version labels. |
| Non-null name/description, including empty strings; incomplete objects; unknown extra keys/types | Retained and compared. |
| Same names inside node parameters or other nested data | Never normalized by these root rules. |
| Other unknown root fields | Retained; missing versus present null is still significant. |

`versionMetadata` describes workflow-history version labels, not the workflow's top-level name or the executable node names. Prior installed n8n 2.41.3 source inspection identified explicit export injection at `dist/commands/export/workflow.js` lines 220/228. Existing captured `workflow.service.js` confirms history `versionName`/`versionDescription` handling, while `workflows.public.controller.js` exposes workflow `sourceWorkflowId` lineage. The current task uses those already captured sources and export evidence; it did not query the installed container again.

The shared review projection keeps its intentional execution-only purpose. The release gate additionally compares all complete nodes (including Sticky Notes, names, types, IDs, positions, note text, parameters and credentials), ordered connections, settings, workflow IDs and active state. Non-null workflow `meta` and top-level descriptions are also compared rather than hidden by review bookkeeping. Named version metadata and arbitrary unknown metadata remain meaningful. Public API/CLI `versionId` and `activeVersionId` convergence is checked separately, including after rollback; generated server version IDs are not equated to the candidate's old export metadata.

## Focused safety review

- HTTP 200 is followed by complete draft comparison; a success status alone is insufficient.
- Non-200 responses produce a safe failure and are not retried blindly. Mocked 403 coverage confirms one attempted PUT.
- Exact saved version is published only for originally active workflows. Workflow 01 is never published.
- Runtime publication polling requires the exact published version and completed matching outbox record for active workflows. Pending/wrong-version publication records do not pass; tests simulate the full bounded poll without sleeping or networking.
- API/CLI core state and server versions are compared after the candidate save and verified rollback.
- Failed draft verification/publication invokes rollback for the affected workflow, with explicit success/failure evidence. New tests ensure an invalid rollback is reported as failed, not restored.
- The next workflow remains blocked unless the current workflow is verified. A stopped journal cannot be reused to bypass that condition.

Two narrow retry-preparation guard adjustments were necessary: the candidate definitions remain pinned to `6021546`, but the release code may now be a descendant commit so this requested fix commit is usable. Preflight records the exact release-code HEAD and later steps reject a changed HEAD. Preflight also requires an explicit reviewed baseline; the original pre-rollback 01 version cannot silently be treated as current after rollback. No old failed journal or wrapper is automatically resumed.

## Actual offline validation

```powershell
.venv/Scripts/python -m pytest tests/test_n8n_export_normalization.py tests/test_n8n_controlled_sync.py tests/test_n8n_api_plan.py tests/test_n8n_workflow_review.py tests/test_api_security.py -q
```

**117 passed, 0 failed, 0 skipped**, six dependency deprecation warnings. This includes both real-capture regressions, portable captured-metadata cases, non-null/unknown metadata, node IDs/names/types/parameters, credentials, webhook paths, ordered connections, settings, missing/changed Sticky Notes, changed positions, nested metadata, active state, version convergence, bounded publication polling, no automatic HTTP retries and rollback verification/failure tests. Existing API security tests use TestClient/MockTransport without live dependencies.

Static checks: candidate JSON/graph validation; approved candidate bytes; Python compilation; Node fixture syntax (no fixture execution); staged diff whitespace and sensitive-pattern checks. Actual results and committed-file inventory are recorded in [offline_normalization_validation.json](../deploy/n8n_review/offline_normalization_validation.json). Earlier 30 isolated API checks and 76 release checks are historical evidence, not rerun live here.

## Retry readiness and remaining gates

**Ready for a separately approved controlled retry, conditional on fresh preflight. No retry is authorized or performed here.**

The reviewed post-rollback reference is `tmp/n8n-review/20261017T225339956378Z/`: workflow 01 has restored original content but a new version ID `fb8306c5-14a0-44e0-9f21-de7ed1892fe9`; 02/03 retain their original versions. A future operator must explicitly choose/verify this reference, create new backups, verify the private API key and candidate integrity, and obtain an exclusive edit window. Public PUT still lacks compare-and-swap. Do not reuse the failed release journal or the old wrapper that lacks the new `--baseline` argument.

Future approved preflight requires `python -m scripts.n8n_controlled_sync preflight --release <new ignored directory> --cli-backup <fresh export directory> --baseline tmp/n8n-review/20261017T225339956378Z`, with the key supplied privately in memory. Never put a key on the command line. Subsequent one-workflow steps use the new journal and require their fresh checks. These commands were not executed in this offline task.

Native candidate rendering, live publication convergence, real application acceptance and the separately approved backend release remain pending. Non-null version labels or lineage will deliberately stop an unreviewed difference rather than be silently discarded. Credential/pin/static-data changes remain outside this fix. No universal zero-downtime or answer-correctness guarantee is claimed.

## Commit scope

One cleanup commit collects only reviewed source, tests, documentation and sanitized reports from the API investigation, stopped attempts and this correction. Full private exports, temporary payloads, logs, API/DPAPI credentials and configuration remain excluded. Canonical `workflows/*.json`, all approved candidate JSONs, backend/agent/RAG/corpus code and prompt versions remain unchanged. No merge or push.
