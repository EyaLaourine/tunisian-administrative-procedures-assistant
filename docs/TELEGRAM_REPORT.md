# Telegram implementation and credential-free verification

Verification date: October 16, 2026, Tunisia local time.

Live deployment is pending. All Telegram network operations in automated tests are mocked. The real
local n8n/FastAPI stack is exercised separately; those tests are not real Telegram conversations.

## Ownership and architecture

The existing bridge, schemas, agent endpoints, workflow 03, environment names, Compose and tests were
inspected. Phase 3 changes in the backend and retrieval were preserved. This task did not modify
`rag/`, `agents/`, `prompts/`, `report/`, evaluation datasets, backend source or workflow 03, and did not
rebuild, recreate, import workflows into, or restart shared services. No user `.env` values were edited.
The already-present `TELEGRAM_BOT_TOKEN=` entry in `.env.example` was verified.

Requests follow the existing route: Telegram adapter → `POST /webhook/assistant` → n8n → existing
agents → bridge reply. No retrieval, orchestration or translation was added to the bridge. Tests use
the currently running backend image; this work does not deploy other engineers' Phase 3 source changes.

## Files changed in this update

- `telegram_bridge/bridge.py`: responsive polling with two bounded background requests, one per chat;
  cancellation suppresses pending answers and retries; Main menu/New question/Back callbacks; bounded
  callback session retention; final-message navigation; checklist-intent handling; safe API/download
  errors; proper long rate-limit waits; distinct form-result guidance and detected-language navigation.
- `telegram_bridge/ui.py`: localized menus, back/new-question actions, form-status explanations and
  busy messages. English, French, Arabic and Derja interfaces; official quotations unchanged.
- `telegram_bridge/contracts.py`: lightweight bridge-only wire models, compatible with backend APIs,
  without importing retrieval or OCR dependencies. Extra response metadata is retained.
- `telegram_bridge/__main__.py`: `--wait-for-token` idle mode with heartbeat and clean signal shutdown.
- `telegram_bridge/Dockerfile` and `telegram_bridge/requirements.txt` (new): separate minimal bridge image.
- `docker-compose.yml`: only the Telegram service block changed. Dedicated image/build, idle command,
  and only the token, upload limit, log level and n8n URL passed into the bridge environment.
- `tests/test_telegram_bridge.py`: expanded mocked tests, concurrency/cancellation, schema and deployment checks.
- `tests/test_telegram_integration.py` (new): real n8n/FastAPI tests with mocked Telegram and downloads.
- `README.md`: Telegram subsection updated.
- `docs/TELEGRAM_ACTIVATION.md` (new): private token setup, startup and live acceptance checklist.
- `docs/TELEGRAM_REPORT.md`: current status and evidence.

## Acceptance statuses

| Requirement | Status | Evidence |
|---|---|---|
| Bot commands | PASS | All 11 commands tested with mocked Telegram |
| Inline keyboards | PASS | Main menu, procedure/language selection, Back and New question |
| Multilingual messages | PASS | Four interfaces; real backend language selection; Latin-script Derja with digits |
| n8n integration | PASS | Real local webhook and schema-compatible production handlers |
| RAG answers and citations | PASS | Real source-based checklists; grounded-answer regression included below |
| PDF handling | PASS | Official blank RNE PDF recognised through real n8n and FastAPI |
| Image handling | PASS | PNG, JPEG and Telegram-photo adapter path recognised through real n8n/FastAPI |
| Security checks | PASS | Bounded uploads, signature checks, no upload storage/indexing, safe errors/logs, narrow environment |
| Automated tests | PASS | Results below |
| Docker configuration | PASS | Separate image built; bridge started alone; healthy token-pending mode; zero restart loop |
| Real Telegram connectivity | BLOCKED: TOKEN NOT PROVIDED | No live Bot API request attempted |
| Real Telegram conversation | BLOCKED: TOKEN NOT PROVIDED | No real incoming message and bot response observed |

PASS for a file type means safe routing/processing is tested, not that arbitrary forms or handwriting
are reliably recognised. This does not certify legal validity or administrative approval.

## Automated evidence

- Final tests without service dependencies: **174 passed**, 20 integration tests deselected; six existing
  dependency deprecation warnings. This includes **72 Telegram-specific tests**.
- Initial new real Telegram-adapter integration tests: 7 passed, 1 failed because the existing language
  detector classifies the supplied Arabic-script Derja spelling as `ar`, not `derja`. It still returned
  the correct official Arabic source. The expectation was corrected to describe the existing contract,
  and a separate explicit-Derja selection case was added. No backend language rules were changed.
- Corrected multilingual integration group: **5 passed**. Selected Derja is honoured, and Latin-script
  Derja with digits is detected correctly. PDF/PNG/JPEG/photo integration cases all passed in the first run.
- Final full integration regression: **20 passed**, no failures or skips, in 218.68 seconds.
  This includes the existing 11 service/assistant integration tests and 9 new Telegram-adapter tests.
  Telegram was mocked; n8n, FastAPI, Qdrant, Ollama and form analysis were real.
  The final navigation-language adjustment was covered by two additional isolated tests included in
  the 174-test result above.
- Compose validation: `docker compose --profile telegram config --quiet` passed.
- Isolated deployment: `docker compose --profile telegram up -d --no-deps --build telegram-bridge` passed.
- From the bridge container: n8n `/healthz` returned 200; FastAPI `/health` returned 200 with Qdrant and
  Ollama both ready. Existing shared services remained running throughout verification.
- Docker logs show `LIVE_CONNECTIVITY_PENDING`; the bridge is idle and healthy with restart count 0.
  That health status does not imply Telegram connectivity.

## Commands

`/start`, `/help`, `/language`, `/procedures`, `/passport`, `/business`, `/birth_certificate`, `/checklist`,
`/form_check`, `/privacy`, `/cancel`.

The welcome opens a compact main menu. Procedure selection offers passport, birth certificate and
business registration. Checklist prompts request circumstances without identity details. Selected
language persists. New question clears procedure/checklist context but retains the selected language.
`/cancel` clears preferences and suppresses the pending answer and subsequent retries. In-flight backend
processing can finish internally; its resource slot remains occupied until completion. Busy chats get
a clear wait/cancel message rather than unbounded queuing. Official quotations and evidence are unchanged.

## Privacy and reliability

Uploads are streamed into memory with a byte bound, checked against PDF/JPEG/PNG signatures and
forwarded only to the form-helper branch. No private file is written, permanently stored or indexed;
there are therefore no temporary upload files to delete. Captions, document contents, questions,
chat IDs and token-bearing exception messages are not logged. Telegram itself handles messages under
its own policies. The existing workflow disables execution data retention.

Plain text avoids Markdown/HTML injection. Responses are split within 4,000 UTF-16 units, including
emoji; navigation appears only on the last part. Timeouts, bounded exponential retries and Telegram
`retry_after` handling are tested. Ambiguous send timeouts are not retried. The process socket lock,
fixed container name and Telegram conflict handling prevent cooperative poller duplication. Update
deduplication remains process-local; crash recovery is not exactly once. Preferences expire after
30 minutes of inactivity and are capped at 1,000 chats. At most two upstream requests run at a time.
Daemon workers allow signal-driven shutdown even if an upstream call has not returned.

## Backend/source limitations preserved

- Some Arabic-script Derja spellings are labelled Arabic by the existing detector. The Derja selector
  is reliable; this bridge does not add its own language detector or change backend rules.
- Birth-certificate requirements lack a permitted official source. The command explains corpus limits.
- The passport application-form template is absent. Unknown forms receive no completeness conclusion.
- The current workflow returns recognition, missing-field labels, errors and a form URL, but omits
  per-field unreadable/not-found detail. The bridge distinguishes unreadable uploads, unsupported forms,
  potential omissions and required human review, and never invents per-field certainty.
- Handwriting and arbitrary real filled identity documents have not been validated. No personal identity
  documents were used in tests. Existing official-source applicability and fee discrepancy warnings remain.

## Activation and manual verification

No credential is needed now. When available, follow [the activation guide](TELEGRAM_ACTIVATION.md).
It covers Telegram → verified @BotFather → `/newbot` → name and username → private token → existing
`.env` → start the bridge → `/start` → actual end-to-end conversation and manual acceptance checklist.

Existing running stack:

```powershell
docker compose --profile telegram up -d --no-deps --build telegram-bridge
```

Fresh stack after README setup/index/workflow publication:

```powershell
docker compose --profile telegram up -d --build
```

The full command is validated by Compose configuration. This update deliberately executed only the
targeted command so another engineer's backend image and shared services were not rebuilt or restarted.

## Activation preflight — October 17, 2026 (Tunisia)

This section records only observations from the current activation attempt. Earlier unit/integration
results above remain historical; none constitutes a real Telegram conversation.

- Local `.env` exists. `TELEGRAM_BOT_TOKEN` is empty in that file, in the effective application
  configuration and in the running bridge environment. No secret values were printed.
- Token format validation could not run because no nonempty token was present. A syntactically valid
  token would still require a real Bot API authentication check before acceptance.
- A BotFather token issuance has not been observed. Personal Telegram account/sign-in state was not
  inspected. Browser/application interaction was not used because setup requires explicit approval.
- Docker Compose configuration validation passed. FastAPI `/health` and n8n `/healthz` returned HTTP 200;
  FastAPI reported Qdrant and Ollama ready.
- The bridge is healthy in `LIVE_CONNECTIVITY_PENDING` mode with restart count 0. A sanitized log scan
  found the pending marker and no authenticated-start marker, polling-conflict marker or HTTP 401 marker.
  Absence of errors in idle mode does not validate Telegram authentication or polling.
- All **92 Telegram unit tests passed**. Telegram network operations were mocked.
- `.gitignore` excludes `.env`, but this workspace has no Git metadata; tracked/published repository
  state cannot be audited here. Explicit Docker COPY rules exclude `.env`; no `.env` files were found
  under `/app` in the running bridge or backend container. Remote published artifacts were not audited.
- Added a minimal root `.dockerignore` excluding `.env` and `.env.*`, with `.env.example` allowed, so
  credentials are also excluded from future Docker build contexts. No Docker image was rebuilt.
- No services were restarted or recreated, no environment values changed, and no agent, RAG, backend
  or workflow source was modified.

**Credential-free live-n8n upload verification: 4 passed** in 48.70 seconds (9 other integration
cases deselected). Official blank RNE PDF and PNG uploads passed in both Form Check and Dossier
Validation modes. Telegram and file downloads were mocked; the n8n/FastAPI/RAG/form-analysis path
was real. This does not verify PDF/image transmission through Telegram.

Current live-activation statuses:

| Check | Observed result |
|---|---|
| BotFather issued a token | Not observed; no token found locally |
| Bridge authenticated to Telegram | BLOCKED: TOKEN NOT PROVIDED |
| Real Telegram message/reply exchange | BLOCKED: TOKEN NOT PROVIDED |
| Real Telegram PDF/image uploads | BLOCKED: TOKEN NOT PROVIDED |
| Dossier Validation through real Telegram | BLOCKED: TOKEN NOT PROVIDED |
| Complete Telegram-to-agents-to-Telegram chain | BLOCKED: TOKEN NOT PROVIDED |

Next manual action: open verified @BotFather in Telegram, sign in personally if prompted, send
`/newbot`, choose a display name and an available username ending in `bot`, and save its issued token
privately in the existing local `.env` entry `TELEGRAM_BOT_TOKEN`. Suggested display name:
`Tunisian Administrative Assistant`; username candidates: `TunisAdminGuideBot` and
`TunisAdminGuide2026Bot`. Availability has not been checked and must be confirmed by BotFather.
Never paste the token, login codes or account credentials into the conversation.
Official instructions: https://core.telegram.org/bots/tutorial#obtain-your-bot-token.

Once private configuration is confirmed, recheck token presence/format without printing it, verify
service readiness, and recreate only the bridge without rebuilding anything:

```powershell
docker compose --profile telegram up -d --no-deps telegram-bridge
```

Then verify real authentication with sanitized diagnostics and check for unauthorized responses and
polling conflicts. Do not run a separate `getUpdates` poller. Real user tests remain required for
`/start`, `/help`, `/language`, English/French/Arabic/Derja questions, citations, `/form_check` PDF,
`/dossier_check` PDF, an image, unsupported-question handling and `/cancel`. Inspect the actual chat
responses (using an explicitly authorized interface or user-observed evidence), not merely container
health, before marking any live result PASS. Record only outcomes, never tokens or personal documents.


## Live activation — October 17, 2026 (Tunisia)

- A nonempty token is now present in the authorized local `.env`. Its format passed a non-disclosing
  check, and the effective application configuration matches the local entry. Its value was not printed,
  copied into reports, or changed. BotFather issuance itself was not observed by the assistant.
- FastAPI and n8n returned HTTP 200; Qdrant and Ollama readiness were true. Compose validation passed.
- Recreated only `telegram-bridge` using `docker compose --profile telegram up -d --no-deps telegram-bridge`.
  No image build, backend restart, workflow change, agent change or RAG change was performed.
- Real Telegram `getMe` returned HTTP 200 with `ok: true`, identifying public bot username
  `TunisAdminGuideBot`. **Telegram authentication: PASS.**
- Real `getWebhookInfo` succeeded and reported no configured webhook, compatible with long polling.
  A sanitized bridge log scan found `telegram_bridge_started`, no pending-mode marker, and no polling
  conflict, API-error or polling-failure markers. Restart count was 0.
- At the first post-activation check, no answered-message event was observed. The user was instructed
  to send `/start` and a French passport question through https://t.me/TunisAdminGuideBot.
- **Real message/reply exchange: awaiting observation.** Authentication alone does not prove a real
  conversation. French/English/Arabic/Derja replies, citations, real Telegram PDF/image uploads,
  Form Check, Dossier Validation, unsupported questions and cancellation still require live acceptance.
- Previous mocked Telegram and real-local-n8n tests remain valid historical evidence, but are not
  reclassified as real Telegram upload or conversation tests.

Subsequent activation check: bridge health became **healthy**. No message-answer or message-failure
event had yet been observed; real conversation acceptance remains pending user interaction.


## First real Telegram conversation confirmed — October 17, 2026 (Tunisia)

- The user supplied the actual French passport-question reply received in Telegram. It contains
  a passport checklist, official Ministry of the Interior French/Arabic source URLs, a warning that
  the official language versions disagree on fee amounts, and an explicit current-applicability
  limitation. No administrative amount or legal applicability was independently certified here.
- Sanitized bridge diagnostics show a real `telegram_message_answered` event with `kind: text` and
  `agent: checklist_builder`, plus two answered events from `intent_router`. The scan showed no
  message-failure, send-failure or poll-failure events. Message contents and chat identifiers were
  not printed or copied into this report.
- **Real French administrative message/reply exchange: PASS**, supported by user-observed Telegram
  output and a successful production bridge reply event through the existing n8n assistant route.
- **Official citations and discrepancy/applicability warnings in that reply: PASS (observed).**
- The bridge remains healthy, with restart count 0. No additional restart or code change was needed.
- English, Arabic and Derja conversations, language selection, real PDF/image uploads, Form Check,
  Dossier Validation, explicit unsupported-question refusal, `/help` and `/cancel` remain unverified
  in live Telegram. The two intent-router events alone do not establish which commands/intents were
  tested. `/start` was requested, but its response was not separately supplied or observed.
- The missing-token blocker is resolved. Remaining live acceptance depends on the user's test
  interactions and observed replies; no claim is made that all Telegram features have passed.


## Real Telegram Dossier Validation confirmed — October 17, 2026 (Tunisia)

- After being instructed to upload the official blank RNE F-002 PDF using `/dossier_check`, the user
  supplied the dossier report actually received in Telegram. A corresponding production bridge event
  confirms `telegram_message_answered`, `kind: file`, `agent: dossier_validator`.
- **Real Telegram dossier-mode document upload and reply: PASS** for this supported blank-form test.
  The requested test file was the official PDF. Diagnostics intentionally log only `kind: file`, not
  filename or MIME type; PDF identification additionally relies on the user's test sequence.
- Observed report: 0 filled fields, 8 missing fields, 0 unreadable fields, 4 fields that cannot be
  verified, and 2 officially supported requirements. Unverified requirements and missing official
  supporting-document lists are explicitly distinguished. These counts describe the observed blank
  form test; they do not establish accuracy for arbitrary uploaded documents.
- The reply preserves official RNE PDF/formalities links and original Arabic quotations. It explicitly
  states that dossier completeness cannot be assessed from available supporting-document sources,
  does not certify legal completeness or official approval, and requires competent-administration review.
- The report also discloses that field detection has not been validated on real handwriting or real
  photographs. No claim of legal validity, complete supporting-document coverage or handwriting accuracy
  is made in this acceptance record.
- Bridge remains healthy, restart count 0; the sanitized scan showed no message/send/poll failure events.
  No code change, image rebuild, service restart or token disclosure was required for this test.
- Still pending live acceptance: ordinary `/form_check` mode, image/photo upload, explicit language-menu
  selection and multilingual question checks, `/help`, `/cancel`, `/start` response confirmation and
  unsupported-question refusal. The observed English dossier report confirms an English dossier reply,
  but does not alone prove language-selection persistence or an English natural-language conversation.


## Real Telegram ordinary Form Check confirmed — October 17, 2026 (Tunisia)

- The user supplied the actual reply received after `/form_check` and the official blank RNE F-002
  PDF upload. The reply explicitly identifies the automatic check as PDF and lists eight potentially
  empty fields, with the official RNE form URL and manual-verification/handwriting limitations.
- The production bridge records a subsequent `telegram_message_answered` event with `kind: file` and
  `agent: form_helper`, following the previously verified dossier-validator upload.
- **Real Telegram ordinary PDF Form Check and reply: PASS.** The observed agent switch confirms that
  choosing Form Check after Dossier Validation routes the upload back to the ordinary form-helper path.
- Observed citations, privacy notice and non-certification/manual-review wording: PASS. No claim is made
  that field values are correct or that the form is legally valid.
- Bridge remains healthy, restart count 0. No message/send/poll failure event appeared in the sanitized
  scan. No code, configuration, token or running service was changed for this verification.
- Real image/photo upload remains pending, as do explicit multilingual/menu/command/refusal checks
  not separately evidenced above. Both document modes have now been observed in real Telegram.


## Real Telegram image/OCR Form Check confirmed — October 17, 2026 (Tunisia)

- Following the request to upload an image of the same official blank RNE F-002 form, the user
  supplied the actual Telegram reply. It explicitly identifies the method as OCR, recognises the
  form and reports eight potentially missing fields. The official RNE citation, no-storage notice
  and manual-review/non-certification wording remain present.
- Sanitized bridge logs show another successful `kind: file`, `agent: form_helper` reply event after
  the prior ordinary PDF test. **Real Telegram image/OCR upload and reply: PASS** for this blank-form
  test, supported by the user-observed OCR reply and corresponding additional file-answer event.
- The exact image MIME type and whether Telegram sent it as a document or compressed photo are not
  established by these privacy-preserving logs. This does not validate all photo conditions,
  handwriting, arbitrary documents or correctness of filled field values.
- No message/send/poll failure event was observed in the sanitized scan. No code or service changes
  were needed. Explicit language-menu persistence, multilingual question checks and remaining
  command/refusal tests still require separate live evidence.


## Live French follow-up context defect and correction — October 17, 2026 (Tunisia)

- The user reported that the real Telegram follow-up `Et si je réside à l’étranger ?` received an
  uncovered-procedure response after a successful French passport question. This live follow-up
  acceptance check initially **FAILED**; French language persistence alone did not establish context correctness.
- Sanitized backend routing metadata showed the initial question routed to `passport`/`checklist`,
  followed by `birth_certificate`/`reply` for the follow-up, both in French. The bridge retained an
  earlier explicitly selected procedure and did not update it from the latest response's category.
- Corrected only `telegram_bridge/bridge.py`: retain the latest known procedure category returned by
  the existing router for text requests. The session stores only category metadata, never the user
  question or document values. A cancelled/cleared session is not recreated by a late response.
- Added three isolated regression cases in `tests/test_telegram_bridge.py` and two real-n8n cases in
  `tests/test_telegram_integration.py`. The latter cover a new conversation and a stale birth-certificate
  preference, followed by the exact passport question and residence-abroad follow-up.
- **95 Telegram unit tests passed. Two new real-n8n follow-up integration tests passed** in 17.85 seconds.
  Both retained passport context, detected the abroad hint, returned French checklist-builder answers
  and official citations, and did not return the uncovered-procedure message. Telegram was mocked in
  these regression tests; post-correction acceptance still requires a real Telegram repeat.
- No backend, agent, RAG, prompt or n8n workflow was modified or rebuilt. Only the bridge is being
  rebuilt/recreated to load this change. Its process-local language/mode/procedure preferences reset.

Deployment of the follow-up context correction completed: only the bridge image/container was
rebuilt/recreated; Compose reported healthy. A sanitized startup scan confirmed Telegram startup
authentication, no pending-mode marker, no polling-conflict marker and no polling-failure marker.
A user-observed repeat of the exact French follow-up is still pending.


## Corrected French follow-up confirmed in real Telegram — October 17, 2026 (Tunisia)

- The user supplied the actual passport reply for residents abroad after repeating the French
  question/follow-up test. The user initially stated that both replies were identical, then explicitly
  corrected that statement: the two responses are different.
- **Post-correction real French passport follow-up: PASS**, based on the user's supplied abroad
  response and clarification. The previously reported uncovered birth-certificate response is resolved
  for this tested conversation. Both replies concern passport guidance, and the follow-up selects
  the residence-abroad scenario.
- Four additional direct real-n8n checks in this verification returned the Tunisia-resident scenario
  for the initial question (with and without procedure context) and for explicit Tunisia residence;
  the context-bearing residence-abroad follow-up returned the abroad scenario. No repeated-response
  defect was reproduced. These four HTTP checks are distinct from real Telegram chat evidence.
- The abroad reply retains official Ministry source links and the current-applicability/legal-advice
  disclaimer. No current administrative fee or legal applicability was independently certified.
- No further code modification, image rebuild or service restart was performed for this clarification.
  Remaining live acceptance includes English/Arabic/Derja conversation and explicit language-selection
  persistence checks, plus commands/refusal checks not separately observed above.


## Real Telegram English passport reply confirmed — October 17, 2026 (Tunisia)

- After instructions to select English and ask the English passport question, the user supplied
  the actual English checklist received in Telegram. **Real English question/reply: PASS.**
- The reply preserves both official Ministry source URLs, the French/Arabic fee-discrepancy warning,
  a notice that the English text is an automatic translation and the official original prevails,
  and the current-applicability/legal-advice limitation. Original French alternative-scenario titles
  remain in their source language. No independent semantic/legal certification of the translation
  or current administrative amounts is claimed.
- This confirms an observed English reply in the instructed language-selection test. Persistence
  against differently worded or differently language-coded follow-ups is not established solely by
  an English question receiving an English answer.
- No code or service change was needed. Arabic and Derja live questions, remaining language-persistence
  checks and unobserved command/refusal checks remain pending.


## Real Telegram Arabic passport reply confirmed — October 17, 2026 (Tunisia)

- After instructions to select Arabic and ask the Arabic passport-renewal question, the user supplied
  the actual Arabic checklist received in Telegram. **Real Arabic question/reply: PASS.**
- The observed response contains Arabic official-source text, both Ministry source URLs, the warning
  about differences between the Arabic and French official versions, and the applicability/legal-advice
  limitation. No current fee, deadline or legal applicability is independently certified by this record.
- No code, token or service changes were needed. Derja, explicit cross-language preference persistence,
  and remaining command/refusal acceptance checks are still pending.


## Real Derja acceptance and incorrect inventory follow-up — October 17, 2026 (Tunisia)

- The user supplied an actual Telegram Latin-script Derja passport question and its reply. The first
  reply uses Derja interface headings, preserves official Arabic requirement quotations, includes
  both Ministry source URLs, and retains discrepancy/applicability warnings.
  **Real Latin-script Derja initial question/reply: PASS.** Sanitized backend metadata confirms
  `language: derja`, `category: passport`, `intent: required_documents`.
- The user's subsequent follow-up declares possession of four photographs and asks what is still
  missing. The actual reply incorrectly switches to the passport loss/theft/damage duplicate scenario.
  The user did not report losing a passport. **Personalized Derja inventory follow-up: FAIL.**
- Reproduced through the real n8n webhook with the bridge's passport category context and forced Derja:
  router hints were empty, yet the checklist builder returned the loss/theft scenario with `found: true`.
  This is distinct from the earlier cross-category bridge-memory issue: the passport category is retained,
  but the backend chooses an unsupported sub-scenario for this question. Source citations alone do not
  establish that the chosen scenario applies to the user.
- A second diagnostic request explicitly stating first application (`awel marra`) produced the
  `first_time` hint and the ordinary first-application/renewal scenario. This is a verified temporary
  disambiguation, not a correction of personalized missing-document reasoning.
- Needed agent-side follow-up: prevent selection of loss/theft-specific scenarios without a matching
  stated circumstance; preserve or clarify application scenario across inventory follow-ups; distinguish
  user-declared possession from verification of document conformity. Do not infer legal completeness.
- No agents, RAG, backend, workflow or bridge source was modified, and no service was rebuilt or restarted
  for this diagnostic. Agent-side correction remains pending under the user's work-ownership restriction.
- This failure prevents claiming complete live conversational acceptance. Previously observed successful
  French/English/Arabic replies, PDF/image uploads and both document modes remain separately recorded.
  User names, personal identifiers, document values and verbatim chat transcripts were not copied here.


## Authorized contextual-dialogue upgrade — October 17, 2026 (Tunisia)

The user explicitly authorized adapting dialogue/routing agents, context, versioned prompts, tests and
coordinated deployment. The earlier restriction on editing those specific components was lifted for
this upgrade. RAG, numerical verification, the form helper and Dossier Validator remain protected.

Implemented behavior:

- Production Telegram text requests carry bounded structured state: category, application scenario,
  residence category, declared document types/counts, pending intent and last intent. No message history,
  identity numbers, document field values or raw prior questions are stored in session state.
- Missing passport application/residence information triggers clarification. Facts already supplied
  are retained, and clarification replies resume the pending request.
- Inventory questions classify source items into declared available, still to prepare, and specification/
  quantity checks. Declared photos are not repeated as missing when their stated count matches the
  official source, but image specifications and legal conformity remain unverified.
- A first-application declaration excludes items explicitly about an earlier passport. Other conditional
  requirements keep the official wording; age/student eligibility and dossier completeness are not inferred.
- Loss/theft/change/pilgrimage scenarios cannot be selected without corresponding stated hints. Retrieval
  identifies an official guide; the builder can consider its complete existing scenario list rather than
  being forced into whichever sub-scenario happened to appear in the retrieved chunk.
- Fees, delay, submission-place and eligibility questions show their relevant section only. Specific
  item questions use the existing grounded-answer agent, even after an inventory has been declared.
- Existing evidence gates, numerical verification, source citations, validated-translation notices,
  conflicting-source warnings and applicability disclaimers remain active. No administrative requirement
  is generated by the new understanding prompt.
- Stateless HTTP clients omitting `context` preserve their existing interface. Upload payloads and both
  ordinary Form Check and Dossier Validation paths remain unchanged.

Understanding and validation:

- Common facts use deterministic language rules. For other self-reported facts, the local model uses
  the new versioned `dialogue_understanding` prompt. Earlier v1/v2 attempts exposed copied enum choices
  and missing evidence; those unsafe records were rejected. Active v3 constrains the JSON output schema
  and requires literal user-message evidence. Invalid individual records are discarded; unsupported
  quantities are not accepted. All earlier prompt versions are retained, not edited in place.
- A real local-model test with a collected-photographs paraphrase extracted the declared photo count
  correctly under v3. This test used controlled text, not a private document or identity data.
- Optional response-schema support was added to the generic prompt/client only for this new prompt.
  Tests verify that existing JSON prompts still send exactly `format: json`; verification source code
  and existing verifier prompts were not changed.

Verification so far:

- Final isolated/unit suite: **285 passed**, 41 integration cases deselected; six existing dependency warnings.
- Legacy/service integration regression: **33 passed** in 376.71 seconds. This includes the existing
  dossier, form, retrieval, grounded-answer and bridge tests, with real local services.
- Earlier contextual-dialogue run: 2 failed/4 passed. A fee reply still included the full document
  section; this was corrected and regression-tested. A first post-publication Derja probe returned
  legacy behavior; the exact case passed when repeated against the stable workflow.
- Subsequent six-case contextual-dialogue run: **6 passed** in 85.68 seconds. This verified the exact
  Derja conversation, French/English/Arabic personalization, focused fees, abroad-context changes and
  a grounded answer to a specific item question.
- Additional coverage now checks a specific item question after an inventory and the model-understood
  collected-photographs paraphrase. Final expanded live-n8n dialogue results are recorded below.
- Hash comparison verified **12 protected source files unchanged**, including RAG, verification,
  form-helper and Dossier Validator source. No official corpus, evaluation dataset or academic report
  was modified.

Deployment:

- Saved pre-change backend and bridge images under `:before-dialogue` tags and exported the active n8n
  workflow to `/tmp/assistant-before-dialogue.json` inside n8n for rollback.
- Built/replaced only the dialogue-related backend/bridge images, imported/published the context
  pass-through update to workflow 03, and restarted n8n to load that published version. Qdrant, Ollama
  and official-data volumes were preserved. Backend refinements were redeployed after regression fixes.
- The bridge is authenticated and healthy after deployment; sanitized scans found no polling conflict
  or polling-failure marker. No token was printed or copied into this report. Production dialogue mode
  is enabled; process-local conversation preferences reset during deployment.

New behavior still requires a user-observed repeat through real Telegram after /cancel and Derja
selection: the original passport question, the declaration of four photos, then first application in
Tunisia. Expected: clarification, retained declaration and a source-based remaining-document report,
with no loss/theft switch and no certification of legal completeness. These new HTTP/local-model tests
are not claimed as user-observed Telegram acceptance. Previous real messaging/upload tests remain
historical evidence for the earlier version.

Full design, affected files and manual check: `docs/DIALOGUE.md`.


Final contextual-dialogue validation and deployment:

- **8 expanded dialogue integration tests passed** in 165.76 seconds against the final deployed backend
  and live n8n workflow. These cover the exact three-turn Derja conversation, French/English/Arabic
  remaining-document flows, focused fee/abroad follow-ups, a grounded item question both before and
  after a declared inventory, and a real local-model interpretation of a collected-photographs paraphrase.
- **285 isolated/unit tests passed.** The **33 legacy/service integration tests also passed** in the
  separately executed non-regression run. They are not described as a single combined pytest run.
- The final backend includes the focused-question-after-inventory fix and schema-constrained extraction
  v3. v1 and v2 remain immutable historical prompt files. Optional JSON-schema support defaults to the
  exact former JSON format for all existing verifier prompts, covered by explicit request-body tests.
- Backend and bridge are healthy. The production bridge is authenticated, without polling-conflict
  or polling-failure markers in sanitized diagnostics. RAG, verification, form-helper and Dossier
  Validator source hashes remain unchanged. No credentials were printed or added to artifacts.
- The new context-aware dialogue is deployed, but **user-observed acceptance of this new conversational
  behavior in Telegram remains pending**. Authentication and previous real messaging/document tests
  are established separately; the new HTTP/Ollama tests are not mislabelled as real Telegram chat tests.
- Suggested real test: /cancel, select Derja, then ask the passport question, declare four photographs,
  and specify first application in Tunisia. Verify acknowledgment, clarification, no loss/theft jump,
  declared photos separated from remaining items, and explicit non-verification of specifications.
