# Phase F: real Telegram acceptance regression

Date: 2026-10-18. Branch: `fix/phase-f` (from `fix/phase-e`). Release commit: `ccd1cdc`.
Production was not modified: no deployment or restart, and no change to Qdrant, workflows, prompts or data. Nothing
was pushed or merged.

**Verdict: PHASE F — READY FOR DEPLOYMENT APPROVAL**

## 1. Evidence used (observed versus inferred)

- **Fixture:** `tests/fixtures/phase_e_telegram_session.json` records each turn with separate fields:
  - `observed_input`: the exact message you quoted;
  - `observed_output`: the bot's behaviour as you described it (full reply texts are not stored anywhere);
  - `logged`: the **exact** production routing metadata of the session (15:30–16:04 UTC; the backend logs metadata
    only, never text);
  - `mapping`: the link between a quoted message and a log line, **inferred** from order, category, intent and
    language;
  - `expected`: the inferred requirement.
- **Replay:** the same turns are replayed in unit tests (`tests/test_phase_f.py`) and end to end (section 5).

| # | Observed input | Observed output | Logged (production) |
|---|---|---|---|
| D1 | "قداش تاخو وقت؟" (after a CIN first-issuance checklist) | fees section | 15:34:34 derja · national_id · **fees** · checklist |
| D2 | "Je veux immatriculer une entreprise en Tunisie" | association procedures | 15:35:01 business · procedure_info · answer · **llm_grounded, 97 s** |
| D3a | "Que contient le formulaire F-001 ?" | no relevant information | 15:37:52 business · answer · method **none** |
| D3b | "Et le formulaire F-002 ?" | generic clarification | 15:38:10 business · **form_help** · reply |
| D4 | "Quels sont les frais ?" | generic 50 TND fee | 15:40:45 business · fees · answer · **llm_grounded** |
| D5 | "Où télécharger le formulaire de passeport ?" | renewal question, then submission place | 15:43:40 passport · **submission_place** · reply |
| D6 | `01.pdf`, `02.pdf` | not recognised | 16:03:29 and 16:03:41: PDF, text layer, 287 / 423 words, recognised = false |

## 2. Root causes and fixes

| # | Root cause (code) | Fix |
|---|---|---|
| D1 | `INTENT_KEYWORDS["processing_time"]` (`agents/intent_router.py`) only knew the masculine "قداش ياخو". The feminine "قداش تاخو وقت" then matched the bare "قداش" ("how much") of **fees**. | Duration phrasings added as regexes (ي/ت + اخو/اخذ + وقت; "قداش (من) وقت"; Arabizi "ta5ou/takhou … wa9t", "wa9t"; MSA "يستغرق", "كم من الوقت"; "how many weeks", "combien de jours/semaines"). The deadline check runs before fees, so "قداش نخلص" stays fees. The CIN section selection was already correct (delay). |
| D2 | A business-registration question without a legal form went to the LLM answer over whatever was retrieved, or to `_retrieved_rows` (first rows in retrieval order). In the session, that meant association rows. | New `agents/rne_registration.py`. A legal form (natural person: trader / artisan / liberal profession; SARL/SUARL/partnerships; SA; GIE; foreign branch; association; foreign association; association network; cooperative) maps to **its official creation rows** in the RNE table (`Type d entreprise` column). Without a legal form, a registration, fee or deadline question gets a clarification listing the forms, in 4 languages. "Registering a company/association" is now recognised as RNE. Lowercase "sa" (French possessive) is not "SA". |
| D3 | (a) `form_reply` answered only when a concept word matched a printed block, so a generic "what does it contain" had no match. (b) In an RNE dialogue, "Et le formulaire F-002 ?" fell into the legal-act clarification (`route_dialogue`) before the form check. | (a) `form_overview()`: a verbatim printed overview of the official form (title, the labels of the fields to fill in, printed instructions and options). A specific question without indexed evidence states the limitation, then gives the overview. (b) `route_dialogue` hands form questions to the form path first. A bare "F-001/F-002" and an "et/and" follow-up are recognised. PDF and OCR recognition is unchanged (tests). |
| D4 | Fees went to the LLM answer, which cited one generic table fee | Fees are answered only from the official row of an identified legal form; otherwise the legal form is asked. A single-row form is remembered in the existing `rne_code` context field, so "Quels sont les frais ?" after "SARL" quotes row C 012. Only the matching declaration form is listed (F-001 natural person / F-002 legal entity). |
| D5 | No download intent existed: "formulaire … passeport" became a passport `submission_place` question, which triggered the renewal clarification. | `FORM_DOWNLOAD` is routed to the answer agent. `download_reply()` gives a link **only** from a verified manifest record that has a stored file (RNE F-001/F-002). The passport application form (`interior-passport-application-form`, robots-blocked at ingestion, no file) is declared **unavailable**, without guessing a URL. CIN: no downloadable form in the sources. |
| D6 | See section 3 | The reply names the supported forms (RNE F-001, F-002). An unrecognised upload logs `form_unrecognised` with only the closest template, its score and the threshold, for future diagnosis. |

**Additional regression found and fixed while working:**
- **Article question after a procedure code.** "Que dit l'article 5 ?" after "SARL" was answered with table row C 012. An article number without a known act now still asks which text is meant.
- **"oui" with a pending legal-form question.** It now re-asks the legal-form question.

## 3. D6 investigation: unrecognised PDFs

- **Verified:**
  - Both uploads had a text layer (287 and 423 words) and were not recognised. No error, OCR fallback or format
    issue was logged.
  - The recognition supports exactly two templates, RNE F-001 and F-002. Both official blank forms are recognised
    (tests; isolated PDF and OCR runs).
- **Inferred, not verified:**
  - The names `01.pdf` / `02.pdf` match the Ministry of the Interior form URLs. `02.pdf` is the passport
    application form in the manifest (`…/uploads/imprimes/02.pdf`).
  - If so, they are **unsupported forms**, and rejecting them is correct behaviour, not an OCR or format failure.
  - This was not checked: the files are not available, and `robots.txt` disallows fetching that path, a rule the
    project does not bypass.
- **Diagnosis from now on:** any rejected upload logs the closest template and its match score (metadata only). To
  confirm the cause for these two files, provide them locally.

## 4. Changed files (commit `ccd1cdc`)

| File | Change |
|---|---|
| `agents/rne_registration.py` (new) | Legal forms → official creation codes; registration detection; the clarification question in 4 languages |
| `agents/intent_router.py` | Deadline regexes; download route; registration/company → RNE category (raw text kept for "SA"); legal-form handling on the no-context path |
| `agents/dialogue.py` | Form questions bypass the dialogue path; legal form → rows; clarification; article question still asks for the act |
| `agents/legal_evidence.py` | `FORM_DOWNLOAD`, bare F-00x reference, `form_overview()`, `download_reply()` |
| `agents/answer.py` | `download_reply` before the legal reply |
| `agents/checklist_builder.py` | Several official codes quoted together; only the matching declaration form listed |
| `agents/conversation.py` | Pending legal-form question re-asked on "oui" |
| `agents/form_helper.py` | `form_unrecognised` metadata log |
| `agents/i18n.py` | Overview, limitation, download and supported-forms strings (en/fr/ar/derja) |
| `tests/test_phase_f.py`, `tests/fixtures/phase_e_telegram_session.json` | 50 tests and the session fixture |
| `tests/test_phase_e.py` | One expectation: "Comment immatriculer une SARL au RNE ?" now quotes the official row (checklist) |

**Not changed:** bridge code (identical to the deployed `rc-20261018-lang`), workflows, prompts, configuration,
data, Qdrant, Ollama.

## 5. Test evidence

| Suite | Baseline: production `rc-20261018-e` | Candidate `rc-20261018-f` |
|---|---|---|
| Unit suite | 1327 at Phase E | **1377 passed** (50 new) |
| Phase F session replay end to end (21 turns: D1–D6 and variants) | **5/21**, reproducing the observed defects | **21/21** |
| Phase E coverage (60 turns) | 58/60 (the 2 differences are the intentionally changed SARL and generic F-001 answers) | **60/60** |
| Phase D conversational (22) | 22/22 | **22/22** |
| Phase C language (26) | 26/26 | **26/26** |
| Defect probes (16) | 16/16 | **16/16** |
| WF02 retrieval with valid official citations | 5/5 | **5/5** |
| Multilingual evaluation vs the accepted baseline | — | **49/49 records identical** |
| Error recovery (backend down; FR and Derja) | — | **2/2** |

**Isolation:** a dedicated Docker network, Qdrant restored from the Phase C snapshots, the canonical workflows in a
throwaway n8n, the production bridge image (`rc-20261018-lang`) running the harness with the Telegram API mocked,
admin and agent keys empty, and host Ollama for inference only.

The candidate's first Phase F run scored 20/21 because of an error in **my** test case (it asserted the word
"association" was absent, but the clarification lists it). The case now checks that no association row is shown;
21/21 after the fix.

**Validated areas:**
- **CIN:** first issuance; deadlines in FR/EN/AR/Derja/Arabizi; fees.
- **Passport:** checklist; download.
- **RNE:** legal-form clarification; SARL, SUARL, SA, natural person, association, foreign association, cooperative;
  fees per form; codes.
- **Forms:** content, follow-ups, limitation, download.
- **Documents:** PDF, OCR image, missing fields, unreadable, corrupt, unsupported.
- **State:** CIN → RNE switch; passport context kept for download.

**Content checks:**
- Table rows and form labels are compared **verbatim** with the official corpus.
- Amounts must belong to the official table.
- The fee-conflict warning tests from Phase E pass unchanged.

**Evidence:** `%USERPROFILE%\tna-backups\phaseF-validation-20261018\` (48 files, `SHA256SUMS`).

## 6. Performance (measured, same 115 backend turns, isolated)

| Metric | Baseline | Candidate |
|---|---|---|
| End-to-end median / p90 / max | 0.19 s / 17.98 s / 102.7 s | 0.21 s / **2.73 s** / 36.7 s |
| Total time for the run | 623 s | **213 s** |
| Routing median / p90 | 1 / 1 ms | 1 / 2 ms |
| Retrieval median / p90 | 99 / 5 509 ms | 113 / 172 ms |
| LLM route-classifier calls | 3 | 1 |
| LLM-generated answers / verbatim answers | 9 / 14 | **1 / 20** |
| LLM translations (EN) | 7 | 7 |
| Placeholder values in logs | 0 | 0 |

Registration, fee and form questions are now answered from official rows and printed form text, not generated.
These are single runs on a shared host GPU, so treat the timings as indicative.

## 7. Known limitations

1. **Families of rows:** "personne physique" (C 001–003) and Tunisian associations (C 010.1 / C 010.2) are quoted as
   all their official rows. They are not remembered for later "frais ?" questions, because the deployed bridge
   keeps only known context fields; the legal form is asked again.
2. **Legal forms outside the list:** other forms in the table (e.g. syndicates, political parties, mutual societies)
   are not in the deterministic list. They lead to the clarification or the existing retrieval path.
3. **Form overview:** this quotes the printed one-page forms as extracted. Mixed Arabic/French layout artefacts in
   the extraction (e.g. a split "المصرّ ح") are quoted as they are.
4. **D6 cause:** not verifiable without the files.
5. **Fixture:** the session fixture's message-to-log mapping is inferred, and reply texts are as you described them.
6. **Unchanged from earlier phases:** French-only sources are quoted in French; there is no conflict detection
   across extracted values; the admin key still needs rotation; the RNE upstream change has not been reviewed; key
   backups are DPAPI-only; Qdrant has no API key.

**Observation:** an untracked folder `deliverables/` (a presentation `.docx`/`.pdf`, created 17:45–17:52 local time,
open in Word) appeared in the production checkout during this phase. It is not created or used by the assistant,
and it was left untouched.

## 8. Safe deployment proposal (not executed; requires approval)

**Backend only:** `tunisian-admin-assistant-backend:rc-20261018-f`
`sha256:221baebdc47426be112187f9837889859c88788a0d337a70412684ecf561f227`. All 65 copied files are hash-identical to
`ccd1cdc`. The bridge stays `rc-20261018-lang`, and no prompt, workflow or data change is needed.

1. Preflight, as in Phase E:
   - images, health, one poller, workflow states;
   - Qdrant 272/174;
   - data and prompts unchanged;
   - rollback image `rc-20261018-e` present;
   - candidate provenance.
2. Minimal backup of `data/`, `config/` and `prompts/` with checksums.
3. Run
   `docker tag tunisian-admin-assistant-backend:rc-20261018-f tunisian-admin-assistant-backend:latest && docker compose -p tunisian-admin-assistant up -d --no-deps --no-build --pull never backend`.
4. Verify:
   - `/health`, the image ID and the static admin-guard check;
   - the bridge unchanged, with no 409;
   - workflows unchanged and Qdrant point-for-point;
   - the smoke test and the Phase F session replay against production with Telegram mocked.
5. Manual Telegram acceptance with the six session inputs:
   - "قداش تاخو وقت؟" after a CIN question;
   - "Je veux immatriculer une entreprise en Tunisie" → "SARL" → "Quels sont les frais ?";
   - "Que contient le formulaire F-001 ?" → "Et le formulaire F-002 ?";
   - "Où télécharger le formulaire de passeport ?";
   - an RNE F-001 upload and an unsupported PDF.

**Rollback:**
`docker tag tunisian-admin-assistant-backend:rc-20261018-e tunisian-admin-assistant-backend:latest`, then the same
`up` command. This returns to the current protected Phase E backend `69d7a7faab1b`. Never use `8adaf99`.
