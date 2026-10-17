# n8n presentation polish — offline proposal, 18 October 2026

**Awaiting explicit approval. No live workflow has been updated in this task.** The three previously synchronized workflows remain the live baseline. The proposal changes only the content of their 20 existing Sticky Notes and five note heights/one note position. Executable nodes, including their positions, are identical.

## Read-only audit and backups

Fresh official CLI backups: `tmp/n8n-review/20261017T232316167115Z/{TnaaIngestIndex1,TnaaRetrieveApi1,TnaaAssistant01}.json`. The drift guard compared full node definitions/positions, settings, runtime and publication versions to the successful synchronization's final exports: no changes. Backups are private/ignored and remain separate from the candidates.

The production backend was inspected without restarting or executing it. Running image: `sha256:8adaf99471c5e5064a09e14ab0e08d56dbbf7e4fd8376c319962b37c5ae4dde0`, container `28862b4efec1`, started `2026-10-17T11:30:37.613482422Z`. Its source has no `/app/agents/legal_evidence.py` and no `admin_api_key`, `agent_api_key` or `max_request_bytes` settings. A source Git commit cannot be inferred from that image ID. Therefore enhanced legal extraction and the reviewed backend key controls must not be described as deployed. The concise scope note retains the legal deployment limitation; security plans and image details remain in documentation.

## Candidates and before/after summary

| Workflow | Executable / notes | Note words, before → after | Intended publication |
|---|---:|---:|---|
| [01 candidate](../deploy/n8n_presentation/candidates/01_ingest_and_index.json) | 5 / 6 | 225 → 113 | Inactive; never execute ingestion. |
| [02 candidate](../deploy/n8n_presentation/candidates/02_retrieve_api.json) | 3 / 4 | 190 → 80 | Published; `retrieve` unchanged. |
| [03 candidate](../deploy/n8n_presentation/candidates/03_assistant_multi_agent.json) | 17 / 10 | 437 → 178 | Published; `assistant` unchanged. |

Total text: **852 → 371 words**, approximately 56% fewer words. Every note has a concise English heading and one or two explanatory source lines. Markdown can wrap according to the native editor viewport; these counts are not a claim that every rendered note occupies exactly three pixel lines.

Before: long audit/release notes, Docker addresses, preparation labels and large footer cards. After: stage labels, short service descriptions and explicit material limitations. “Draft,” historical “live unchanged” statements, candidate-image discussion and release debugging text are removed from the proposed **editable note contents**. Those details remain in the architecture/security/synchronization/rollback documentation and historical change evidence.

Existing colors are retained: input/response blue, routing purple, evidence green, documents gold, errors/safety red, supporting explanation gray. No executable or Sticky Note ID/name/type is changed. No decorative or fake execution node is added.

## Exact annotation plan

The [complete before/after diff](../deploy/n8n_presentation/ANNOTATION_DIFF.md) lists all 20 note contents and their stable IDs. [annotation_changes.json](../deploy/n8n_presentation/annotation_changes.json) records exact text, position, dimensions and color before/after. Candidate file SHA-256 values and baseline hashes are in [review_manifest.json](../deploy/n8n_presentation/review_manifest.json).

- 01: **Trigger → Official Sources → Document Processing → Embeddings & Qdrant → Run Summary**, plus Pipeline Safety. Text explains extraction → structural/recursive chunking → embeddings → indexing as backend-internal operations, with no fake executable stages. The inactive/reindexing warning remains.
- 02: **Retrieval Request → RAG Retriever → Grounded Evidence**, plus Retrieval Boundary. Dense retrieval is distinguished from the assistant's separate retrieval agent; no unsupported reranker/hybrid claim is added to `/retrieve`.
- 03: **01 · Request Entry**, **02 · Document Processing**, **03 · Intent Routing**, **04 · Evidence Retrieval**, **05 · Specialized Agents**, **06 · Error Handling**. Supporting cards cover direct replies, orchestration/service boundaries, diagram reading and scope limits. The informational-only dossier limit, non-deployment of enhanced legal extraction and upstream-errors-as-503 limitation remain explicit.

Only the following note geometry changes are proposed:

| Workflow / existing note | Before | After |
|---|---|---|
| 01 / Safety and legend | height 220 | height 180 |
| 02 / Relationship and legend | height 280 | height 200 |
| 03 / Legal evidence | height 350 | height 240 |
| 03 / External infrastructure | height 320 | height 240 |
| 03 / Legend and review boundary | position `[-80,1220]`, height 300 | position `[-80,1140]`, height 240 |

All other note positions/dimensions, every color and every executable node position are unchanged. This reduces annotation density and canvas extent without adding routing risk. Existing connection curves remain intact; this proposal does not claim to eliminate every wire crossing. Use Zoom to Fit for the overview and section zoom for details during the 15-minute demonstration. No new candidate has been imported/rendered natively; actual wrapping and readability must be checked after an approved application. No live layout change was used as a preview.

## Functional equivalence and actual validation

The visual-only projection removes only Sticky Note `position` and parameters `content`, `width`, `height`, `color`; the remaining complete workflow objects must be equal. Thus workflow IDs, executable nodes/positions/parameters, note IDs/types, connections, settings, credentials, webhooks, publication state and existing server snapshots cannot silently change. The independent execution-semantic comparison must also match, and all candidates pass structural validation.

CLI exports include a read-only `activeVersion` history snapshot. It is deliberately preserved, including its old annotations, rather than rewritten to pretend the new presentation is already published. The proposed editable notes are the top-level `nodes`; a future API update must send only the supported writable payload, not historical `activeVersion`/server version fields.

**25 focused tests passed, 0 failed, 0 skipped**, five dependency deprecation warnings. Tests use the actual fresh backups, validate schema/counts/hashes and non-overlapping note frames, and reject executable ID/name/type/position/parameter changes, credential changes, reordered connections, settings/publication/version changes, lost notes and unknown note parameters. No workflow, model, API mutation or isolated n8n instance was executed for these tests. The first test run found a test-reader issue (the workflow reader cannot load a multi-entry annotation array); that reader was corrected and the full targeted suite passed.

```powershell
.venv/Scripts/python -m scripts.n8n_presentation_polish --baseline tmp/n8n-review/20261017T232316167115Z
.venv/Scripts/python -m pytest tests/test_n8n_presentation_polish.py -q
```

The generator has no API/apply interface or credential handling. Exact results and deployment-status evidence: [validation.json](../deploy/n8n_presentation/validation.json). Tests using private backups explicitly skip when those excluded files are unavailable on another checkout; this run had all three backups available.

## Approval boundary and next procedure

No deployment-status wording needs to be guessed: the running image was checked, and the truthful limitation is retained. Enhanced backend deployment remains outside this task. Native candidate rendering is still unverified.

After explicit approval only: re-export/check drift from this baseline, back up again, bind the validated authenticated API procedure to **these presentation candidates and their reviewed hashes**, save/verify each draft, publish exact versions for 02/03 only, verify runtime registrations and strict candidate exports, then inspect all native canvases. Keep 01 inactive. On failure restore every workflow modified in that attempt from fresh backups. The existing release loader remains pinned to the earlier candidate commit; do not blindly run it expecting these new presentation files to be selected. No unsafe editor/CLI import is proposed.

This request does not authorize backend/Telegram deployment, key enforcement, ingestion, Qdrant writes, Telegram messages or unrelated service changes. No live write, credential change, container restart, commit, merge or push occurred in this preparation. Local file inventory appears in the validation report. Stop and request explicit approval for the visual-only live update.
