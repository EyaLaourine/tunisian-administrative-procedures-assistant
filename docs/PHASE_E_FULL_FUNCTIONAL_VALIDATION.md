# Phase E: multilingual UX fixes and complete functional validation

Date: 2026-10-18. Branch: `fix/phase-e` (from `fix/conversational-understanding`). Release commit: `d994df7`.
Production was not modified; no deployment, restart, ingestion, indexing, production-Qdrant write or Telegram message.

**Verdict: PHASE E — READY FOR DEPLOYMENT APPROVAL**

## 1. Summary

| Item | Result |
|---|---|
| A1: gratitude language | Fixed. "يعطيك الصحة", "yaatik saha" and "3aychek" get "يعيشك، مرحبا بيك!…" in any conversation; the conversation language and the `/language` preference are not changed. |
| A2: irrelevant fee warning | Fixed. The discrepancy warning is shown only when the answer contains an amount or fees are asked for. |
| Additional defects found by the coverage run and fixed | 3: ambiguous CIN "change" request; RNE form questions sent to the LLM classifier and refused as out of scope; an English error fragment in localized file errors |
| Unit suite | **1327 passed**, 5 skipped (1264 at Phase D + 63 new) |
| Isolated end to end, final image | Coverage **60/60**; Phase D conversational **22/22**; language **26/26**; defect probes **16/16**; WF02 retrieval 5/5; error recovery 2/2 |
| Same suite on the current production backend (baseline) | 52/60, failing exactly the 8 defect turns fixed here |
| Multilingual evaluation | Identical to the accepted baseline in **49/49** records |
| Candidate | Backend only: `tunisian-admin-assistant-backend:rc-20261018-e` `sha256:69d7a7faab1bd9b474bde6c16f3ffe2c31b276a622b28a30c88cbdeea42ec1de` (64/64 files hash-identical to `d994df7`) |

## 2. The two UX defects

### A1: short gratitude in the wrong language

- **Observed:** "يعطيك الصحة" was answered "Avec plaisir ! Si vous avez une autre question, je suis là."
- **Root cause:** "يعطيك الصحة" contains no strong Derja marker, so detection was not confident. The small-talk reply
  therefore fell back to the conversation language (French in that session).
- **Fix** (`agents/conversation.py`, `agents/intent_router.py`, `agents/schemas.py`):
  - **Language of the expression itself** (`expression_language`), deterministic, with no RAG, OCR or LLM:
    - Derja-only expressions (يعطيك الصحة, يعيشك, yaatik/ya3tik saha, 3aychek, باهي, behi…) → Derja;
    - English (thanks, thank you…) → English;
    - French (merci, oui…) → French, or Derja when the conversation is Derja, since these words are everyday Derja;
    - shared Arabic-script words (شكرا, نعم) → Derja in a Derja conversation, otherwise MSA;
    - neutral words (ok) → the conversation language.
  - **Natural Derja reply:** "يعيشك، مرحبا بيك! كان عندك سؤال آخر، أنا هوني."
  - **The conversation is not redirected:** the deployed Telegram bridge stores `route.language` as the
    conversation language. For a pure courtesy message, `language` therefore keeps the conversation language and
    the new optional `reply_language` gives the reply's own language. The `/language` preference is never touched.
    This fix needs no bridge change; the isolated run caught an earlier variant that would have let a Derja
    thank-you switch the next "ok" to Derja.
  - **Unchanged:** mixed messages ("merci, et pour les frais ?") still route as fees questions.

### A2: fee-discrepancy warning attached to an unrelated answer

- **Observed:** "je veux savoir le lieu de depot" returned the submission place plus a warning about conflicting
  passport fees.
- **Root cause:** `ChecklistBuilder._procedure_guide` compared fee amounts between the parallel FR and AR passport
  guides and attached the warning **before** the answer's sections were chosen. The dialogue path then narrowed
  the sections to the requested focus (place, delay…) but kept the warning.
- **Fix** (`agents/checklist_builder.py`, `agents/schemas.py`):
  - The discrepancy is recorded structurally in `ChecklistResult.fee_discrepancy`, not by string matching.
  - `_attach_fee_warning()` adds it to the warnings only when the shown sections contain an amount or the intent
    is `fees`. It runs on both paths: the direct builder and the dialogue focus filter.
  - Official items, citations and the general disclaimer are untouched.
- **Scope:**
  - Passports: the only corpus documents with a parallel version.
  - CIN: one French guide, so no discrepancy is possible.
  - RNE: the business path has no parallel-version warning.
  - A real conflict that affects the answer is still shown: fee answers, and document lists that include the fee
    line.
- **Measured on the real corpus** (production code → fixed): the warning was shown on place, delay, fees and
  documents answers before. It is now shown on **fees and documents only**.

## 3. Additional defects found by the coverage run (fixed, low-risk)

| # | Defect (observed in the isolated baseline) | Fix |
|---|---|---|
| 1 | "Je veux changer ma carte d'identité" went straight to a grounded answer. The CIN guide has two "change" cases (data change; loss, theft or damage). | `agents/dialogue.py`: for a CIN, a bare change verb asks which official case applies (first card, renewal, data change, loss/theft/damage); "oui" re-asks it. The validated "baddel CIN" → modification mapping is kept. |
| 2 | "Que contient le formulaire F-001 ?" got the out-of-scope refusal. With the LLM fallback on, as in production, the LLM classified it before the deterministic form check ran. | `agents/intent_router.py`: `identify_form()` runs before the LLM fallback; one LLM call fewer. |
| 3 | A corrupt PDF gave "Je n'ai pas pu lire ce fichier : unreadable PDF", with an English fragment | `agents/form_helper.py`, `agents/i18n.py`: localized reason texts (en/fr/ar/derja); the technical `error` field is unchanged |

## 4. Changed files (commits `9a63499`, `6934e04`, `10b66b1`, `d994df7`)

| File | Change |
|---|---|
| `agents/conversation.py` | `expression_language()`, Derja phrases and reply, CIN pending question |
| `agents/intent_router.py` | Courtesy reply language and conversation language; form questions before the LLM fallback |
| `agents/schemas.py` | `ChecklistResult.fee_discrepancy`, `RouteDecision.reply_language` (both optional) |
| `agents/checklist_builder.py` | `_attach_fee_warning()` on both paths |
| `agents/dialogue.py` | CIN ambiguity clarification and `cin_application` strings; "première carte" counts as first issuance |
| `agents/form_helper.py`, `agents/i18n.py` | Localized file-error reasons |
| `tests/test_phase_e.py` (new) | 52 tests: A2, CIN routing and content, RNE routing, context switches, form routing without LLM, localized errors |
| `tests/test_conversational_understanding.py` | A1 expectations (expression language; conversation language kept) and the observed-defect test |

Not changed: Telegram bridge code, n8n workflows, prompts, configuration, data, Qdrant and Ollama models.

## 5. Functional coverage matrix

**How it was tested:**
- **Entry point:** Telegram (bridge code; Telegram API mocked) → n8n workflow 03 (canonical file) → backend agents
  (`/agents/*`), unless noted.
- **Environment:** an isolated stack. Qdrant was restored from the Phase C snapshots, the backend had admin and
  agent keys empty, n8n was throwaway, and the network was dedicated. Host Ollama was used for inference only.
- **Facts asserted:** only those present in the official corpus. Allowed amounts were extracted from it: passport
  20/25/60/80/150, CIN 25.
- **Evidence:** "Result" refers to the final-image run (evidence in section 9). B is the baseline (current
  production backend) and C is the candidate.

| # | Capability | Entry point / agent | Scope and preconditions | Test inputs (examples) | Expected | Actual | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | Passport procedures | WF03 → router (dialogue) → retriever → `checklist_builder` | FR and AR official guides (8+ scenarios); residence and case clarified first | renewal FR + "En Tunisie"; AR duplicate; place / fees / delay; Derja ambiguous "نبدّل" → "تجديد" | Sourced checklist; place without the fee warning; fees with it; Derja clarification | All as expected; amounts ⊆ official; place and delay without warning (B: FAIL, C: PASS) | `interior-passport-guide-fr/ar` | **PASS** |
| 2 | CIN procedures | same | One French guide, 4 scenarios: first issuance, renewal, data change, loss/theft/damage; place, delay and documents sections | first issuance (after a passport, items cleared); place; delay; fees; damaged; "changer" → clarification → "perte"; Derja; English | Official items verbatim; clarification for the ambiguous case; FR source noted for AR/Derja; EN machine translation flagged | All as expected (ambiguity: B FAIL, C PASS). Fees: only the official 25-dinar line, no separate fee section. | `interior-national-id-guide-fr` | **PASS** |
| 3 | RNE registration and formalities | router → `checklist_builder` (official table) / `grounded_answer` | Table of 95 procedures with codes, fees and deadlines; decrees; law 2018-52 | "RNE C 001" fees and deadline; "RNE C 999"; natural-person documents; SARL guidance | Table row with official fee and deadline; code-not-found; sourced answer | As expected; unknown code → "code not found" | `rne-formalities-procedure-table`, decrees | **PASS** |
| 4 | RAG retrieval and grounding | WF02 `/webhook/retrieve` → `/retrieve` | Hybrid retrieval over 272 + 174 official chunks | 5 queries (passport, CIN, RNE fees, AR passport, beneficial owner) | 3 passages, each citing an official manifest document (URL and SHA-256) | 5/5; median 406 ms (B 407 ms) | Qdrant snapshot (isolated) | **PASS** |
| 5 | Legal information and citations | router → `grounded_answer` (legal evidence) | Law 2018-52 (AR), RNE decrees, beneficial-owner decree | beneficial-owner authorities (FR); article 16 (AR); article 999; article 5 with and without the act | Verbatim article with "Source"; no guess for a non-existent article; clarification without an act; contextual act used | All as expected | `rne-law-2018-52-ar`, `rne-decree-beneficial-owners` | **PASS** |
| 6 | Checklist generation | `checklist_builder` (+ `personalize` in dialogue) | Procedure guides and RNE table; declared documents | passport renewal with "4 photos"; CIN scenarios | Official items only; declared items separated; isolated between procedures | As expected (unit and end to end) | corpus | **PASS** |
| 7 | Document / dossier validation | `/dossier_check` → WF03 → `dossier_validator` | RNE F-001 and F-002 templates only | F-001 with 3 of 7 fields carrying a placeholder; unrelated PDF | Filled/missing counts; requirements quoted or "not verifiable"; values never echoed | "Champs remplis: 3, manquants: 4"; unrelated → not evaluated; placeholder absent from replies and logs | official blank forms | **PASS** |
| — | Conflicting extracted information | — | No code compares extracted values with each other or with declarations (code search for conflict/inconsistency logic: none) | — | — | — | code inspection | **NOT IMPLEMENTED** |
| 8 | PDF/image ingestion, OCR, extraction (uploads) | bridge download → WF03 → `form_helper` (text layer or Tesseract ara+fra) | PDF, JPEG, PNG ≤ 10 MB, signature-checked | blank F-001 PDF; F-002 page PNG (OCR); text-free PNG; corrupt PDF; unrelated PDF | Recognised with all fields missing; OCR path works; unreadable or unsupported clearly stated | PDF 0.54 s, OCR 2.05 s; text-free image → "not a supported official form"; corrupt → localized unreadable message (C) | official blank forms | **PASS** |
| 9 | Form-filling assistance (F-001, F-002) | `form_helper` (uploads); `grounded_answer` (printed form content) | Field completeness for the two RNE forms; quotes of printed instructions | partial F-001; "Que dit le formulaire F-001 sur les pièces à joindre ?"; generic "Que contient le formulaire F-001 ?"; F-002 equivalent | "Potentially missing fields: 4"; official extracts; no out-of-scope refusal | Missing-field count correct. F-001 specific question → official extracts. **Generic or other specific questions → "not found in my sources; I prefer not to guess"** (B: out-of-scope refusal) | official forms | **PARTIAL** (field check PASS; printed-content Q&A limited) |
| 10 | Telegram commands, buttons and state | bridge (`ui.py`, `bridge.py`) | /start /help /language /procedures /checklist /form_check /dossier_check /privacy /cancel; inline buttons; 30-min sessions | 12 command and callback turns | Correct localized texts; no backend call for menus; procedure button calls the backend; /cancel clears the session; >2000 characters rejected | All as expected | `telegram_bridge` (image `rc-20261018-lang`) | **PASS** |
| 11 | Automatic language detection (FR, EN, MSA, Arabic-script Derja, Latin Derja) | `agents/language.py` + router | Per-message detection; context for short messages; optional preference | 26-turn language suite; Phase D 22-turn suite; A1 cases | Answer language follows each message; courtesy replies follow A1 | 26/26, 22/22; A1 fixed (B: FAIL) | — | **PASS** |
| 12 | Out-of-scope, unavailable sources, error recovery | router rules / LLM; WF03 error branch; bridge | — | weather; "carte grise"; birth certificate; passport application form (robots-blocked source); backend stopped | Refusal; "not covered"; no fabricated form; localized error message when the backend is down, and normal service after restart | Refusal, "not covered" and error recovery correct (503 ×3 → localized error, then normal service). **The unavailable passport form question gets the passport clarification (case, residence), with no explicit statement that the official form is unavailable.** | manifest: `interior-passport-application-form` blocked by robots | **PARTIAL** (unavailable-source wording) |

### CIN test results (unit: `tests/test_phase_e.py`; end to end: section 6)

| Case | Unit | End to end |
|---|---|---|
| First issuance (FR) | routing + verbatim official items | PASS (after a passport turn; previous declared items cleared) |
| Renewal (FR, Derja, EN) | routing (3 languages) | PASS (Derja: FR source noted; EN: validated machine translation) |
| Lost / stolen / damaged | routing; scenario 3 items verbatim | PASS ("abîmée"; "perte" after clarification) |
| Required documents | all 4 scenarios: items ⊆ official guide, amounts ⊆ {25} | PASS |
| Submission place / delay | items ⊆ the official place/delay sections | PASS |
| Fees | only official amounts | PASS (the guide's fee line; no separate fee section exists) |
| Ambiguous question | "changer ma carte" → clarification; "oui" re-asks; resolved by perte / changement de données / première carte / تجديد | PASS |
| Passport → CIN switch | declared items and passport case dropped | PASS |
| Language switching | FR → Derja, EN → FR | PASS |

### RNE test results

| Case | Unit | End to end |
|---|---|---|
| Registration guidance (SARL) | routing → answer | PASS (sourced answer; amounts ⊆ official) |
| Formality / form F-001 | routing without LLM (with and without RNE context) | PASS (specific question → official extracts) |
| Formality / form F-002 | same | PASS (no refusal; content Q&A limited, see matrix row 9) |
| Document requirements | routing → checklist | PASS |
| Fees and deadlines (RNE C 001) | routing → table | PASS |
| Legal questions with citations | — | PASS (FR and AR, verbatim articles) |
| Unsupported code (RNE C 999) | context keeps the code | PASS ("code not found in the official table") |
| CIN → RNE switch | CIN case dropped | PASS |

### Document, OCR and form test results

| Case | Test document | Result |
|---|---|---|
| Valid PDF | official blank F-001 (text layer) | recognised, all fields missing |
| Valid image | official blank F-002 page as PNG (OCR) | recognised |
| Missing required field | F-001 with "PLACEHOLDER 12" in 3/7 fields | "Champs potentiellement manquants : 4"; dossier report 3 filled / 4 missing |
| Invalid or unreadable file | corrupt PDF; text-free PNG | localized unreadable message; "not a supported official form" |
| Unsupported document | neutral one-page PDF | "not a supported official template", no field conclusion |
| Conflicting extracted information | — | **NOT IMPLEMENTED** (no conflict-detection logic) |
| Sensitive document handling | placeholder values | never echoed in replies; **0** occurrences in backend logs (baseline and candidate); uploads processed in memory, data mount read-only |

All test documents are the public blank official forms or synthetic files with a neutral placeholder; no personal
data was used.

## 6. Regression results (isolated, same stack, same inputs)

| Suite | Baseline: production `rc-20261018-conv` | Candidate `rc-20261018-e` (final) |
|---|---|---|
| Coverage (60 turns) | 52/60 (failures = the 8 defect turns fixed here) | **60/60** |
| Phase D conversational (22) | 21/22 (the reworded Derja thanks) | **22/22** |
| Phase C language (26) | 26/26 | **26/26** |
| Defect probes (16) | 16/16 | **16/16** |
| WF02 retrieval with valid official citations | 5/5 | **5/5** |
| Multilingual evaluation vs the accepted baseline | — | **49/49 records identical** (part A language 28/36, all 22/36, part B 13/13) |
| Error recovery (backend down) | — | **2/2** (FR, Derja) |
| Unit suite | 1264 at Phase D | **1327** |

## 7. Performance and quality (measured unless stated)

These are backend log metrics over the same 94 backend turns per run. The baseline and candidate ran back to back
on the same machine and stack.

| Metric | Baseline | Candidate |
|---|---|---|
| End-to-end turn time: median / p90 / max | 0.18 s / 6.27 s / 54.2 s | 0.17 s / 5.67 s / 48.2 s |
| Rule-based replies (median, end to end) | 60 ms | 50 ms |
| Routing (`agent_route`): median / p90 | 1 / 1 ms | 1 / 1 ms |
| Retrieval (`agent_retrieve`): median / p90 | 92 / 165 ms | 96 / 138 ms |
| Checklist: median / p90 (p90 = EN machine translation) | 36 / 16 156 ms | 37 / 15 881 ms |
| Grounded answer: median / p90 | 8 / 33 068 ms | 8 / 17 ms |
| LLM route-classifier calls | 4 | **1** (form questions no longer use it) |
| LLM-generated answers / verbatim-passage answers | 3 / 12 | 2 / 14 |
| LLM translations (EN) | 6 | 6 |
| Unsupported intents | refusal or "not covered" by rules; LLM fallback only for unmatched text | unchanged; form questions now rule-based |
| Grounding: amounts in answers ⊆ official corpus | all checked turns | all checked turns |
| Language consistency | A1 failure | 26/26 + 22/22 + A1 |
| Procedure-state isolation | passport → CIN → RNE cleared | same + CIN case |

**Measured versus estimated:**
- All latencies are single runs and vary with host GPU load, because LLM-backed turns run on the shared host
  Ollama.
- The largest turns (17–48 s) are LLM-grounded answers and EN translations, unchanged by this phase.
- Small-talk and clarification turns cost about 0.1 ms of routing (Phase D measurement, unchanged).

## 8. Known limitations

1. **Printed-content questions about RNE forms:** only questions that match a printed instruction block are
   answered with extracts. Others get the honest "not found in my sources" reply, which is better than the previous
   out-of-scope refusal but not a full answer.
2. **Unavailable official source** (passport application form, blocked by robots.txt at ingestion): a question
   asking where to download it gets the passport clarification. The assistant does not state that the form itself
   is not in its sources.
3. **Conflicting extracted information** across fields or documents is not detected (not implemented).
4. **French-only official sources** (CIN guide, RNE texts) are quoted in French for Arabic and Derja users, by
   design.
5. **Bridge display language after a courtesy message:** the deployed bridge uses the response's `language` for its
   navigation buttons. After "يعطيك الصحة" in a French conversation, the reply text is Derja and the buttons stay in
   the conversation language (French). Only a bridge change could do otherwise; none was made.
6. **The CIN guide has no separate fee section:** fee questions quote the guide's own fee line.
7. **Unchanged from earlier phases:**
   - the regression fixture of the Phase C session is reconstructed;
   - the admin key still needs rotation before any activation;
   - the RNE upstream change has not been reviewed;
   - key backups are DPAPI-only;
   - Qdrant has no API key.

## 9. Evidence

`C:\Users\Eya Laourine\tna-backups\phaseE-validation-20261018\` (53 files, `SHA256SUMS`):
- `pass_baseline/`, `pass_candidate/` and `pass_final/`: per-turn results with full reply texts (coverage,
  conversational, language), probes, WF02 summary, backend logs, multilingual evaluation (final) and error recovery
  (final);
- the case definitions and generators;
- the test documents (`docs/`).

The isolated containers and network were removed.

## 10. Exact production impact of deploying

- **Changed:** the backend container only (image `rc-20261018-e`). Behaviour changes for users:
  - A1 (gratitude reply language);
  - A2 (fee warning only where relevant);
  - CIN "change" clarification;
  - form-content questions no longer refused;
  - localized file errors.
- **Not changed:** the Telegram bridge (`rc-20261018-lang` stays), n8n workflows, prompts, configuration, data,
  Qdrant and Ollama.
- **API:** two optional response fields (`fee_discrepancy` on checklist results, `reply_language` on route
  decisions). Clients that ignore unknown fields, including the deployed bridge and workflow 03, are unaffected.

## 11. Proposed deployment and rollback (not executed; requires approval)

**Deployment** (same pattern as Phase D; backend only; no POST to admin endpoints):
1. Preflight:
   - production images and health;
   - Qdrant 272/174;
   - data and prompts unchanged;
   - rollback image `rc-20261018-conv` present;
   - candidate provenance (64/64 at `d994df7`).
2. Minimal backup of `data/`, `config/` and `prompts/`, with checksums.
3. Run
   `docker tag tunisian-admin-assistant-backend:rc-20261018-e tunisian-admin-assistant-backend:latest && docker compose -p tunisian-admin-assistant up -d --no-deps --no-build --pull never backend`.
4. Verify:
   - `/health`, the image ID and the static admin-guard check;
   - the bridge unchanged, with one poller and no 409;
   - workflows 01/02/03 states, and Qdrant point-for-point;
   - the bounded smoke test and a production subset of the coverage suite with Telegram mocked.
5. Manual Telegram acceptance:
   - "يعطيك الصحة" in a French conversation;
   - "je veux savoir le lieu de depot" after a passport answer;
   - "Je veux changer ma carte d'identité";
   - "Que dit le formulaire F-001 sur les pièces à joindre ?".

**Rollback:**
`docker tag tunisian-admin-assistant-backend:rc-20261018-conv tunisian-admin-assistant-backend:latest`, then the
same `up` command. This returns to the accepted Phase D backend `d9d9f8ca7962`; no data or prompt rollback is
needed. Never use `8adaf99`.
