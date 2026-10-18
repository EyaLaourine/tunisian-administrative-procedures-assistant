# n8n workflow compatibility of the release candidate `rc-20261018b` (2026-10-18)

**Scope.** The three committed workflow exports, which equal the live published versions
(`TnaaAssistant01` = `af6ad259`, `TnaaRetrieveApi1` = `f4849a5c`, `TnaaIngestIndex1` = `819f02d9`, inactive), checked
against backend image `rc-20261018b` (`6124980f`).

**Isolation.**
- Live n8n was not modified, published or executed.
- The tests used my own isolated containers only:
  - `rc-n8n`, a fresh n8n with no volume, running the repository exports with `backend` replaced by `rc-candidate`;
  - for workflow 01, a Docker **internal** network with no internet, no Qdrant and no production containers.
- The test containers and the network for workflow 01 were removed afterwards.

## 1. API contract (OpenAPI, read from the running images)

| Comparison | Result |
|---|---|
| `final-candidate` (the image already validated with these workflows) vs `rc-20261018b` | **Identical**: all 13 routes, methods, request and response schemas, status codes and header parameters |
| Production `8adaf99` vs `rc-20261018b` (production contract read from a network-less container) | Same 13 routes and methods. `DialogueContext` gains 2 optional fields (`rne_code`, `legal_subject`), which is backward compatible. Optional `X-Agent-Key` header on the agent routes (open while `AGENT_API_KEY` is unset). `X-Admin-Key` on `/ingestion/run` and `/index/run`: **403 unless `ADMIN_API_KEY` is configured**. |
| Code since `final-candidate` (`12828f3`) in `backend/`, `rag/`, `ingestion/`, `agents/schemas.py` | only the `ollama_url` default (containers override it) |

**Workflow 03 expressions.** All 46 field references used by the workflow's expressions, and the six request
bodies, resolve against the rc schemas: `$json.*`, `$('Intent Router').item.json.*`, `next_agent`, `passages`,
`reply`, `context`, `recognised`, `form_doc_id`, `missing`, `form_url`, `found`, `doc_id`, `warnings`,
`translation`, `citations`, `method`, `prompt_ref`, and the Dossier Validator fields (`form_type` is a dict
filled with `doc_id`, `title` and `url` in `agents/dossier_validator.py`). An automated check flagged four items;
two were artefacts of the checker's own key regex (`data_b64` contains digits) and two were the untyped
`form_type` dict, verified in the code.

**Workflow 01 summary node.** It reads `counts` (from `/ingestion/run`), `documents_indexed`, `documents_skipped`
and `collection_points` (from `/index/run`). All of these are present in `backend/main.py` and
`rag/indexing.IndexingReport`.

## 2. Live contract tests (isolated)

| Workflow | Test | Result |
|---|---|---|
| 03 Assistant | 728-case replay (`scripts/final_replay.py`) through `rc-n8n` | 728/728 completed; identical to final-candidate on all 17 metrics |
| 03 | Multilingual 36 + behaviour 13 | 0 failures; 13/13 |
| 03 | Defect probes (context chaining as the bridge does) | 16/16 |
| 03 | Integration tests (assistant, dialogue, Telegram bridge with a mocked Telegram API) retargeted at `rc-n8n` | 37/37 |
| 03 | Error branch: a 2,500-character message makes the Intent Router return 422 | **HTTP 503**, `agent: orchestrator`, `error: agent_unavailable`, `failed_agent: "Intent Router"`, localised (FR and AR verified) |
| 03 | Envelopes | checklist `[agent, citations, context, doc_id, found, route, text, translation, warnings]`; answer `[agent, citations, context, found, method, prompt_ref, route, text]`; direct `[agent, context, route, text]`; uploads (replay) form and dossier fields |
| 03 | Context round-trip | the returned `context` (now including `rne_code` and `legal_subject`) is accepted on the next turn; the follow-up keeps RNE C 012 |
| 03 | Legal fix through n8n | the late-penalty question returns Law 2018-52 art. 51 |
| 02 Retrieval API | `POST /webhook/retrieve {"query", "top_k": 3}` | 200, a list of 3 passages `[chunk_id, citation, score, text]` with full citation metadata |
| 02 | With `filters.procedure_category` | 200, filtered passages |
| 02 | Body without `query` | n8n generic 500 "Error in workflow". **Pre-existing**: workflow 02 has no error branch and the backend's 422 is unchanged since production. Not a regression. |
| 01 Ingest and index, **as committed** | Executed (`n8n execute`) against the rc backend on the isolated network | **Fails at "Download official documents": HTTP 403, "Administrative endpoints are disabled (ADMIN_API_KEY not configured)".** Path and method are correct. `final-candidate` behaves the same (the hardening predates today's fixes). |
| 01, **proposed patch** | Executed with a test Header Auth credential against an isolated stand-in that accepts only the matching `X-Admin-Key` (`deploy/proposed/admin_echo.py`; nothing downloaded or indexed) | Matching key: both nodes 200 and "Run summary" produced, exit 0. Wrong key: 401 at the first node, and the run stops. The key never appears in the n8n output. |

## 3. Required workflow change (prepared, NOT applied)

- **Workflow:** `TnaaIngestIndex1`.
- **Nodes:** "Download official documents" and "Build chunks and index (both strategies)".
- **Why.** The hardened backend fails closed on the admin endpoints. Without the header, the next ingestion or
  re-indexing run returns 403.
- **When it matters.** The workflow is **inactive**, so it does not affect the deployment itself or the
  assistant. It must be applied before the next ingestion, together with `ADMIN_API_KEY`.
- **Patch:** `deploy/proposed/01_ingest_and_index_admin_key.json`, generated by `make_workflow_01_admin_key.py`.
  The two nodes gain `authentication: genericCredentialType`, `genericAuthType: httpHeaderAuth` and
  `credentials.httpHeaderAuth = {id: "TnaaAdminHeaderAuth", name: "TNAA Backend Admin"}`. Node IDs, connections,
  settings, notes and the inactive state are unchanged (verified).
- **To apply later (approval):**
  1. Create the Header Auth credential privately: header `X-Admin-Key`, value = `ADMIN_API_KEY`.
  2. Map the credential ID in the patch to the real one.
  3. Update through the verified API procedure (`docs/N8N_AUTHENTICATED_API_UPDATE.md`), keeping the workflow
     inactive.
  4. Set `ADMIN_API_KEY` and recreate the backend.
- **Rollback:** restore the current export of workflow 01; the workflow stays inactive.

**Workflows 02 and 03 under a future phase 2.** If `AGENT_API_KEY` is activated later, their 7 HTTP nodes need the
"TNAA Backend Agent" credential (`docs/SECURITY_PHASE2_ACTIVATION_PLAN.md`). This is not needed for this
deployment, because the agent key stays unset.

## N8N WORKFLOW COMPATIBILITY VERDICT

| Workflow | Verdict | Evidence |
|---|---|---|
| `TnaaAssistant01` (03, published) | **COMPATIBLE — NO CHANGE REQUIRED** | identical OpenAPI vs final-candidate; 46 expression references resolve; replay 728/728 identical metrics; multilingual 0 failures; probes 16/16; integration 37/37; error branch 503 verified |
| `TnaaRetrieveApi1` (02, published) | **COMPATIBLE — NO CHANGE REQUIRED** | `/retrieve` contract unchanged; isolated webhook calls return passages with citations; filters work; the error behaviour is unchanged from production |
| `TnaaIngestIndex1` (01, inactive) | **CHANGE REQUIRED** (before its next execution, not for the deployment) | as committed it gets 403 from the hardened backend (isolated run); the proposed patch passes both isolated runs (correct key 200/200 with summary; wrong key 401) |

The deployed backend image `rc-20261018b` is compatible with the two **published** workflows as they are. Workflow
01 is inactive and needs the prepared credential patch, together with `ADMIN_API_KEY`, before anyone runs an
ingestion.
