# Phase 3 evaluation

All results below were produced on 2026-10-16 by the scripts named in each section. The raw outputs are in
`data/evaluation/`. Host-side calls used `127.0.0.1` (see the latency note in `docs/TEST_RESULTS.md`).

## 1. Evaluation set (`data/evaluation/eval_set.jsonl`)

Built by `scripts/build_eval_set.py`. It has 84 questions:

| Split | Count |
|---|---|
| Language | 34 FR, 26 EN, 11 AR, 13 Derja (9 of them in Latin script) |
| Procedure | 25 passport, 4 national ID, 45 RNE, 4 birth certificate, 5 out of scope, 1 unspecified |
| Answerability | 67 answerable, 2 conflicting, 9 unsupported (including 2 procedures outside the corpus), 3 ambiguous, 3 out of scope |
| Verification | 69 verified evidence, 2 document-level only (ambiguous), 13 with no answer in the corpus |

- **Ground truth is never written by hand.** Each answerable item lists *evidence spans* that must occur
  verbatim in a named official document. The build script checks every span against the extracted text and
  stores the page, the full official block (`reference_extract`) and the source URL. Items whose span is not
  found are marked `UNVERIFIED` and excluded; there are none.
- **Evidence groups.** Equivalent French and Arabic passages form one *group*. Conflicting items (the FR/AR
  passport stamp duties) have one group per version.
- **Parallel subset.** 7 verified facts plus one unsupported request, each asked in 4–5 language/script
  variants (`parallel_group`).
- **Unsupported items** record why no answer exists:
  - birth certificates: the source opts out of AI use;
  - no official RNE checklist of required documents;
  - code RNE C 014 does not exist;
  - procedures outside the corpus.
- **Human review status:** `pending` for all items.

## 2. Retrieval (`scripts/evaluate_retrieval.py`)

**Relevance.** A chunk is relevant when it is from the group's document and contains the span, after NFKC
normalisation with whitespace and diacritics removed.

**Metrics** (computed over the 71 items with labels):
- Recall@k: the share of evidence groups found in the top k.
- Hit@5: at least one group is found in the top 5.
- MRR@5: reciprocal rank of the first relevant chunk.

Every configuration uses the same questions, the same cached routes (`routes.json`, production router
including its LLM fallback) and k = 5.

| Configuration | Chunks | R@1 | R@3 | R@5 | MRR@5 | Hit@5 | ms |
|---|---|---|---|---|---|---|---|
| Dense, raw query (Phase 1) | structure | 0.465 | 0.676 | 0.718 | 0.575 | 0.732 | 368 |
| Dense, raw query (Phase 1) | recursive | 0.528 | 0.725 | 0.803 | 0.642 | 0.817 | 360 |
| Agent retriever (Phase 2, before) | structure | 0.493 | 0.648 | 0.697 | 0.577 | 0.704 | n/a* |
| Agent + term normalisation | structure | 0.507 | 0.662 | 0.711 | 0.591 | 0.718 | 364 |
| Agent + term normalisation | recursive | 0.415 | 0.556 | 0.648 | 0.504 | 0.662 | 366 |
| Hybrid RRF (raw + expanded + BM25) | structure | 0.549 | 0.768 | 0.831 | 0.668 | 0.845 | 393 |
| **Hybrid RRF + max 2 chunks/doc** | structure | **0.549** | **0.782** | **0.859** | **0.675** | **0.873** | 386 |
| Hybrid RRF + max 2 chunks/doc | recursive | 0.507 | 0.711 | 0.768 | 0.613 | 0.775 | 396 |
| Hybrid RRF + max 3 chunks/doc | structure | 0.549 | 0.768 | 0.852 | 0.669 | 0.859 | 388 |

\* Measured with cached embeddings through `localhost`, so latency is not comparable
(`retrieval_results_final.json`). The final configurations are in `retrieval_results_improved.json`.

### Baseline findings (before any change)
1. **The Phase 2 production retriever was worse than raw dense retrieval** (Hit@5 0.704 vs 0.732). Its fixed
   expansion ("Registre National des Entreprises immatriculation …") pulled in the 95 near-identical rows of
   the RNE table and crowded out the legal texts (law 2018-52, decree-law 2022-18, name-reservation and
   beneficial-owner decrees). The same expansion was what rescued Latin-script Derja.
2. **Exact procedure codes** ("RNE M 004.03", "RNE C 025") were missed by every dense configuration.
3. **SARL vs SUARL is not a real ambiguity in this corpus:** both are in the single official row RNE C 012.
4. **English company types** ("public limited company") had no route to the official French term
   "Société anonyme".

### Improvements, each kept only after a measured gain on the same set

| Change | Effect (Hit@5, structure) | Kept |
|---|---|---|
| RRF of dense(raw) + dense(expanded) + BM25(raw), same category filter (`rag/hybrid.py`) | 0.718 → 0.845 | yes |
| At most 2 chunks per document in the top 5 | 0.845 → 0.873 (a cap of 3 gives 0.859) | yes (2) |
| Company-type normalisation (EN/AR/Derja → official FR term), also fed to BM25 | agent 0.704 → 0.718; fixed R03 in the hybrid | yes |
| Arabizi word map (Latin-script Derja → Arabic script), queries only | Latin Derja on the parallel subset: 0.0 (dense) → 0.714 (hybrid) | yes, see caveat |
| Batched embedding of raw + expanded queries | hybrid latency within 22 ms of plain dense | yes |
| Multi-query without BM25; BM25 with expansion only | both below the full hybrid (`retrieval_results_variants.json`) | no |

**Caveat.** The term map and the Arabizi map were compiled after looking at failures on this set, and no
held-out split exists. The reported gains on those items are therefore optimistic.

### Chunking comparison

| Strategy | Chunks | Mean chars | Median chars | Hit@5 (dense) | Hit@5 (hybrid + cap) |
|---|---|---|---|---|---|
| structure | 272 | 526 | 430 | 0.732 | **0.873** |
| recursive | 174 | 867 | 911 | **0.817** | 0.775 |

- **With raw dense retrieval, recursive chunks win.** The structure strategy makes each RNE table row a short
  chunk; the 95 rows are near-identical for an embedding model, and recursive chunks carry more context.
- **With BM25 and the cap, structure chunks win.** One row is one chunk, so an exact code or company type
  selects exactly that row. Recursive chunks merge several rows, and the cap then discards useful rows.
- **The better strategy depends on the retriever.** It should be chosen together with it.

### Multilingual retrieval (official documents are never translated; only queries are expanded)

Parallel subset, Hit@5 (identical information needs):

| Query | Dense (raw) | Agent | Hybrid + cap |
|---|---|---|---|
| French | 1.000 | 0.714 | 1.000 |
| English | 1.000 | 0.714 | 1.000 |
| Arabic | 0.714 | 0.857 | 1.000 |
| Derja, Arabic script | 0.750 | 1.000 | 1.000 |
| Derja, Latin script | 0.000 | 0.714 | 0.714 |

- **Cross-lingual retrieval already works for FR, EN and AR.** BGE-M3 maps English and French questions onto
  Arabic-only passages (e.g. law 2018-52 article 51), and Arabic questions onto French ones.
- **Latin-script Derja is the weakest case.** Words such as *passbor*, *charika* or *khtiya* match neither
  script. The remaining misses (M10 beneficial owner, M12 late penalty) use vocabulary outside the map.

### Remaining retrieval failures (hybrid + cap)
P12, R09, R14, R16, R17, R23, R32, M10, M12:
- **Fee-decree questions (R14, R16, R17).** Answers about refunds, payment methods or extract fees still lose
  to RNE table rows.
- **R23.** A French question whose answer exists only in the Arabic law (appeal deadline).
- **R32.** "Which form": the forms' text is mostly field labels.
- **P12 and R09.** Displaced by the cap.

## 3. Answer quality (`scripts/evaluate_agents.py`)

The full production chain (route → retrieve → checklist or answer) runs in-process with real Qdrant and
Ollama. All checks are deterministic; no LLM is used as a judge.

| Check | First run (`agent_results_hybrid.json`) | Final (`agent_results_final.json`) |
|---|---|---|
| Category routing | 0.952 (n=83) | 0.952 |
| Intent routing | 0.819 | 0.819 |
| Language detection | 0.988 (n=84) | 0.988 |
| Citation validity (URL + SHA-256 match manifest) | 172/172 | 147/147 |
| Citation support (expected document cited) | 0.826 (n=69) | 0.855 |
| Verified evidence span present in response | 0.594 | 0.580 |
| Faithfulness (verbatim items; numbers in LLM answers present in passages) | 1.000 | 1.000 |
| Unsupported / out-of-scope rejection | 0.833 (n=12) | 0.917 |
| FR/AR conflict flagged | 2/2 | 2/2 |
| Response language consistency | 0.750 | 0.798 |

Median latency in the final run: checklist 426 ms (n=49), grounded answer 27.0 s (n=22), router-only
replies 2.3 s (n=13, the LLM fallback dominates).

### Fixes between the two runs
All were found by error analysis on this set, so the after-fix numbers are optimistic.
- **Unknown procedure codes.** Questions naming a code absent from the official table (RNE C 014) are
  reported as non-existent instead of being answered with other rows.
- **RNE questions without a registration act.** Fee or duration questions about the fee decree, name
  reservation or beneficial owners go to the Grounded Answer agent instead of the table.
- **RNE table rows.** They now follow retrieval order, and the top non-table passages are quoted verbatim.
- **Generic passport questions.** They no longer select the "change of passport" or "pilgrimage" scenarios.

### Reading the metrics
- **"Evidence span present" is a strict lower bound.** R25 is answered correctly in French ("valable pour une
  durée de six mois, renouvelable une fois") from an Arabic-only decree. English checklists are validated
  translations. Neither can contain the official span verbatim.
- **Language consistency fails mostly by design.** English and Derja users receive the verbatim French
  original when no validated translation or Arabic version exists.

### Remaining failures (final run)
- **Routing (R20, R28, O04, M08).** All four category errors come from the LLM fallback. R28 uses the
  indefinite Arabic form "مستفيدا حقيقيا", which the keyword rules do not cover.
- **O04 (driving licence) is not refused.** The LLM answer is rejected, but the fallback then quotes unrelated
  passport passages. The fallback should check relevance before quoting.
- **"Which form" questions (R32, R33)** get the greeting instead of the official form links.
- **Fee-decree questions (R14–R17)** still depend on weak retrieval (section 2).

## 4. Prompt iterations (grounded_answer, 12 answer-routed questions, same passages within a run)

| Run | Prompt | Accepted | Numbers in sources | Evidence span | Language OK | Median s |
|---|---|---|---|---|---|---|
| A | v1 | 0.667 | 1.000 | 0.273 | 0.917 | 29.2 |
| A | v2 | 0.750 | 1.000 | 0.091 | 1.000 | 26.5 |
| B | v2 | 0.750 | 1.000 | 0.091 | 1.000 | 24.7 |
| B | v3 | 0.750 | 1.000 | 0.182 | 1.000 | 31.7 |

- **v1 → v2.** Observed during Phase 2: an Arabic answer was cut off. v2 raised the token limit and asked for
  faithful list reproduction. The measured effect: acceptance and language consistency improved, but the model
  paraphrased more.
- **v2 → v3.** v3 asks for a verbatim quotation before each explanation. Evidence rose from 1/11 to 2/11,
  acceptance was unchanged, and the median time grew by 7 s. **Not adopted**: the difference is a single item
  and v3 is slower. v2 stays active (`prompts/registry.yaml`).
- **`translate_items@v1` FR→AR was withdrawn** in Phase 2 (meaning errors that passed validation).
  Translation is applied FR→EN only.
- **Evaluator limitation.** One version-file bug was found by the evaluator: the YAML changelog of v3 was
  invalid. `test_every_prompt_version_parses` now guards all versions.

## 5. Deployment status

- **Code changes not yet deployed.** The Phase 3 changes are in the code (hybrid retrieval is now the default:
  `RETRIEVAL_MODE=hybrid`), but the running backend container still serves the Phase 2 code. It was not
  rebuilt during this phase, to avoid disrupting parallel work on the Telegram bridge. To deploy:
  `docker compose up -d --build backend`. To fall back to the previous retriever: `RETRIEVAL_MODE=agent`.
- **Measurement method.** All Phase 3 measurements ran in-process with the current code against the live
  Qdrant and Ollama services.

## 6. Final reliability changes and held-out validation (2026-10-16)

### Held-out set (`data/evaluation/heldout_set.jsonl`, `split: heldout`)
- **Content.** 20 questions written after all retrieval and routing tuning: 16 with verified evidence and
  4 unsupported. They are on official facts not used in the development set; languages are 8 EN, 7 FR,
  3 AR and 2 Derja.
- **Procedure.** The set was built and evaluated **before** any change of this phase, then evaluated once
  more after. No component was chosen or tuned on it.
- **Evidence.** Verified verbatim against the extracted official text, like the development set.

### Changes, each diagnosed on the development set
1. **Answerability gate (`agents/answerability.py`).** If the procedure was not identified by the keyword
   rules (LLM fallback or "general"), at least half of the question's IDF-weighted informative terms must
   occur in the top-5 passages. Words absent from the corpus get the maximum IDF. Otherwise both answering
   agents refuse (`insufficient_evidence`) instead of answering or quoting unrelated passages. Keyword-routed
   questions are not affected, so valid answers and citations are preserved. On the development set it
   refuses O04 (support 0.00) and keeps P15 (0.66) and R20 (0.69).
2. **Translation-validation bug.** The official ID guide writes "3⁄4 cm" with U+2044 (fraction slash), so
   every FR→EN translation of that item failed the number check and fell back to French.
3. **RNE answers.** The header and the table field labels are localised for EN/AR/Derja and placed
   **before** the verbatim official line ("Procedure code — Code procédure: RNE C 012"). A first version
   replaced the French labels; that altered the official quotation and cut verbatim evidence from 0.580 to
   0.449, so it was reverted to the prefix form.
4. **Scenario lists.** The "other cases" line has a localised label.
5. **Derja detection.** Common Latin-script Derja verbs (nekhou, ya5ou, …) were added; B04 is now detected
   as Derja.

### Results

| Metric | Dev before | Dev after | Held-out before | Held-out after |
|---|---|---|---|---|
| Hit@5 dense raw query | 0.732 | – | 0.750 | – |
| Hit@5 Phase-2 agent retriever | 0.718 | – | 0.562 | – |
| Hit@5 hybrid + cap (production) | 0.873 | – | 0.750 | – |
| MRR@5 hybrid + cap | 0.675 | – | 0.531 | – |
| Citation validity | 147/147 | 145/145 | 31/31 | 31/31 |
| Unsupported-answer rejection | 0.917 | **1.000** | 0.750 | 0.750 |
| Faithfulness | 1.000 | 1.000 | 0.938 | 0.938 |
| Language detection | 0.988 | 1.000 | 0.950 | 1.000 |
| Language consistency, strict (whole text) | 0.798 | 0.821 | 0.700 | **0.800** |
| Language consistency, assistant text (official quotations excluded) | 0.909 | 0.929 | 0.944 | **1.000** |
| Verified evidence span present | 0.580 | 0.565 | 0.375 | 0.312 |

- **Assistant-text language consistency** (`scripts/evaluate_agents.py`, `scripts/rescore_language.py`)
  removes every response segment that occurs verbatim in an official document before checking the language.
  The "before" values were computed on the recorded responses. Both metrics are reported, because official
  quotations are deliberately kept in their original language.
- **Evidence-span decreases** come from translations that now pass validation (N02, H05): a validated
  English translation cannot contain the French span verbatim.
- **Retrieval was not changed in this phase.** On held-out data the production hybrid ties raw dense
  retrieval on Hit@5 and ranks lower (MRR@5 0.531 vs 0.635). Part of the development gain was overfitting.

### Held-out failures (not tuned on)
- **H17 "Comment renouveler une carte grise ?" is answered.** The generic words *renouveler* and *carte* occur
  in the national-ID evidence (lexical support 0.58 ≥ 0.5), and the LLM then conflates vehicle registration
  with the ID card. A fix needs semantic verification of the answer against the evidence. Simple lexical
  variants either still pass H17 or refuse valid development questions (R20, whose verb "prévoit" is absent
  from the corpus).
- **H14.** An accepted LLM answer contains a number absent from its passages.
- **Retrieval misses (H02, H05, H08, H15).**

## 7. Evidence verifier (2026-10-16)

### Root causes of the held-out failures
- **H14 (unsupported number).** The question was keyword-routed and answered by Mistral 7B from Law 2018-52
  art. 55, which states the fine in Arabic words ("خمسون ألف دينار", fifty thousand dinars). The model
  wrote "510,000 TND". The answer agent only checked that citation markers existed, not what the cited text
  says.
- **H17 (topic confusion).** "Comment renouveler une carte grise ?" was routed by the LLM fallback ("general").
  The lexical gate passed it (0.58 support from the generic words *renouveler* and *carte*), and the model
  presented the national-ID renewal procedure as the answer. Nothing checked that the evidence described the
  procedure asked about.

### Mechanism (`agents/verification.py`; used by the Grounded Answer and Checklist Builder agents)

**Numerical claims (deterministic).**
- Every number written with digits in an LLM answer must occur in the passages cited by the same sentence,
  or in the question.
- Source numbers are read as digits and as number words (FR/EN/AR), e.g. "خمسون ألف" = 50,000 and
  "سبعة أيام" = 7.
- Citation markers, the sources footer and page numbers are not claims.
- Sentences with unsupported numbers are removed. If no cited sentence remains, the answer is refused
  (`unsupported_claim`). No number is ever replaced.

**Topic consistency.**
- **Keyword-routed procedure:** checked with source metadata (the passages' `procedure_category`).
- **LLM-routed or unknown, French or Arabic question:** a topical content word that occurs in none of the
  official documents (light stemming; verb forms excluded) means the subject is not covered.
- **LLM-routed or unknown, English or Derja question:** the `evidence_topic@v1` LLM verdict (JSON,
  validated; any error means refusal).
- **First version:** used the LLM verdict for all languages and showed the LLM only one passage per
  document.
  - The one-passage selection hid the relevant RNE row in H09 (a bug, fixed).
  - The verdict was unstable: "carte grise" was judged consistent in some runs.

**Settings.** `EVIDENCE_VERIFICATION` and `EVIDENCE_TOPIC_CHECK` (both default `true`).

### Evaluation sets
Development and held-out sets as before, plus:
- **`regression_set.jsonl` (15).** The known failure types, with answerable "twins". Written before the
  verifier existed.
- **`test_set.jsonl` (14).** Untouched. Evaluated first with verifier v1, then once with the final version.
- **`test2_set.jsonl` (12).** Written after v1 and before the final topic rule. Evaluated once with the final
  version; the "off" column is the same code with `EVIDENCE_VERIFICATION=false`.

### Results (off = verifier disabled or pre-verifier code; on = final verifier)

| Set | False acceptance off → on | False refusal off → on | Unsupported numbers off → on | Valid citations off / on |
|---|---|---|---|---|
| Development (84) | 0.000 → 0.000 | 0.058 → 0.058 | 2/85 → 0/78 | 145/145 · 145/145 |
| Regression (15) | 0.143 → **0.000** | 0.000 → 0.125 (RN1 = H14: refused, wrong figure) | 1/9 → 0/1 | 14/14 · 11/11 |
| Held-out (20)\* | 0.250 → 0.000 | 0.000 → 0.125 (H09, H14) | 1/9 → 0/1 | 31/31 · 25/25 |
| Test 1 (14) | 0.250 → 0.250 (T11) | 0.000 → 0.100 (T07 "tarif") | 2/19 → 0/17 | 23/23 · 19/19 |
| Test 2 (12) | 0.167 → 0.167 | 0.833 → 1.000 | 2/7 → 0/8 | 2/2 · 1/1 |

\* H17 and H09 were analysed before the final version, so the held-out set is no longer independent for them.

**Conclusions.**
- **The numerical check is a clear gain.** It removed every unsupported number on every set, in 3 ms
  (median).
- **The topic check is a trade-off.** It removes the known failure type, but on the independent test sets it
  did not reduce false acceptance and added false refusals:
  - false refusals come from synonyms ("tarif" vs "redevance") and word forms ("fixe");
  - subjects named with corpus words still pass ("attestation de travail", "شهادة الإقامة").
- **Test set 2 is dominated by routing.** 5 of its 6 answerable questions are refused by the router's LLM
  fallback with the verifier off.

### Latency (`scripts/benchmark_verifier.py`, `verifier_latency.json`)

| Path | Median | Max | n |
|---|---|---|---|
| Numerical check | 3.0 ms | 5.3 ms | 17 |
| LLM topic verdict (EN/Derja LLM-routed questions only) | 6.6 s | 10.8 s | 6 |

- The deterministic FR/AR topic rule takes a few milliseconds.
- Keyword-routed questions, the large majority, pay no LLM cost.
