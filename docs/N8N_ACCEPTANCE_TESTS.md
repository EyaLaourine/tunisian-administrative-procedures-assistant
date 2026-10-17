# Final manual acceptance matrix

Status: **planned**, except the static/mocked checks explicitly reported in [validation](N8N_VALIDATION_REPORT.md). Do not treat this matrix or historical Telegram transcripts as newly executed tests. Run application tests only after approved release, using official blank public test forms and no personal information. Record question/context, actual answer, selected document/procedure, passages, citation target and outcome. A working citation alone cannot establish correctness; check every substantive claim against its cited passage and scenario.

| ID | Input / context | Required behavior and evidence | Safe execution class |
|---|---|---|---|
| L1 | FR: « Quels documents pour un premier passeport en Tunisie ? » | Correct domestic procedure; supported items only; fee-source conflicts visible, citations resolve. | Approved HTTP acceptance; optional manual Telegram |
| L2 | EN: “Which documents for a first passport in Tunisia?” | English framing; same applicable official evidence; identify translation limitations. | Approved HTTP / manual Telegram |
| L3 | AR: « ما هي وثائق جواز السفر للمقيمين بتونس؟ » | Arabic answer, appropriate scenario and source language. | Approved HTTP / manual Telegram |
| L4 | Derja AR: « شنوة الأوراق باش نعمل باسبور؟ » | Supported procedure, comprehensible Derja framing; no fabricated conditions. | Approved HTTP / manual Telegram |
| L5 | Derja Latin: “Chnowa lewra9 bech naamel passeport?” then “3andi 4 souwar chamseya, chneya ne9es?” | Maintain first-application context; recognize photos already held; do not switch to loss/duplicate without evidence. Conditional items remain conditional. | Approved HTTP multi-turn / manual Telegram |
| L6 | After L1: « Et si je réside à l'étranger ? » | Switch residence scenario while retaining passport topic; correct consular evidence. | Approved HTTP multi-turn / manual Telegram |
| L7 | « Quels papiers ? » with no context | Clarify procedure, do not guess a checklist. | Approved HTTP / manual Telegram |
| L8 | Unsupported civil-status question or request for a guaranteed approval | Refuse unsupported facts/guarantees; clarify scope; no invented source. | Approved HTTP / manual Telegram |
| A1 | Named RNE formality with exact legal entity/type | Exact applicable row; ask clarification if formality/entity ambiguous. | Approved HTTP |
| A2 | RNE fee question followed by deadline question, same explicit formality | Preserve entity/procedure; exact official row and units; no cross-row fee/deadline mixing. | Approved HTTP multi-turn |
| A3 | CIN checklist; then renewal vs first application | Distinguish procedures supported by actual indexed source; do not extrapolate unsupported scenarios. | Approved HTTP |
| A4 | Ask about an article of an actually indexed act; then unrelated legal interpretation | Quote the exact act/article if found; source language/limits explicit; refuse unsupported interpretation. Requires reviewed backend module deployed. | Approved HTTP |
| A5 | Check every answer's citation URLs and key numerical claims | Match document title, passage, scenario and numbers; distinguish current validity from indexed historical text. | Read-only source inspection after answer |
| M1 | `/form_check`, official blank RNE F-001/F-002 PDF | Form helper only; request omits `mode`; identifies potential omissions with citations/limitations; no stored field values. | Manual Telegram after approval |
| M2 | `/dossier_check`, same blank PDF | Request `mode: dossier`; separate filled/missing/unreadable/unverifiable and supported/unverified requirements; informational, no legal certification. | Manual Telegram after approval |
| M3 | Public test-form image, no personal entries | OCR branch recognized; uncertain fields not asserted certain; same privacy/source protections. Real handwriting remains a separate unverified scenario. | Manual Telegram after approval |
| M4 | Unsupported document / corrupt PDF / unsupported MIME | Safe localized rejection/error, no internal trace or guessed form result. | Isolated HTTP then approved manual Telegram |
| M5 | File above configured 10 MB / declared body above configured 15 MB | Rejection before expensive processing; no personal data logs. Streaming/no-length body limit is a known gap, not a claimed pass. | Isolated mocked tests only first |
| S1 | Admin key absent, wrong, correct | Reviewed backend: absent configuration 403; missing/wrong when configured 401; correct passes dependency. Never execute real ingestion/indexing as an auth test. | Mocked focused tests executed |
| S2 | Agent key absent, wrong, correct | Optional key semantics; configured wrong/missing 401, correct reaches validation/service mock. Checklist shares router dependency but needs explicit endpoint acceptance later. | Mocked focused tests executed; isolated full-call acceptance pending |
| S3 | n8n `X-Assistant-Key` missing/wrong/correct | Enforced only after credential mapping; n8n auth rejects unauthorized requests; valid clients preserve contract. Exact platform error response recorded, not assumed. | Isolated credential test after approval, not executed |
| R1 | HTTP backend timeout, connection error, 401/403/422/429/500/502/503 | Six workflow 03 error outputs return sanitized 503; no success masquerade; no raw data. Distinguish transport errors from malformed 2xx. | Graph/expression checks executed; n8n execution simulation pending approval |
| R2 | Qdrant unavailable / Ollama unavailable | Safe refusal/error or deterministic supported fallback; no unsupported answer; bounded time. | Mocked service failure only; never stop production services |
| R3 | Empty retrieval / malformed 2xx response | Empty evidence refuses/clarifies. Malformed 2xx not comprehensively guarded by n8n; record limitations rather than claim success. | Isolated mock pipeline test after approval |
| T1 | `/start`, `/help`, `/language`, `/cancel`, all four menu languages | Commands/menus work; cancellation clears intended pending state/context; normal text unaffected. | Manual Telegram by user only after approved window |
| T2 | Two concurrent members / repeated request / HTTP retry | Session isolation; bounded requests; no duplicate Telegram reply; no personal data in sanitized logs. | Isolated bridge mocks + explicit manual Telegram acceptance pending |

Do not send unsolicited Telegram messages. Do not disable production backend/Qdrant/Ollama to simulate failures. Do not run workflow 01 or publish duplicate webhook paths. A future test record must distinguish observed success, failure, unsupported behavior and unexecuted/manual gates.
