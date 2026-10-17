# Technical gap register (audit, 2026-10-17)

## Scope and method

- **Audit only.** No production code, workflow, container, collection, dataset or prompt was changed.
- **System under test:** the production stack (n8n 127.0.0.1:5678, backend 127.0.0.1:8000), which runs the
  code hashed in `data/evaluation/full_document_coverage_deployment.json`. The isolated post-audit candidate
  stack is **not** production and is out of scope except where noted.
- **Probe types:** "Telegram shape" means a webhook request with `context` (as the live bridge sends it).
  "Web shape" means a request without `context` (as the web fallback, CLI and evaluation scripts send it).
- **Probe evidence:** 23 query-only requests sent on 2026-10-17 to the production webhook, plus 2 read-only
  backend route/retrieve calls. The raw output was kept in the audit scratchpad and is not committed, because
  it contains full replies.
- **Severity scale:**
  - CRITICAL: wrong or empty official information on a primary path, or a fabricated legal statement.
  - HIGH: systematic incorrect or incomplete answers, or evaluation validity at risk.
  - MEDIUM: scenario-specific defect or reliability gap.
  - LOW: hygiene or documentation.

---

### G-01 · CRITICAL · Telegram RNE fee/deadline replies are empty

- **Component:** `agents/dialogue.py` (canonical query) and the contextual rendering in
  `agents/checklist_builder.py`. Deployed code.
- **Expected:** a Telegram question on an RNE fee or deadline returns the official table row, as the
  context-free path does.
- **Actual:** every Telegram-shape RNE fee/deadline question returns exactly 751 characters. The reply has a
  🏢 icon, an empty body, three source links and a disclaimer, while reporting `found: true`. The same question
  without `context` returns the correct row (`vingt dinars (20 TND)`, `Trente jours …`).
- **Reproduction:**
  `POST /webhook/assistant {"text":"Quelle redevance pour RNE C 001 (Personne physique commerçant; Création) ?","language":"fr","context":{}}`
- **Evidence:**
  - Probes RNE-C001-fee, RNE-C001-delay, RNE-C010.1-fee and the demo question R01
    "Combien coûte l'immatriculation d'une SARL ?": 5/5 empty in Telegram shape, 2/2 correct in web shape.
  - Earlier audit: 190/190 fresh-context cases empty, 188/190 correct without context. I recomputed this
    from `full_document_coverage_results.jsonl`, where all 190 replies are 751 characters long.
- **Root cause:** verified by the earlier audit's code inspection and corroborated by the undeployed fix
  (repository `checklist_builder.py` lines 78–80 now bypass section filtering for business rows).
  Contextual rendering keeps only `fees`/`delay` sections, while RNE table sections are typed `other`.
- **Recommended fix:** deploy and regression-test the candidate fix, then run the 190-case dialogue group
  on production.
- **Academic impact:** high. RNE is one of 3 covered procedures, and Telegram is the declared primary
  interface. Demo step R01 fails if run in Telegram.

### G-02 · CRITICAL · A fabricated legal provision passes every safeguard

- **Component:** retrieval (`rag/hybrid.py`) → answerability gate → `agents/answer.py` + numeric verifier.
- **Expected:** "ماذا ينص الفصل 16 من قانون السجل الوطني للمؤسسات 52 لسنة 2018؟" is answered from Article 16
  ("registration is a simple presumption of merchant status") or refused.
- **Actual:**
  - After 175.6 s the system answered (`method: llm_grounded`) that Article 16 concerns "amendments and
    changes", and printed an invented quotation labelled "الفصل 16".
  - The citation is a valid URL of the correct law, but the content is fabricated.
- **Evidence:**
  - Probe LEGAL-art16.
  - Read-only `/agents/route` + `/agents/retrieve`: none of the 8 retrieved passages contains Article 16.
    The indexed heading is `الفصل16`, without a space.
- **Root cause (verified):**
  1. Retrieval misses the exact article.
  2. The gate accepts because the category came from rules.
  3. The numeric verifier accepts because 16, 52 and 2018 appear in the question.
  4. Citation validation checks only that passage numbers are in range, not entailment.
- **Recommended fix:**
  - Exact article lookup: normalise `الفصل\s*N` / `Article N` and filter by heading.
  - Refuse when the requested article is absent from the passages.
  - Add a span-entailment check for quoted text.
- **Academic impact:** high. It contradicts the report's "faithfulness 1.0", which is a lexical number check
  only.

### G-03 · HIGH · Legal answers confuse validity with delivery and misattribute articles

- **Component:** grounded answer (LLM) + verifier.
- **Actual (production probes, compared against `data/processed/chunks_structure.jsonl`):**
  - **Name reservation:** the reply says the certificate "is delivered within six months renewable once".
    Article 3 says it is delivered the **same day** and is **valid** for six months.
  - **Beneficial owner:** the reply attributes the 2-day public-request deadline to "article 4". The official
    text is **Art. 5**.
  - **Turn 1 of MT-BO:** the competent authorities are reduced to "the Centre … and the competent
    authorities". The enumerated list in Article 1 (Banque centrale, CTAF, …) is omitted.
- **Evidence:** probes LEGAL-name-reservation, LEGAL-BO-delay, MT-BO-turn1. The earlier audit's manual
  reviews also list 17 incorrect, 8 incomplete and 4 false refusals among 51 failure-targeted cases.
- **Root cause (hypothesis):** Mistral 7B paraphrasing. Verifiers check numbers, not their role (delivery
  vs validity) or article references.
- **Recommended fix:** an extractive answer mode for legal texts (quote the article, then summarise);
  article-number verification; prompt v3 evaluation on legal items.
- **Academic impact:** a defence question on "how do you know answers are correct?" will expose this.

### G-04 · HIGH · Deployed code ≠ repository; no version control

- **Component:** release process.
- **Actual:**
  - 8 backend files differ between the repository and the running container, and `agents/legal_evidence.py`
    is absent from the container.
  - `telegram_bridge/contracts.py` differs as well.
  - The project directory is not a git repository.
  - Unit tests (821 passed today) exercise the **repository** code, not production.
- **Evidence:** SHA-256 comparison (`docs/ARCHITECTURE_VERIFICATION.md` §1).
- **Recommended fix:**
  - Initialise git and tag the deployed state.
  - Deploy candidates only after the full regression; record the image digest in the test reports.
- **Academic impact:** results are hard to attribute to a code version, which weakens reproducibility.

### G-05 · HIGH · Multi-turn legal subject lost

- **Component:** `DialogueContext` (deployed version has no `legal_subject`) and `canonical_query`.
- **Actual:**
  - Turn 1 is about beneficial-owner information access.
  - Turn 2, "Et quelles sont les conditions ?", is answered with RNE **association registration** rows
    (50 TND) and generic form instructions. The answer cites unrelated sources.
- **Evidence:** probe MT-BO (production); earlier audit `rne-arrete-2026-35:multi_turn:001–003`.
- **Root cause (verified in code):** the context keeps only `category = business_registration`, so the
  follow-up query becomes generic.
- **Recommended fix:** deploy `legal_subject`/`rne_code` context (candidate); otherwise ask for
  clarification.

### G-06 · HIGH · Reported evaluation does not measure the production Telegram path

- **Component:** evaluation (`scripts/evaluate_agents.py`, report Tables 3–6).
- **Actual:**
  - The 84-item and 20-item agent results were produced 2026-10-16 (13:13 and 15:41), **before** the dialogue
    layer was deployed (2026-10-17). They used requests without `context`.
  - All 84 development items have `human_review: "pending"`. Labels were verified automatically
    (`verification_status`), not by a person.
- **Evidence:** file timestamps; `eval_set.jsonl` fields; G-01 shows the two paths diverge.
- **Recommended fix:** re-run the evaluation with `context: {}` (Telegram shape) on the deployed image, and
  report both shapes.
- **Academic impact:** an evaluator who tests through Telegram will observe behaviour that no reported
  metric covers.

### G-07 · MEDIUM · CIN loss answered with the first-application scenario

- **Actual:** "Quelles pièces pour une CIN après une perte ?" returns "Obtention de la carte d'identité
  nationale pour la première fois", without "Attestation de déclaration de perte".
  - This happens in **both** request shapes. The earlier audit reported only the fresh-context shape.
  - The `loss` hint is detected (returned context: `hints: ['loss']`).
- **Root cause (verified by the earlier audit):** the special-scenario filter requires every matched hint;
  the loss title also matches "modification".
- **Fix:** the candidate fix exists and is undeployed.

### G-08 · MEDIUM · Arabic "من أجل" parsed as a deadline keyword

- **Actual:** both Arabic passport-loss questions, about documents and about fees, are routed
  `processing_time` and return only the deadline and the place. The requested `شهادة ضياع جواز السفر` and
  `150 دينارا` are omitted.
- **Evidence:** probes AR-passport-loss-docs and AR-passport-loss-fee.
- **Root cause (verified):** keyword `أجل` in `agents/intent_router.py` (deployed) matches `من أجل`.
- **Fix:** candidate fix (word boundary plus exclusion).

### G-09 · MEDIUM · Questions about form instructions get a generic welcome

- **Actual:** "Que dit le formulaire sur les données manquantes … RNE-F-001 ?" → `form_help` → the welcome
  text, although the instruction text is indexed (7 chunks per form).
- **Evidence:** probe FORM-text-question.
- **Fix:** route `form_help` + text-only questions that name a known form to retrieval.

### G-10 · MEDIUM · n8n has no error branches

- **Actual:** none of the 16 nodes sets `onError` or retry, and there is no error workflow. Backend failures
  surface as raw n8n errors. The bridge (retry 3× then a localized error) and the web proxy (502) compensate.
- **Not exercised:** testing it would require stopping a production service.
- **Fix:** add "Continue (error output)" branches and a structured error response node.

### G-11 · MEDIUM · Stray unauthenticated Qdrant exposed on all interfaces

- **Component:** host, not this project's Compose file.
- **Actual:**
  - A container named `qdrant` (unpinned `qdrant/qdrant` image, created 2026-08-19) publishes
    `0.0.0.0:6333-6334` with no API key.
  - It holds one collection, `documents`. Its contents were not inspected.
- **Fix:** stop it or bind it to 127.0.0.1 before demonstrating on a shared network; confirm its owner.

### G-12 · MEDIUM · Documentation contradicts deployment state

- **Telegram reported as not live:** `docs/TELEGRAM_REPORT.md`, `docs/TELEGRAM_ACTIVATION.md` (status
  table) and report Section 6 state that no token is configured or that live use is pending. The bridge
  logs show live authentication and 4 real messages answered on 2026-10-17. Real uploads over Telegram have
  still not been observed.
- **Demo script:** `docs/DEMO_SCRIPT.md` R01 expects "RNE C 012 (50 TND …)". This holds for the CLI and
  web, not Telegram (G-01).
- **Fix:** update the status tables. In the defence, state precisely which paths are verified live.

### G-13 · LOW · Group chats share one dialogue session

- **Actual:** sessions are keyed by `chat.id`. In an in-process check (mocked Telegram and n8n), user 2 in
  a group inherited user 1's passport context. Private chats were isolated, both sequentially and with 6
  concurrent chats.
- **Fix:** key the session by `(chat.id, from.id)`, or restrict the bot to private chats.

### G-14 · LOW · High latency on LLM paths

- **Actual:**
  - Grounded answers took 23–176 s in the 5 probes (median 74 s).
  - EN translation took about 25–32 s.
  - Mistral was loaded with about 2.1 GB in VRAM on a 4 GB GPU, so it was partly offloaded to the CPU.
    The isolated candidate stack was sharing Ollama during the audit, which may have inflated these times.
- **Fix:** warm up the models before the demo, and avoid concurrent test runs during it.

### G-15 · LOW · Unused or disabled components

- **Grounded answer prompt:** `grounded_answer` v3 was evaluated and not adopted (v2 active).
- **Topic check:** `evidence_topic` v1 is wired but disabled (`EVIDENCE_TOPIC_CHECK=false`).
- **Retrieval workflow:** workflow 02 (Retrieval API) is active but not called by workflow 03.
- **Ingestion workflow:** workflow 01 is inactive.
- All of these are acceptable, but should be presented as experiments, not as runtime features.

### G-16 · LOW · Corpus coverage limits

- **Indexed:** 12 of 18 registry entries are indexed.
- **Not indexed, with documented reasons:** birth certificate (robots.txt AI opt-out), the passport
  application form (robots.txt), a scanned 2026 decree (no OCR in ingestion), and 2 sources not found.
- **Thin sources:** `rne-decree-law-2022-18-fr` yields only 6 extracted blocks.
- **Applicability:** `applicability` is `unverified` for every document.
- **Citation scheme:** Interior guides are cited with `http://` URLs (the registry URL is https).
- Correctly disclosed, but it limits the coverage of answers.

---

## Earlier audit findings: independent corroboration

| Earlier claim | Status | Evidence |
|---|---|---|
| 846 executed cases | VERIFIED | `full_document_coverage_results.jsonl`: 846 rows, all `completed` |
| 728 real n8n executions / 118 retrieval probes | VERIFIED | `transport` field counts |
| 12 indexed documents | VERIFIED | Qdrant: 272 + 174 points; inventory sums to 446 chunks across 12 documents |
| 190/190 contextual RNE cases without substantive answer | VERIFIED and REPRODUCED | Recomputed; 5/5 new production probes |
| 281/480 narrow factual checks conformant | VERIFIED (count) | `full_document_coverage_scored_results.json`: 281 true, 199 false. Narrow lexical criterion, not semantic accuracy. |
| Eight F-001/F-002 uploads recognised | VERIFIED | 8 upload cases; today 8/8 Telegram-adapter upload/dossier integration tests passed against production n8n (Telegram mocked) |
| CIN-NATURAL-LOSS | REPRODUCED, and broader | Also fails without context (G-07) |
| AR-INTENT-PHRASE | REPRODUCED | G-08 |
| LEGAL-SEMANTIC-GROUNDING | REPRODUCED | G-02, G-03 |
| LEGAL-CONTEXT-SUBJECT | REPRODUCED | G-05 |
| FORM-TEXT-ROUTING | REPRODUCED | G-09 |

## Special investigations (Section 5 of the audit brief)

| # | Topic | Finding |
|---|---|---|
| 1 | RNE fee/deadline with fresh context | FAILED in production (G-01) |
| 2 | Loss of exact RNE codes | FAILED on the Telegram path: no row at all. The web path returns the exact row first, then neighbouring rows (C 010.1 → C 010.1 followed by C 010.2 …). The candidate adds exact-key lookup. |
| 3 | Filtering removes official table rows | VERIFIED root cause of #1 |
| 4 | CIN loss scenario | FAILED (G-07) |
| 5 | Arabic passport intent confusion | FAILED for `من أجل` titles (G-08). The Derja renewal question now gets a residence clarification in Telegram shape, which avoids the earlier wrong "abroad" variant. |
| 6 | Beneficial-owner article references | FAILED (G-03) |
| 7 | Multi-turn legal subject | FAILED (G-05) |
| 8 | Incorrect refusals despite evidence | Earlier reviews: 4 `false_refusal` among 51 reviewed. Not re-measured. |
| 9 | Context reliability across Telegram users | Private chats isolated (in-process check). Group chats share context (G-13). |
| 10 | Correct citations hiding wrong answers | CONFIRMED: G-02, G-03 and G-05 all carry valid official citations. Citation validity (100 % in every run) is not evidence of correctness. |
