# Slide content (exported from FINAL_PRESENTATION.pptx by export_slide_content.py)

Each block lists the slide's professor section, presenter, target duration, the exact on-slide text (tables, charts and pictures summarised), the main message (first line of the speaker notes), the evidence (the source line), the layout and the transition. Do not edit by hand; regenerate after changing the deck.

## Slide 1

- **Section:** 1 · Introduction and Use Case (title)
- **Presenter:** Member 1
- **Target duration:** 28 s
- **Layout:** Title band
- **Main message:** Good morning. We are presenting the Tunisian Administrative Procedures Assistant: a local, source-grounded,
- **Evidence:** see notes
- **Transition:** next slide, same presenter

**On-slide text:**

- Tunisian Administrative Procedures Assistant
- A local, source-grounded multi-agent RAG system for multilingual administrative guidance
- Telegram · n8n · FastAPI · Qdrant · Ollama French · English · Arabic · Tunisian Derja (Arabic and Latin script)
- Advanced Deep Learning · Team of six · October 2026
- Member 1 · Member 2 · Member 3 · Member 4 · Member 5 · Member 6

## Slide 2

- **Section:** 1 · Introduction and Use Case
- **Presenter:** Member 1
- **Target duration:** 76 s
- **Layout:** Three cards
- **Main message:** Why this use case? Consider a citizen who wants to renew a passport or register a small company.
- **Evidence:** report §1; official pages interior passport guide FR/AR (data/raw), RNE formalities table
- **Transition:** next slide, same presenter

**On-slide text:**

- Fragmented, bilingual and risky to paraphrase
- Fragmented
- ▪  Ministry of the Interior guides (FR / AR) ▪  RNE table of 95 procedures with fees and deadlines ▪  Laws and decrees as Official Journal PDFs
- Language gap
- ▪  Official text: French and Arabic ▪  Users often write Tunisian Derja, in Latin script with digits: “9adech ya5ou wa9t el passbor?”
- High stakes
- ▪  FR and AR passport pages state different stamp duties: 20/60 vs 25/80 TND ▪  A fluent but invented fee or document costs citizens time and money

## Slide 3

- **Section:** 1 · Introduction and Use Case
- **Presenter:** Member 1
- **Target duration:** 79 s
- **Layout:** Numbered objectives + side panels
- **Main message:** So we set five objectives:
- **Evidence:** report §1 (objectives, scope); config/sources.yaml (exclusions with recorded reasons)
- **Transition:** Member 2 will now show you how the system is built.

**On-slide text:**

- Objectives, scope and expected value
- Answer only from verifiable official documents, with citations
- Refuse or ask for clarification when the corpus cannot answer
- Support FR, EN, AR and Derja without altering official text
- Check official forms and dossiers without certifying them
- Run on one laptop (4 GB GPU): no paid API, no data leaves the machine
- Scope Passports · National identity card (CIN) RNE business registration (95 procedures, 6 legal texts, forms F-001/F-002)
- Deliberately excluded Birth certificates: the only source opts out of AI use (robots.txt)
- Value: traceable answers, free, private, multilingual

## Slide 4

- **Section:** 2 · System Architecture and Automation Workflow
- **Presenter:** Member 2
- **Target duration:** 65 s
- **Layout:** Full-width architecture diagram (native shapes)
- **Main message:** Everything you see here runs locally, behind the loopback address.
- **Evidence:** docker-compose.yml; backend/main.py; backend/agents_api.py; live inventory 2026-10-18
- **Transition:** next slide, same presenter

**On-slide text:**

- Architecture: everything runs locally behind 127.0.0.1
- Citizen Telegram
- Web page / CLI same webhook
- Telegram bridge long polling, no inbound port
- n8n 2.41.3 wf 03 assistant (17 nodes) wf 02 retrieve API wf 01 ingest+index (inactive)
- FastAPI backend /agents/route /agents/retrieve /agents/checklist /agents/answer /agents/form-check /agents/dossier-check
- Qdrant 1.19 272 + 174 chunks
- Ollama 0.40.4 bge-m3 · mistral 7B translategemma 4B
- Official corpus 12 docs + SHA-256
- Design choices: Docker Compose · ports bound to 127.0.0.1 · Ollama on the host GPU (RTX 3050, 4 GB) reached via host.docker.internal · no paid API · uploads processed in memory, never indexed

## Slide 5

- **Section:** 2 · System Architecture and Automation Workflow
- **Presenter:** Member 2
- **Target duration:** 42 s
- **Layout:** Three real n8n screenshots
- **Main message:** These are real screenshots of our three workflows in the n8n editor.
- **Evidence:** workflows/*.json = live published versions (verified 2026-10-18); n8n editor screenshots
- **Transition:** next slide, same presenter

**On-slide text:**

- Three real n8n workflows
- Screenshots of the live editor (Zoom to Fit), 2026-10-18
- PICTURE: real screenshot
- 01 · Ingest and index
- 5 nodes · inactive · admin-only backend calls
- PICTURE: real screenshot
- 02 · Retrieval API
- 3 nodes · published · POST /webhook/retrieve
- PICTURE: real screenshot
- 03 · Assistant orchestration
- 17 nodes · published · POST /webhook/assistant
- Sticky-note frames document each stage; every agent call in 03 has an error output to a sanitised HTTP 503 reply.

## Slide 6

- **Section:** 2 · System Architecture and Automation Workflow
- **Presenter:** Member 2
- **Target duration:** 81 s
- **Layout:** Sequence of steps + latency cards
- **Main message:** Let me follow one request.
- **Evidence:** workflows/03_assistant_multi_agent.json; report §7 latency (final candidate)
- **Transition:** That difference shaped the whole design (to Member 3).

**On-slide text:**

- One request, end to end
- Workflow 03 routes on file, dossier mode and the router's decision
- Telegram user message
- Bridge language, session context
- Webhook File attached?
- Intent Router rules first, LLM fallback
- Direct reply? greeting / clarification
- RAG Retriever hybrid or exact code
- Checklist? next_agent
- Builder / Answer verbatim or verified
- Uploads (PDF, PNG, JPEG, Telegram photo) go to the Form-Filling Helper, or to the Dossier Validator in /dossier_check mode.
- Errors from any of the six agent calls go to one sanitised 503 reply; the bridge retries, then shows a localised message.
- Measured latency, final candidate alone on the GPU (median of 3):
- 0.08 s RNE row
- 0.19 s FR checklist
- 0.25 s Legal article
- 0.16 s PDF form
- 1.72 s Image OCR
- 17.5 s EN checklist
- 20–70 s LLM answer

## Slide 7

- **Section:** 3 · Prompt Engineering
- **Presenter:** Member 3
- **Target duration:** 48 s
- **Layout:** Table + technique chips
- **Main message:** We use a language model only where rules cannot decide, and we keep prompts as versioned files.
- **Evidence:** prompts/registry.yaml; agents/llm.py; agents/prompts.py; report Annex A
- **Transition:** next slide, same presenter

**On-slide text:**

- Prompt library: versioned and validated
- Language models are used only where rules cannot decide
- TABLE: Prompt | Role (model) | Active | Versions | Output validated in code // intent_router | Fallback classifier (Mistral 7B) | v1 | v1 | JSON; enums checked // grounded_answer | Answer from numbered passages (Mistral) | v2 | v1 · v2 · v3 | [n] citations exist; numbers in cited text // dialogue_understanding | User-declared facts (Mistral) | v3 | v1 · v2 · v3 | JSON schema; evidence = exact substring // translate_items | FR→EN checklist lines (TranslateGemma 4B) | v1 | v1 | same numbered lines and numbers // evidence_topic | Topic consistency (Mistral) | v1 (off) | v1 | disabled: unstable verdicts
- Techniques used
- Role prompting
- Grounding rules
- Citation format [n]
- Structured JSON / schema
- Few-shot examples
- Untrusted-input framing
- Language variable
- Length limits
- temperature 0
- Files: prompts/<name>/<version>.yaml · registry selects the active version · every response records its prompt_ref · versions are never edited in place

## Slide 8

- **Section:** 3 · Prompt Engineering
- **Presenter:** Member 3
- **Target duration:** 68 s
- **Layout:** Split before/after + table
- **Main message:** Our grounded-answer prompt went through three versions, all stored.
- **Evidence:** prompts/grounded_answer/v1-v3.yaml; data/evaluation/agent_results_hybrid.json (v1,v2) and agent_results_prompt_v3.json (v2,v3)
- **Transition:** next slide, same presenter

**On-slide text:**

- Before / after 1: grounded_answer v1 → v2
- Stored versions v1, v2, v3 — v3 was measured and not adopted
- BEFORE · v1 num_predict: 600 7. Be concise: at most 8 short sentences or bullet points. Problem: an Arabic answer was cut mid-sentence at 600 tokens; lists were summarised.
- AFTER · v2 (active) num_predict: 900 7. ... When the passages contain a list (documents, conditions), reproduce the relevant list items faithfully instead of summarising. Technique: output-length budget + explicit list-fidelity constraint
- TABLE: Same 12 answer-routed dev questions | v1 | v2 | v3 (run B) // Answer accepted by citation validation | 0.667 | 0.750 | 0.750 // Response language correct | 0.917 | 1.000 | 1.000 // Verified evidence span present | 0.273 | 0.091 | 0.182 // Median seconds | 29.2 | 26.5 | 31.7
- Same input R29 “What shareholding threshold makes someone a beneficial owner?” v1: LLM answer rejected → Arabic passage quoted to an English user v2: “...hold 20% or more of the capital...” [1, 2] — correct, in English

## Slide 9

- **Section:** 3 · Prompt Engineering
- **Presenter:** Member 3
- **Target duration:** 51 s
- **Layout:** Two before/after panels + two tables
- **Main message:** For the router, only one version exists, so we wrote a clearly labelled control baseline without our role,
- **Evidence:** data/evaluation/prompt_experiments/intent_router_results.json, dialogue_understanding_results.json (scripts/prompt_experiments.py)
- **Transition:** next slide, same presenter

**On-slide text:**

- Before / after 2 and 3: intent router and dialogue extractor
- intent_router: B0 → v1 B0 (controlled baseline, written 2026-10-18 — not historical): same enums and JSON mode; no role, no Derja/Latin-script note, no category definitions. v1 adds: role · multilingual + Arabizi notice · definitions (RNE, CIN) · “do not answer”.
- TABLE: 84 dev questions, LLM only | B0 | v1 // Category accuracy | 0.714 | 0.881 // Intent accuracy | 0.619 | 0.655 // Both correct | 0.452 | 0.643 // Valid enums | 0.988 | 0.952 // Median seconds | 3.7 | 3.1
- dialogue_understanding: v1 → v2 → v3 v1: schema in prose, pipe-separated enum hints. v2: “default {items: []}”, two few-shot examples, “never write 'not provided'”. v3: same text + JSON response schema enforced by Ollama (constrained decoding).
- TABLE: 18 synthetic declarations | v1 | v2 | v3 // Schema-valid outputs (raw) | 7/18 | 4/18 | 18/18 // Invented application / residence (raw) | 15 | 0 | 0 // Item precision after code validation | 0.727 | 0.818 | 0.632 // Item recall after code validation | 0.421 | 0.474 | 0.632 // Median seconds | 10.2 | 4.2 | 4.4
- Reading: v1's RNE definition fixed most 'general' errors (category +0.167); Derja intent did not improve and invalid enums rose slightly — the code rejects them. v2 removed 15 invented scenario facts; v3's schema made 18/18 outputs valid. Invented quantities are removed by code validation, not by the prompt.

## Slide 10

- **Section:** 3 · Prompt Engineering
- **Presenter:** Member 3
- **Target duration:** 35 s
- **Layout:** Before/after + lesson + compliance table
- **Main message:** For translation, a plain "translate this" baseline rewrote dates and dropped a photo size. Our prompt keeps
- **Evidence:** prompt_experiments/translate_items_results.json; docs/PROMPT_ENGINEERING.md; report §7; presentation/PROMPT_ENGINEERING_EVIDENCE.md
- **Transition:** Member 4 explains how we find the articles.

**On-slide text:**

- Before / after 4: translation — and the lesson we drew
- translate_items: B0 → v1 B0 (controlled baseline): “Translate this text from French into English.” v1: “...one line per item, keeping exactly the same numbering. Keep all numbers, amounts and measurements exactly as they are.”
- TABLE: 11 official FR checklist scenarios | B0 | v1 // Same numbered structure | 10/11 | 10/11 // Accepted by production validator | 4/11 | 10/11 // Median seconds | 17.0 | 15.9
- Withdrawn, not re-prompted: FR → AR “veuve” (widow) → “العوراء” (one-eyed woman); “timbre” → “الطوابق” (floors). Both passed format validation. Decision: Arabic and Derja users receive the official text.
- Lesson No prompt version made a 7B model paraphrase law reliably (Law 2018-52 Art. 16 was fabricated behind a valid citation). Fix was architectural: legal articles and table rows are now extracted verbatim, not generated.
- TABLE: Compliance | intent_router | grounded_answer | dialogue_und. | translate_items // Before version | B0 (labelled baseline) | v1 (historical) | v1 (historical) | B0 (labelled baseline) // Documented failure / test / outputs | yes / 84 dev / JSON | yes / 12 dev / JSON | yes / 18 synth. / JSON | yes / 11 official / JSON

## Slide 11

- **Section:** 4 · Retrieval-Augmented Generation
- **Presenter:** Member 4
- **Target duration:** 67 s
- **Layout:** Table + provenance flow + stat cards
- **Main message:** Our knowledge base is small on purpose: twelve official documents, each downloaded with its provenance.
- **Evidence:** data/raw/manifest.json; config/sources.yaml; rag/chunking.py; Qdrant collection info (read-only, 2026-10-18)
- **Transition:** next slide, same presenter

**On-slide text:**

- Official corpus: 12 documents, provenance first
- TABLE: Publisher | Indexed documents | Language // Ministry of the Interior | Passport guide (FR), passport guide (AR), national ID guide (FR) | FR · AR // RNE (registre-entreprises.tn) | Formalities table (95 procedures), forms F-001 and F-002 | FR · FR/AR // Legal texts via RNE | Law 2018-52 (AR), Decree 2022-298 fees (FR), Decree-law 2022-18 (FR) | AR · FR // Legal texts via RNE | Decrees 2019 (beneficial owners, name reservation, AR), Order of 13 Jan 2026 (FR) | AR · FR
- 18 candidate sources
- robots.txt + AI opt-out + TLS
- original + SHA-256 manifest
- typed text blocks (PyMuPDF / HTML)
- two chunkers
- structure-aware chunks (≤1200 chars)
- recursive chunks (1000 chars, 150 overlap)
- 1024-d
- BGE-M3 embeddings, cosine (Qdrant)
- Excluded with a recorded reason: birth certificate and passport-form pages (robots), one scanned decree without text layer

## Slide 12

- **Section:** 4 · Retrieval-Augmented Generation
- **Presenter:** Member 4
- **Target duration:** 52 s
- **Layout:** Pipeline diagram (native shapes)
- **Main message:** At query time the router's category becomes a filter.
- **Evidence:** rag/hybrid.py; agents/retriever.py; backend/settings.py (retrieval_mode=hybrid); report §4
- **Transition:** next slide, same presenter

**On-slide text:**

- Retrieval: hybrid fusion, exact keys, and a per-document cap
- Question + route category, intent, code?
- Dense: raw query
- Dense: expanded query
- BM25 + term normalisation
- Reciprocal rank fusion k = 60, category filter
- ≤ 2 chunks per document in the top 5
- RNE code in the question → exact payload scroll: the table row by key (a code is a key, not a meaning)
- ▪  Retrieval only finds the document and section; ▪  agents then read complete official units (section, row, article). ▪  Citations are copied from the payload, never generated.
- Arabizi word map and company-type normalisation feed BM25 (e.g. charika → شركة, “public limited company” → Société anonyme). No neural reranker (4 GB GPU).

## Slide 13

- **Section:** 4 · Retrieval-Augmented Generation
- **Presenter:** Member 4
- **Target duration:** 64 s
- **Layout:** Native column chart + table
- **Main message:** We measured retrieval against evidence spans verified verbatim in the official text, on 71 labelled development
- **Evidence:** retrieval_results_improved.json; docs/EVALUATION.md §2, §6; re-run read-only on 2026-10-18: identical Hit@5/MRR@5 for all 4 configurations (retrieval_results_reproduce_20261018.json)
- **Transition:** Member 5 explains the agents that use these passages.

**On-slide text:**

- Retrieval evaluation on verified evidence spans
- 71 labelled dev questions, k = 5; relevance = the official span occurs in the chunk
- CHART (column): categories [Dense raw, Agent (Phase 2), Hybrid RRF, Hybrid + cap 2] — Hit@5: 0.732, 0.718, 0.845, 0.873; MRR@5: 0.575, 0.591, 0.668, 0.675
- TABLE: Chunking (Hit@5) | Dense raw | Hybrid + cap // Structure-aware (272) | 0.732 | 0.873 // Recursive (174) | 0.817 | 0.775
- ▪  Ranking reverses: recursive wins dense, structure wins hybrid (one table row = one chunk). ▪  Held-out (20): hybrid ties dense at Hit@5 0.750; MRR@5 0.531 vs 0.635 — part of the dev gain was overfitting. ▪  Latin-script Derja: 0.000 → 0.714 Hit@5 (parallel subset).

## Slide 14

- **Section:** 5 · Multi-Agent Architecture
- **Presenter:** Member 5
- **Target duration:** 88 s
- **Layout:** Classification table + rationale
- **Main message:** We describe our system honestly as an orchestrated multi-agent architecture, not an autonomous one. n8n decides
- **Evidence:** backend/agents_api.py; agents/*.py; report Table 1 and Table 7 (final_regression.tex)
- **Transition:** next slide, same presenter

**On-slide text:**

- Orchestrated multi-agent architecture
- Specialised agents coordinated by n8n — no agent plans or chooses tools at run time
- TABLE: Component | Decision it owns | Type | LLM use // n8n workflow 03 | Branch on file, mode, next_agent; error replies | Orchestrator | none // Intent Router | Language, procedure, intent, clarification, dialogue state | Agent (rule-first) | fallback only // RAG Retriever | Which passages are evidence (fusion, exact key) | Deterministic | embeddings only // Checklist Builder | Official scenario and sections quoted verbatim; FR/AR conflicts | Deterministic + LLM | FR→EN translation // Grounded Answer | Extract article/row, generate, or refuse | Agent | Mistral 7B + verifiers // Form-Filling Helper | Form identity, field statuses | Deterministic | none (OCR) // Dossier Validator | Readiness report; composes 3 agents | Deterministic | none
- Why separate agents?
- ▪  Lists must be complete and verbatim ▪  Procedure codes are keys ▪  Legal text must not be paraphrased by a 7B model ▪  Forms need geometry and OCR ▪  Readiness is never certified by a model
- Evidence of the cost of one generic path: before the dedicated paths, all 190 RNE follow-ups returned only links, and the official legal passage appeared in 1 of 30 legal answers. After: 190/190 and 26/30 on the same 728 replayed cases.

## Slide 15

- **Section:** 6 · Multimodality
- **Presenter:** Member 5
- **Target duration:** 88 s
- **Layout:** Pipeline + results table + stat card
- **Main message:** Citizens can also send a form as a PDF, a scan or a phone photo.
- **Evidence:** agents/form_helper.py; agents/dossier_validator.py; data/evaluation/multimodal_eval_results.json (scripts/multimodal_eval.py). Filled text = neutral word 'placeholder'.
- **Transition:** Now Member 6 will show the system live.

**On-slide text:**

- Multimodality: official forms as PDF, scan or photo
- Upload type, signature, ≤10 MB
- Text layer? PDF geometry
- Deskew + OCR Tesseract ara+fra
- RANSAC homography anchor words → blank form
- Ink per field vs blank template
- Statuses filled / empty / unreadable
- TABLE: Case (fixtures derived from official blank forms) | Method | Result | s // Official blank F-001 (PDF) | text_layer | 0 filled / 7 fields | 0.08 // Official blank F-002 (PDF) | text_layer | 0 filled / 8 fields | 0.06 // F-002 with 5 fields filled ('placeholder', synthetic) | text_layer | 5 filled / 8 fields | 0.08 // F-001 with 3 filled fields rendered to PNG (200 dpi) | ocr_ink | 3 filled / 7 fields | 2.27 // F-001 with 3 filled fields rendered to JPEG, rotated 3 degrees | ocr_ink | 3 filled / 7 fields | 2.44 // Corrupt PDF (first 5 KB of F-001) | ocr | not recognised | 0.02 // Unsupported type (text/plain) | — | unsupported file type text/plain | 0.00 // Oversized upload (11 MB of zeros declared as PNG) | — | file larger than 10 MB | 0.22
- 13/13
- multimodal cases behave as expected (candidate backend, 2026-10-18)
- Dossier Validator Keeps apart: field status · official requirements quoted verbatim · completeness, which is never certified (no official RNE list exists).

## Slide 16

- **Section:** 7 · Live Demonstration and Evaluation
- **Presenter:** Member 6
- **Target duration:** 55 s (+ demo time)
- **Layout:** Four demo rows
- **Main message:** We chose four interactions on fast, deterministic paths, so that the demo does not depend on a slow model.
- **Evidence:** presentation/LIVE_DEMO_SCRIPT.md; latencies from report §7 and data/evaluation/rc_20261018b_multilingual_results.json
- **Transition:** next slide, same presenter

**On-slide text:**

- Live demonstration
- Four interactions chosen for fast, deterministic paths (≈ 90 s in total)
- FR
- Quels documents pour renouveler mon passeport ? J'habite en Tunisie.
- Checklist Builder · verbatim official list + source
- ≈ 0.2 s
- FR
- Et combien ça coûte ?
- Follow-up keeps context · fee section (timbre) + FR/AR conflict note
- ≈ 0.2 s
- Derja
- 9adech el ma3loum mta3 RNE C 012?
- Exact official RNE row by key · Arabic header
- < 1 s
- Photo
- /form_check + photo of blank F-001
- OCR + homography · 7 fields reported empty
- ≈ 2.5 s
- Fallback: if the live bot is slow, show the recorded results in data/evaluation/rc_20261018b_multilingual_results.json and the n8n execution view. Grounded LLM answers (20–70 s) are shown from recordings only.

## Slide 17

- **Section:** 7 · Live Demonstration and Evaluation
- **Presenter:** Member 6
- **Target duration:** 53 s
- **Layout:** Before/after stat cards + table
- **Main message:** Before release, an independent audit replayed 728 end-to-end cases through n8n.
- **Evidence:** report/tables/final_regression.tex; rc_20261018b_replay_results.jsonl (scripts/score_replay.py); rc_20261018b_multilingual_results.json; pytest
- **Transition:** next slide, same presenter

**On-slide text:**

- Evaluation: what the end-to-end audit changed
- Same 728 audit cases replayed through n8n: original production vs final candidate
- before → after
- 0/190  →  190/190
- RNE fee/deadline with chat context: exact row
- before → after
- 281/480  →  480/480
- Targeted official facts present
- before → after
- 1/30  →  26/30
- Legal answers containing the official passage
- before → after
- 0/10  →  10/10
- Form-instruction answers with the official passage
- TABLE: Check | Result // Fabricated legal provision (Law 2018-52 Art. 16) | yes → no // Citation URLs found in the official manifest | 1547/1547 // Release candidate rc-20261018b, same 728 cases: all 17 replay metrics | identical to final candidate // Multilingual parallel subset, 36 questions (rc-20261018b): 18 evidence, 4 correct refusals, 14 clarification questions, 0 failures | 0 failures (36/36 as designed) // Behaviour cases: clarification, follow-up, RNE codes, out-of-scope, carte grise, injection | 13/13 // Unit and regression tests (no services needed) | 1097 passed, 5 skipped; integration 37/37 on the rc stack

## Slide 18

- **Section:** 8 · Conclusion and Future Improvements
- **Presenter:** Member 6
- **Target duration:** 30 s
- **Layout:** Two columns
- **Main message:** Our limits are real:
- **Evidence:** report §8; docs/EVALUATION.md; docs/SECURITY_PHASE2_ACTIVATION_PLAN.md
- **Transition:** next slide, same presenter

**On-slide text:**

- Limitations and future improvements
- Limitations
- ▪  Small corpus (12 documents); legal currency unverified ▪  No official RNE list of supporting documents ▪  Latin-script Derja retrieval weakest (0.714 Hit@5) ▪  LLM answers slow on 4 GB (20–70 s) ▪  No evaluation on real handwriting or photographs ▪  Labels written by the team; human review pending
- Future improvements
- ▪  Human-reviewed labels and a larger held-out set ▪  Activate agent and webhook keys (phase 2 plan ready) ▪  Arabic legal translation with expert validation ▪  Semantic answer–evidence check (H17 type errors) ▪  More procedures from official sources that allow reuse ▪  GPU with more memory → reranker, faster answers

## Slide 19

- **Section:** 8 · Conclusion and Future Improvements
- **Presenter:** Member 6
- **Target duration:** 31 s
- **Layout:** Four statement cards
- **Main message:** To conclude:
- **Evidence:** see notes
- **Transition:** —

**On-slide text:**

- Conclusion
- Grounded by construction Lists, table rows, legal articles and form instructions are quoted verbatim; generation is fenced and verified.
- Measured, not assumed Retrieval on verified spans, held-out and independent end-to-end audit; failures reported, not hidden.
- Local and multilingual FR, EN, AR and Derja on one laptop: no paid API, no data leaves the machine.
- Main lesson Perfect citation metrics hid empty and fabricated answers. The fix was architectural: extract, do not paraphrase.
- Thank you — questions welcome (10 minutes).

## Slide 20

- **Section:** backup
- **Presenter:** —
- **Target duration:** backup only
- **Layout:** Divider
- **Main message:** Backup divider: no speech.
- **Evidence:** see notes
- **Transition:** —

**On-slide text:**

- Backup slides (not part of the 20-minute talk)

## Slide 21

- **Section:** 7 · Live Demonstration and Evaluation
- **Presenter:** All members
- **Target duration:** backup only
- **Layout:** Table + bullets
- **Main message:** Security. The candidate closes the admin endpoints by default, and makes agent and webhook keys optional. We
- **Evidence:** backend/main.py; backend/agents_api.py; docs/SECURITY_PHASE2_ACTIVATION_PLAN.md
- **Transition:** —

**On-slide text:**

- Backup · Security controls and phase-2 activation
- TABLE: Control | Status in validated candidate | Production today // Admin endpoints (/ingestion/run, /index/run) | 403 unless ADMIN_API_KEY set; 401 on wrong key | no authentication (older image) // Agent endpoints (/agents/*, /retrieve) | open while AGENT_API_KEY unset; 401 when set | open // Assistant webhook (X-Assistant-Key) | bridge sends it when configured; n8n Header Auth | not configured // Request size | 413 above 15 MB; uploads ≤ 10 MB | uploads ≤ 10 MB // Network | all ports on 127.0.0.1; Ollama loopback only | same
- ▪  Order: create n8n Header Auth credentials → attach to the 7 agent nodes (harmless while keys unset) → set AGENT_API_KEY and recreate backend → set ASSISTANT_WEBHOOK_KEY and recreate bridge → enable webhook auth. ▪  Workflow 03 maps any backend error (including 401) to 503: a key mismatch looks like an outage — smoke-test after every step. ▪  No step is executed without the owner's approval.

## Slide 22

- **Section:** 4 · Retrieval-Augmented Generation
- **Presenter:** Member 4
- **Target duration:** backup only
- **Layout:** Table + native chart
- **Main message:** Full retrieval table. All eight configurations, plus Hit@5 per language on the parallel subset.
- **Evidence:** data/evaluation/retrieval_results_improved.json (overall and parallel_by_language)
- **Transition:** —

**On-slide text:**

- Backup · Full retrieval comparison (71 dev questions, k = 5)
- TABLE: Configuration | R@1 | R@3 | R@5 | MRR@5 | Hit@5 // Dense raw · structure | 0.465 | 0.676 | 0.718 | 0.575 | 0.732 // Dense raw · recursive | 0.528 | 0.725 | 0.803 | 0.642 | 0.817 // Agent + normalisation · structure | 0.507 | 0.662 | 0.711 | 0.591 | 0.718 // Agent + normalisation · recursive | 0.415 | 0.556 | 0.648 | 0.504 | 0.662 // Hybrid RRF · structure | 0.549 | 0.768 | 0.831 | 0.668 | 0.845 // Hybrid + cap 2 · structure | 0.549 | 0.782 | 0.859 | 0.675 | 0.873 // Hybrid + cap 2 · recursive | 0.507 | 0.711 | 0.768 | 0.613 | 0.775 // Hybrid + cap 3 · structure | 0.549 | 0.768 | 0.852 | 0.669 | 0.859
- CHART (column): categories [fr, en, ar, derja, derja-latin] — Dense raw: 1.000, 1.000, 0.714, 0.750, 0.000; Hybrid + cap: 1.000, 1.000, 1.000, 1.000, 0.714

## Slide 23

- **Section:** 7 · Live Demonstration and Evaluation
- **Presenter:** Member 6
- **Target duration:** backup only
- **Layout:** Table + bullets
- **Main message:** Numeric verifier. Every digit in a generated answer must appear in the cited passage, as digits or as number
- **Evidence:** report/tables/verification.tex; agents/verification.py; docs/EVALUATION.md §7
- **Transition:** —

**On-slide text:**

- Backup · Numeric evidence verifier (off → on)
- TABLE: Set | False accept off | on | False refusal off | on | Unsupp. numbers off | on // Development | 0.000 | 0.000 | 0.058 | 0.058 | 2/85 | 0/78 // Regression | 0.143 | 0.000 | 0.000 | 0.125 | 1/9 | 0/1 // Held-out | 0.250 | 0.000 | 0.000 | 0.125 | 1/9 | 0/1 // Test 1 | 0.250 | 0.250 | 0.000 | 0.100 | 2/19 | 0/17 // Test 2 | 0.167 | 0.167 | 0.833 | 1.000 | 2/7 | 0/8
- ▪  Every number written with digits in an LLM answer must occur in the cited passage (digits or number words: “خمسون ألف” = 50,000). ▪  H14: Mistral wrote “510,000 TND” for fifty thousand dinars — now refused instead of shown. Median cost 3 ms.

## Slide 24

- **Section:** 3 · Prompt Engineering
- **Presenter:** Member 3
- **Target duration:** backup only
- **Layout:** Table
- **Main message:** Dialogue prompt detail. The raw and the validated metrics for v1, v2 and v3 on identical inputs.
- **Evidence:** data/evaluation/prompt_experiments/dialogue_understanding_results.json; dialogue_messages.jsonl (synthetic, labelled)
- **Transition:** —

**On-slide text:**

- Backup · dialogue_understanding outputs (identical inputs)
- TABLE: Metric (18 synthetic messages, 4 languages) | v1 | v2 | v3 // Valid JSON (raw) | 16 | 18 | 18 // Schema-valid (raw) | 7 | 4 | 18 // Item precision (raw) | 0.643 | 0.619 | 0.619 // Item recall (raw) | 0.474 | 0.684 | 0.684 // Evidence exact substring (raw) | 30/37 | 16/21 | 20/21 // Spurious items on questions / injection (raw) | 3 | 5 | 5 // Invented quantities (raw) | 3 | 4 | 12 // Expected application / residence found (raw) | 6/6 | 0/6 | 0/6 // Invented application / residence (raw) | 15 | 0 | 0 // Item precision / recall after code validation | 0.727 / 0.421 | 0.818 / 0.474 | 0.632 / 0.632 // Invented quantities after code validation | 0 | 0 | 0 // Median seconds | 10.2 | 4.2 | 4.4

## Slide 25

- **Section:** 3 · Prompt Engineering
- **Presenter:** Member 3
- **Target duration:** backup only
- **Layout:** Native chart
- **Main message:** Router baseline vs v1 per language. The improvement is largest in English and smallest in Derja.
- **Evidence:** data/evaluation/prompt_experiments/intent_router_results.json. In production the keyword rules answer first; this measures the fallback prompt alone.
- **Transition:** —

**On-slide text:**

- Backup · intent_router B0 vs v1 by language (LLM path only)
- CHART (column): categories [fr (n=34), en (n=26), ar (n=11), derja (n=13)] — B0 both correct: 0.588, 0.500, 0.273, 0.154; v1 both correct: 0.706, 0.808, 0.545, 0.231
