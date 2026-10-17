# Post-audit fix report

## Decision and scope

Candidate changes are implemented and tested. **Not deployed to the production backend or Telegram bridge.** The requested gate is preserved: “Do not deploy until the regression results are reviewed.” This report and the retained original intent discrepancies are ready for that review. Existing production behavior therefore remains unchanged.

The original 846-case audit was not repeated. This run replays **632 selected original cases** through a real isolated n8n instance and the final candidate Docker backend, with the existing Qdrant and Ollama services. The workflow copy has the same 16 nodes and no execution-payload retention; only its six backend URLs point to the candidate. Production workflow 03 is unchanged. No Telegram API request or unsolicited message was made by this work.

Current source applicability remains unverified. Exact source copying does not establish that a law is current, that it applies to an individual, or that a dossier is legally complete.

## Confirmed root causes and changes

1. **Context destroyed RNE identity.** The canonical dialogue query omitted codes and entity wording. It also truncated dotted codes such as `C 010.1` to `C 010`. Public procedure codes now survive fresh context, follow-ups and corrections, including dotted suffixes. Original question wording is retained for RNE retrieval. The bridge wire contract now preserves these fields rather than silently dropping them.
2. **The guide filter removed the RNE answer.** Business-table sections use `kind=other`; context filtering retained only guide kinds such as `fees` or `delay`. Actual production traces show `other` sections before filtering, no sections afterwards, and `found=true` with only source links. Business results now retain their dedicated labelled table rendering.
3. **Vector similarity could replace an exact row.** I 001/I 002 fee queries could select other procedures. Code queries now read the exact indexed Qdrant table point, including the full dotted code. The builder independently resolves the same exact official extracted row; unavailable codes return not-found rather than a neighboring procedure. The corpus and the RAG implementation under `rag/` are unchanged.
4. **CIN loss was excluded by a compound title.** The official loss/theft/damage title also says “Changement”. Requiring the user to state both loss and modification excluded the correct scenario; a further scoring penalty tied it with first application. Both are corrected. Theft/damage language variants map to the existing combined official scenario, without adding requirements.
5. **Arabic purpose wording looked like a deadline.** `أجل` inside `من أجل` triggered processing-time intent in official loss titles. Purpose wording is removed before intent matching; genuine deadline questions remain supported. Arabic plural beneficial-owner wording and explicit legal references now identify the covered legal subject deterministically.
6. **Legal generation accepted semantically wrong claims.** Valid citation indices and supported numbers did not establish article identity, list completeness or legal meaning. For the six confirmed legal source families, answers now quote located, complete extracted article bodies rather than generating legal paraphrases. Explicit article requests select that exact provision; printed payment lists, numerical thresholds and qualifications remain in their source wording. A bounded allowlisted legal-subject slot keeps follow-ups on the same text. Ambiguous broad-law/fee follow-ups and statements that the text does not fit the user's case ask for clarification.

No raw conversation history, personal identifiers or uploaded values are added to session state. Existing chat isolation, cancellation, 30-minute expiration and retention caps remain in force. Privacy behavior, the numerical verifier, form recognition and dossier-validator code were not changed. No prompt version or registry was changed.

## Files

Modified existing files:

- `agents/dialogue.py`: public subject/code context, corrections, query preservation and clarification.
- `agents/schemas.py`: bounded public context fields.
- `telegram_bridge/contracts.py`: matching request/response context fields.
- `agents/intent_router.py`: precise code matching, legal source routing and Arabic intent correction.
- `agents/retriever.py`: exact indexed Qdrant row retrieval for explicit procedure codes.
- `agents/checklist_builder.py`: preserve business rendering, exact official row identity, CIN scenario correction.
- `agents/answer.py` and `backend/agents_api.py`: inject the read-only corpus and use conservative legal extraction.

New implementation/test tools:

- `agents/legal_evidence.py`.
- `tests/test_post_audit_fixes.py`.
- `scripts/post_audit_regression.py`, `scripts/run_candidate_integration.py`, `scripts/post_audit_integrity.py`, `scripts/post_audit_report.py`.
- This report and separate `data/evaluation/post_audit_*` evidence/backup artifacts.

## Before and after

| Confirmed case | Audit / reproduced behavior | Candidate behavior |
|---|---|---|
| Fresh-context RNE fee/deadline questions | 0/190 requested factual answers; source-only rendering | 190/190 code-associated source values retained |
| Context-free RNE rows | 188/190 exact source facts | 190/190; I 001/I 002 no longer substituted |
| Natural lost-CIN question | First-application checklist | Official combined theft/loss/damage checklist |
| Arabic passport loss titles | Some document/fee/condition questions routed as deadlines | All 72 guide scenario and 18 fee queries have the original expected intents |
| Law 52/2018 Article 3 | Centre-creation content from another provision | Exact data-exchange provision and its extracted list |
| Law 52/2018 Article 16 | Invented definitions of amendments/changes | Exact trader-status presumption and effects against third parties |
| Name reservation | Validity period could become delivery time | Verbatim provision distinguishes issuance, validity and renewal |
| Beneficial-owner access follow-up | Generic association-registration answer | Same access-order subject, distinct authority/public provisions, or clarification |

Production reproduction: `data/evaluation/post_audit_reproduction.json`. Original expectations and original result files remain intact.

## Executed regression results

- Unit/isolated suite: **821 tests**, failures 0, errors 0, skipped 0. This includes the original 285 tests and 536 added regressions.
- Existing integration suite: **41 tests**, failures 0, errors 0, skipped 0. Webhook constants are redirected to the isolated candidate; existing test bodies/expectations are unchanged. Telegram transport is mocked in bridge tests. Qdrant round-trip tests use temporary test collections and clean them up.
- Original-case n8n replay: **632/632 executed**, all HTTP-completed; no failed original automatic source/contract diagnostics.

| Original case group | Executed | HTTP completed | Exact fact correct/assessed | Original intent-label match/assessed | Failed source/contract diagnostics |
|---|---:|---:|---:|---:|---:|
| guide_scenario | 72 | 72 | 72/72 | 72/72 | 0 |
| direct_factual | 30 | 30 | 0/0 | 25/30 | 0 |
| multi_turn | 18 | 18 | 0/0 | 17/18 | 0 |
| multilingual | 12 | 12 | 0/0 | 4/12 | 0 |
| upload | 8 | 8 | 0/0 | 0/0 | 0 |
| formalities_row | 190 | 190 | 190/190 | 190/190 | 0 |
| unsupported_birth_certificate | 4 | 4 | 0/0 | 4/4 | 0 |
| dialogue_regression | 2 | 2 | 0/0 | 2/2 | 0 |
| upload_error | 4 | 4 | 0/0 | 0/0 | 0 |
| unsupported_upload | 2 | 2 | 0/0 | 0/0 | 0 |
| formalities_row_dialogue | 190 | 190 | 190/190 | 190/190 | 0 |
| guide_fee | 18 | 18 | 16/16 | 18/18 | 0 |
| fresh_cin_profile | 4 | 4 | 4/4 | 4/4 | 0 |
| fresh_passport_profile | 8 | 8 | 8/8 | 8/8 | 0 |
| fee_service | 37 | 37 | 0/0 | 37/37 | 0 |
| fee_condition | 3 | 3 | 0/0 | 3/3 | 0 |
| scenario_specific | 18 | 18 | 0/0 | 4/18 | 0 |
| adversarial | 12 | 12 | 0/0 | 4/12 | 0 |

`0/0` means not assessed by that exact-fact diagnostic, not incorrect and not passed semantically. The two guide-fee cases without an explicit printed amount are excluded from that amount denominator.

Separate measurements:

- **Exact requested-source facts: 480/480**, versus 281/480 in the audit. This is the same restricted source-span/scenario/code check, not global answer accuracy.
- **Exact indexed-row retrieval: 380/380**, with retained `/agents/retrieve` traces.
- **Fee-service unit/rate quote retention: 37/37**. Quote retention alone does not independently prove interpretation of a fee column or individual applicability.
- **Citation provenance: 1462/1462** returned structured citations match original manifest URL and SHA. This measures provenance, not semantic citation correctness.
- **Legal subject context: 18/18** original legal follow-ups preserve the exact source subject. Fresh/existing code context, correction, topic reset, bridge round-trip and session expiration/isolation also have local regressions.
- **Known uncovered birth-certificate refusal: 4/4**. Invalid/corrupt/unsupported uploads: 6/6 safe-response contracts. Supported official form uploads: 8/8 across F-001/F-002, PDF/image, Form Check/Dossier Validation; no legal completeness certification.
- Legal responses: 120 source-excerpt replies and 10 clarifications across 130 legal cases, including 12 adversarial cases. They do not generate additional legal requirements. This is not a scored estimate of general refusal accuracy.
- Eight purposive source comparisons are recorded separately. Seven retain every selected source block verbatim. In the eighth, the legal clause is intact but its preceding section-heading prefix is omitted; the full-block mismatch remains recorded. These reviews address the confirmed article/list/threshold/confusion defects and are not a random sample or a global semantic score.

## Remaining disagreements and limits

**36/618 original intent-label comparisons differ.** Exact IDs, unchanged expected labels and actual labels are preserved in `post_audit_intent_differences.json`. Several broad legal questions contain fee, condition or document wording and receive a more specific intent than the original generic `procedure_info` expectation. The legal source path still controls their composition. These differences are not silently reclassified as passes, and production logic/ground truth was not changed merely to match labels. Review them before rollout.

General semantic correctness, semantic citation entailment and refusal accuracy across all questions are **not estimated**. Legal excerpts can be long, remain in the original source language and can contain existing extraction defects; the interface limitation notices support all four languages. This change prioritizes source fidelity over fluent legal paraphrase. Case-specific applicability, current legal validity, unsupported CIN-abroad scenarios, handwritten forms and real photographs remain unverified. Broad factual questions about form instructions that previously routed to upload help were outside these targeted repairs.

The 214 unselected audit cases were not rerun, including the 118 diagnostic retrieval probes. Their original observations remain available. No new real Telegram exchange or post-deployment upload success has been observed.

## Latency observations

Seconds, median / p95 on matching original case IDs:

| Group | Original audit | Final candidate |
|---|---:|---:|
| formalities_row_dialogue | 0.250 / 0.360 | 0.125 / 0.250 |
| formalities_row | 0.235 / 0.344 | 0.141 / 0.234 |
| direct_factual | 85.891 / 244.688 | 0.516 / 42.266 |
| upload | 1.984 / 2.953 | 2.204 / 5.218 |

Exact code retrieval avoids embedding/generation and still checks Qdrant's indexed point. Legal source composition avoids answer generation, but routing/retrieval and other English translations can still load local models. Runs used concurrency two and overlapped the existing integration suite on shared Ollama; model cold starts and scheduling make this an observational comparison, not a controlled latency benchmark. No general latency guarantee is made.

## Preservation and current health

Integrity captured at 2026-10-17T14:38:36.540257+00:00:

- Original corpus, source registry, processed chunks, all original `full_document_coverage*` artifacts, prompts, RAG implementation, verification, form helper and dossier validator: unchanged hashes; protected changes found: 0.
- Qdrant: all 272 structure and 174 recursive point IDs/payloads unchanged. Actual collection snapshots are downloaded under `data/evaluation/post_audit_backup/qdrant/` with checksums.
- Active workflow 03 unchanged: True. Backup: `post_audit_backup/active_workflow.json`.
- Final candidate backend source hashes match the reviewed host files (nine checked files). Final bridge image context-contract smoke test passed with network disabled.
- `.env` was not copied into reports, snapshots or images. Its token was not displayed. Uploaded personal documents were not used. Logs retain only existing routing/count/timing metadata.

| Production service | State | Health | Same container as audit |
|---|---|---|---|
| backend | running | healthy | True |
| n8n | running | healthy | True |
| qdrant | running | healthy | True |
| telegram-bridge | running | healthy | True |

Production backend and candidate backend health endpoints report Qdrant/Ollama reachable. Candidate endpoints are `http://localhost:8001/health` and `http://localhost:5679/webhook/assistant`; the ordinary production endpoints remain ports 8000 and 5678. No production container was recreated.

## Reproduce and review

```powershell
.venv/Scripts/python -m pytest -m "not integration" -q
.venv/Scripts/python scripts/run_candidate_integration.py
.venv/Scripts/python scripts/post_audit_regression.py --label candidate_final
.venv/Scripts/python scripts/post_audit_integrity.py
.venv/Scripts/python scripts/post_audit_report.py
```

The regression runner resumes its append-only candidate output. For an independent rerun, choose a new label. It loads the original questions, contexts and expectations without rewriting them. Do not use the old exhaustive audit runner to overwrite its protected baseline after code changes. The integration adapter redirects only webhook constants; availability probes still check the production service health endpoints, and retrieval service tests use the shared local services.

## Coordinated deployment after review — not executed

Preserved rollback tags: `tunisian-admin-assistant-backend:post-audit-before` and `tunisian-admin-assistant-telegram:post-audit-before`. Final candidate tags have suffix `:post-audit-final`; their exact image IDs are recorded in `post_audit_image_evidence.json`.

Only backend and bridge need replacement. n8n, Qdrant, Ollama, workflow state and corpus must remain untouched. The bridge must be updated too: the old wire schema would drop the new public subject/code fields. Recreating the bridge clears its in-memory sessions, so users should begin a new conversation after rollout.

```powershell
docker compose --profile telegram config --quiet
docker image tag tunisian-admin-assistant-backend:post-audit-final tunisian-admin-assistant-backend:latest
docker image tag tunisian-admin-assistant-telegram:post-audit-final tunisian-admin-assistant-telegram:latest
docker compose up -d --no-deps --no-build backend
docker compose --profile telegram up -d --no-deps --no-build telegram-bridge
docker compose --profile telegram ps
```

Check backend health, n8n health, both Qdrant collections and sanitized bridge authentication/polling metadata. Do not print Compose environment or raw credential-bearing error URLs. Replay the same cases with a new output label and production URLs:

```powershell
.venv/Scripts/python scripts/post_audit_regression.py --url http://localhost:5678/webhook/assistant --backend-url http://localhost:8000 --label production_after_review
```

Health and HTTP tests alone do not prove Telegram delivery.

## Rollback

```powershell
docker image tag tunisian-admin-assistant-backend:post-audit-before tunisian-admin-assistant-backend:latest
docker image tag tunisian-admin-assistant-telegram:post-audit-before tunisian-admin-assistant-telegram:latest
docker compose up -d --no-deps --no-build backend
docker compose --profile telegram up -d --no-deps --no-build telegram-bridge
```

No workflow, prompt, corpus or Qdrant restore is needed for this image rollback because none was changed. Collection snapshots and the workflow export are retained for recovery, not automatically restored. Existing source-file copies and pre-change hashes are under `post_audit_backup/` for source-level rollback.

## Manual Telegram acceptance — pending after rollout

Use only the user's authorized chat and public blank official forms; never put a token or personal document in this conversation.

1. `/start`, `/help`, `/language`: check English, French, Arabic and Derja menus and replies.
2. Ask the fee for `RNE C 012`; follow with “Et le délai ?”; correct to `RNE C 010.1`. Confirm exact codes/rows, distinguish filing deadlines from processing times, and compare to the official table. Test I 001/I 002 and an unavailable code.
3. Ask for CIN replacement after loss, theft and damage; confirm the existing combined official scenario, never first application.
4. Test the original Derja passport/photos dialogue; confirm first/renewal and residence clarifications, declared photos and remaining conditional items. Test domestic and abroad cases and the source-fee disagreement notice.
5. Ask who can access beneficial-ownership information, then conditions and deadlines. Confirm the access-order subject remains and authority/public provisions stay distinct. Change to name reservation, then CIN; confirm subject reset.
6. Ask Law 52/2018 Articles 3 and 16; compare exact provisions. Check beneficial-owner threshold/control fallbacks, the complete payment-method list, and reservation issuance versus validity.
7. In a second authorized test chat, select a different procedure. Confirm no context leaks. Test `/cancel`, topic correction and context expiration without sharing personal identifiers.
8. Upload public F-001/F-002 PDFs and rendered images in both `/form_check` and `/dossier_check`; verify fields, citations, missing supporting-document evidence and explicit non-certification.
9. Test a corrupt PDF, unsupported upload, uncovered birth-certificate procedure and requests to invent requirements or guarantee approval. No invented requirements, fabricated amounts, completeness certification or sensitive log values may appear.
10. Record actual sent messages and received replies before claiming Telegram success. None of these post-rollout Telegram interactions has yet been observed.
