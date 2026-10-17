# Independent post-fix audit — pre-production release gate (2026-10-17)

**Type:** verification and release-readiness audit. Nothing was deployed, restarted, rebuilt, reindexed or
modified in either environment. No Telegram message was sent, and no credential was displayed.

**Companion documents:**
- `POST_FIX_REGRESSION_RESULTS.md`: commands, numbers, latency.
- `INTENT_DISCREPANCY_REVIEW.md`: all 36 discrepancies.
- `RELEASE_READINESS_CHECKLIST.md`: gates, smoke tests, rollback.

## 1. Executive summary

Codex's corrections are **genuinely implemented, running in an isolated candidate, and their headline
results reproduce under an independent runner with independent checks**:
- **Contextual RNE:** 190/190 correct versus a production baseline of 0/166 executed.
- **Context-free RNE:** 190/190 correct, versus 188/190 in production.
- **Required official spans:** 480/480.
- **Unit tests:** 821/821.
- **Integration tests:** 40/40 (the 41st is a production-Qdrant-mutating test that was not run, by rule).

The Article 16 hallucination is eliminated. Legal questions on the six covered acts are now answered **only
with verbatim extracted articles**, and a nonexistent article is refused. **No regression** was found in
the 728-case replay, the 82-request routing matrix, or the 214 original cases that Codex did not replay.

Remaining weaknesses are real but **not worse than production**:
- article selection in the long fee decree can quote the wrong provision;
- an article-number follow-up drops the legal subject;
- a penalty question that does not name the law gets a false "not in sources" reply;
- legal answers are long, untranslated excerpts;
- three pre-existing CIN routing gaps remain;
- group chats share context;
- the candidate and production stacks contend severely for the single 4 GB GPU.

**Verdict: CONDITIONAL GO.** Candidate status: **READY WITH LIMITATIONS**. The conditions are in §13.

## 2. Production versus candidate (isolation verified before any test)

| Component | Production | Candidate | Shared? | Risk |
|---|---|---|---|---|
| Backend container / image | `tunisian-admin-assistant-backend-1`, `sha256:8adaf99471c5…` (= `:latest` = `:post-audit-before`), created 11:30 UTC, `/app/data` **rw** | `post-audit-candidate`, `…:post-audit-final` `sha256:7254fcf24012…`, created 14:26 UTC, `/app/data`, `/app/config`, `/app/prompts` **read-only**, restart policy `no` | No | Low |
| Backend port | 127.0.0.1:8000 | 127.0.0.1:8001 | No | Low. Localhost only. The candidate also exposes `/index/run` and `/ingestion/run`, which would write to the **shared** Qdrant if called (not called). |
| n8n | `tunisian-admin-assistant-n8n-1`, workflow `TnaaAssistant01` `versionId 92f81ea7…` (unchanged; matches backup) | `post-audit-n8n` (same image, no volume, workflow imported from `post_audit_backup/candidate_workflow.json`), same ID `TnaaAssistant01`; its 6 HTTP nodes → `post-audit-candidate:8000`; all other parameters and connections identical | No (separate instance) | Low. Same workflow ID on two instances could confuse an operator. |
| n8n port | 127.0.0.1:5678 | 127.0.0.1:5679 | No | Low |
| Qdrant | `official_docs_structure` 272 / `official_docs_recursive` 174 | **Same instance** (`qdrant:6333`, same Docker network) | **Yes** (read path) | Medium. Payloads verified identical to the 11:44 UTC snapshot after all candidate testing. |
| Ollama | host, `bge-m3`, `mistral:latest`, `translategemma:4b` | **Same host Ollama** | **Yes** | **High during the demo:** contention (§10) |
| Telegram bridge | `tunisian-admin-telegram-bridge`, `sha256:7eafea6e…` (= `:post-audit-before`), live token | `…telegram:post-audit-final` `sha256:befa1e0c0a81…`; **image only, not running** | Token is in `.env` only | Low |
| Docker network | `tunisian-admin-assistant_internal` | same network | Yes | Low/Medium: the candidate could reach production services by name |
| Secrets in container env | `TELEGRAM_BOT_TOKEN`, `N8N_ENCRYPTION_KEY` present (via `env_file: .env`) | Same set present | – | Low/Medium; pre-existing, not a regression. The backend does not need them. |

## 3. Exact code and deployment version identification

| File | Repository = candidate container | Production container | Candidate bridge image |
|---|---|---|---|
| `agents/answer.py` `f87abeef…`, `checklist_builder.py` `2f6a48ee…`, `dialogue.py` `06110116…`, `intent_router.py` `0d47db76…`, `legal_evidence.py` `c03c69be…` (absent in production), `retriever.py` `5d2a4e28…`, `schemas.py` `f33e0616…`, `backend/agents_api.py` `e28dc7ba…` | ✅ identical (SHA-256) | differs (pre-fix; equals `post_audit_backup/` copies) | n/a |
| `telegram_bridge/contracts.py` `208d1585…`, `bridge.py` `56188f7b…`, `ui.py` `1753bb39…` | ✅ | `contracts.py` differs (pre-fix) | ✅ identical |
| `rag/*`, prompts, corpus | identical in all three | identical | – |

Codex's 632-case run (`post_audit_candidate_final_results.jsonl`) started at 14:26:32 UTC, after the
final candidate container was created (14:26:22 UTC), and targeted only `localhost:5679`. **Codex's
results were produced against the corrected candidate.**

## 4. Reproduction of the original critical failures (production, today)

| Defect | Production behaviour today | Evidence |
|---|---|---|
| G-01: contextual RNE source-only reply | 166/166 executed contextual cases empty (751-character icon + sources) | `prod_rne.jsonl` |
| RNE I 001 / I 002 substitution | I 001 → C 001 row, I 002 → C 008 row (context-free) | same |
| CIN loss → first application | Reproduced on the earlier probe; production also routes Arabic theft and French damage to the first application (§6 of the regression report) | probes |
| Arabic "من أجل" → processing_time | Reproduced (the conditions question still `processing_time` on production) | probes |
| Art. 16 hallucination | Original audit probe (generated "amendments" definition); production legal path unchanged | earlier audit |

## 5. Independently verified fixes

| Original defect | Original behaviour | Candidate behaviour | Evidence | Count | Status |
|---|---|---|---|---:|---|
| Contextual RNE fee/deadline | Empty body, `found:true`, 0/190 | Exact requested row only; fee and deadline verbatim; official citations | Independent replay | 190/190 | **VERIFIED FIXED** |
| Context-free RNE | 188/190; I 001/I 002 wrong row; extra rows | Exact row only, including dotted codes | Independent replay | 190/190 | **VERIFIED FIXED** |
| Art. 16 legal hallucination | Invented provision + quotation | Verbatim Art. 16 (`قرينة بسيطة`); "cite exactly" also correct; Art. 999 refused | Probes, both shapes | 3 cases × 2 | **VERIFIED FIXED** |
| Name reservation validity vs issuance | Validity rendered as delivery time | All articles verbatim: "same day" issuance **and** 6-month validity | Probes | 2 × 2 | **VERIFIED FIXED** |
| Beneficial-owner article misattribution | Art. 4 cited for an Art. 5 rule | Whole Arrêté 2026-35 quoted verbatim, so nothing is misattributed (verbose) | Probes + replay | – | **VERIFIED FIXED** (verbose) |
| BO access follow-up drift (multi-turn) | Switched to association rows | Subject retained (`legal_subject`) for "Et quelles sont les conditions ?" | Replay (8 contained + 7 expected clarifications of 15) + M7 | – | **VERIFIED FIXED**, except article follow-up M8 |
| CIN loss (natural FR) | First application | Loss/theft/damage scenario, both shapes; FR/EN/AR/Derja-AR/Derja-Latin loss and theft | Matrix | 15+ | **VERIFIED FIXED** (Telegram shape); web shape still fails for Arabic theft and French damage |
| Arabic "من أجل" | `processing_time`, requested section omitted | `required_documents` / `fees` with the correct duplicate scenario; a genuine deadline is still `processing_time` | Matrix + 72 guide scenarios + 18 guide fees | 90 | **VERIFIED FIXED** |
| Guide scenarios | 68/72 spans retained | 72/72 | Replay | 72 | Improved |

## 6. Remaining failures (all independently observed)

| # | Failure | Severity | Present in production? |
|---|---|---|---|
| R1 | **Fee decree 2022-298 article selection.** "Que prévoit le décret … pour les redevances ?" and "Que couvre le tableau 3 ?" return Arts. 5/7/6 or 4/3/6. The fee tables are in Art. 1. Verbatim but **wrong provision** for the question. | Medium/High (fails the "valid URL, wrong provision" rule) | Production answered the same family with LLM or fallback text reviewed incomplete/incorrect |
| R2 | **Article-number follow-up loses the legal subject (M8).** "Que dit l'article 5 ?" after a beneficial-owner question → `out_of_scope`, and the returned context is emptied. | Medium | Production has no legal subject at all |
| R3 | **False refusal: "penalty for a false declaration to the RNE"** (EN, the act not named). Mistral says the passages lack the information and cites unrelated documents. Law 2018-52 **Art. 55** (5 years, 50,000 TND) is in the corpus. | Medium (safe direction, misleading) | Production also refused (numeric verifier) |
| R4 | **CIN routing gaps:** Latin-Derja "njaded" → first application; Arabic theft and French "détériorée" → first application on the **web** shape; "my data changed" (EN, Telegram shape) → first-application list with "I have noted the documents you say you already have". | Medium | Yes, all identical or worse |
| R5 | **Legal answers are long and untranslated:** up to 4,598 characters (whole Arrêté); English and French users receive Arabic or French source text with a notice. | Low/Medium (usability) | Production paraphrased (and hallucinated) instead |
| R6 | **Form-instruction questions → generic `form_help` welcome** (8 cases) | Medium | Yes (unfixed, out of Codex's scope) |
| R7 | **Adversarial "invent / guarantee" requests** get verbatim excerpts and a no-conclusion notice, not an explicit refusal | Low | Production generated text |
| R8 | **Group chats share one session** (keyed by `chat.id`) | Low | Yes |
| R9 | **Unnecessary clarifications** in 3 Telegram-shape cases (application type already stated) | Low | Yes |
| R10 | **Pledge/leasing rows list the F-001/F-002 registration forms** | Low | Yes |
| R11 | **Telegram-shape English answers keep the French official scenario title** | Cosmetic | Yes |

## 7. Regression results (summary; details in `POST_FIX_REGRESSION_RESULTS.md`)

- **Automated suites:** unit 821/821; integration 40/40 (1 not run, by rule).
- **Full replay (all 728 n8n-stage original cases):**
  - 0 errors;
  - required spans 480/480;
  - citations 1614/1614 official URLs;
  - expected document cited in 690/716 assessed cases.
- **Groups Codex did not replay:** passage containment is equal to or better than production, so no
  regression.
- **Uploads:** F-001 (7 missing) and F-002 (8 missing) are recognised in PDF and PNG, in both form-check and
  dossier mode. Dossier `cannot_verify` = 4 and `completeness_certified=false` in all 4 dossier cases.
  Corrupt and unsupported files are handled safely in 6/6 cases.
- **Not tested:** handwriting and real photographs.

## 8. Legal grounding analysis

**Mechanism.** For the six legal families, `legal_evidence.legal_reply`:
1. identifies the act by number or theme;
2. selects the requested article number exactly (or refuses if it is absent);
3. otherwise returns all articles (short acts) or the top 3 by term overlap (Law 2018-52, fee decree);
4. quotes the extracted article bodies verbatim, with no LLM.

This **removes the generation channel that produced the Article 16 fabrication**.

**Source-to-answer comparisons (most important cases)**

| Question | Official text | Candidate answer | Match |
|---|---|---|---|
| Art. 16, Law 2018-52 | "يعتبر تسجيل الشخص الطبيعي بالسجل التجاري قرينة بسيطة لثبوت صفة التاجر…" | Same text, § 16, p. 5 | ✅ exact |
| Name reservation validity / issuance | Art. 3: issued "في نفس يوم تقديم المطلب"; "صالحة لمدة ستة أشهر قابلة للتجديد مرة واحدة" | Both sentences verbatim | ✅ |
| BO threshold (décret 2019-54) | "نسبة تُساوي أو تفوق 20 % من رأس المال أو من حقوق الاقتراع" | Verbatim | ✅ |
| BO authority deadline (Arrêté 2026-35) | Art. 2: "deux (2) jours"; Art. 5: decision on public requests in "deux (2) jours" | Whole Arrêté; both provisions under their own article numbers | ✅ (no misattribution; verbose) |
| Fee decree, table 3 | Table 3 is inside Art. 1 | Arts. 4, 3, 6 | ❌ wrong provision (R1) |
| False-declaration penalty | Law 2018-52 Art. 55: 5 years and 50,000 TND | "Passages do not contain information" | ❌ false refusal (R3) |

**Limits.**
- The legal path never interprets: it quotes.
- Applicability to an individual case is never asserted, and the notice says so.
- Correctness therefore depends on article **selection**, which is reliable for explicit article numbers
  and short acts, and weak for the long fee decree.
- Questions on penalties or legal rules that do **not** name an act still go to Mistral.

## 9. Telegram-style conversation analysis

**Tested as HTTP context chaining only; this is not real Telegram.**
- **Subject and code retention:** RNE code retention, code correction (including dotted codes),
  passport residence clarification, CIN loss follow-up, topic change and reset all work (M1–M7, M9, M10).
- **M8 fails:** see R2.
- **Session scope:** in the bridge implementation (hash-identical to the candidate bridge image), sessions
  are keyed by `chat.id` with a 30-minute TTL, a 1000-session cap and in-memory storage only.
- **Isolation:** an in-process check confirmed isolation between private chats (sequential and 6
  concurrent) and shared context within a group chat.
- **Deployment effect:** recreating the bridge clears all sessions.
- **Wire contract:** the new `rne_code` / `legal_subject` fields require deploying the **bridge too**. The
  old bridge contract would drop them, and the code-retention fixes would not reach Telegram users.

## 10. Performance

| Operation | Candidate alone (median s) | With production running concurrently |
|---|---:|---|
| Passport / CIN checklist FR | 0.31 / 0.23 | 0.33 / 0.23 |
| RNE fee / deadline / follow-up | 0.08 / 0.08 / 0.08 | 0.14 / 0.12 / 0.12 |
| Legal article | 0.24 | 0.25 |
| Passport checklist EN (translation) | 17.8 | **192–204** |
| Form check PDF / PNG | 0.16 / 1.72 | 0.17 / 2.03 |
| Dossier validation PDF | 0.30 | **47–62** |

Production's own legal answer took 169–193 s, and its multi-turn follow-up 54–77 s, under the same load.

**Demo practicality:** the candidate on its own is fast enough for a 15-minute demonstration.
- **Sub-second:** everything except English translation (about 18 s) and PNG OCR (about 2 s).
- **Concurrency is not acceptable:** the two stacks must not run concurrently.

## 11. Security findings

| Finding | Status |
|---|---|
| Logs | Candidate logs: 6,220 lines, 0 occurrences of question text, Arabic content, `data_b64` or PDF base64. n8n does not save executions. |
| Ports | Candidate ports bound to 127.0.0.1 only (8001, 5679); no new public port |
| File validation | Enforced (corrupt PDF and text/plain rejected, 6/6) |
| Prompt injection | Ignored in 2 probes; the legal path cannot be injected because it generates nothing |
| Production data | Qdrant payloads identical to the pre-test snapshot; workflow `versionId` unchanged; corpus untouched (no write path exercised) |
| Secrets in env | `TELEGRAM_BOT_TOKEN` and `N8N_ENCRYPTION_KEY` present in **both** backend containers via `env_file`; not needed by the backend. Pre-existing; remediation: give the backend an explicit variable list. |
| Stray Qdrant | Container `qdrant` (unpinned image) still on **0.0.0.0:6333–6334, unauthenticated**, with collection `documents`. Unrelated to the project; not touched. Remediation: owner to bind it to 127.0.0.1 or stop it. |
| Shared-Qdrant mutation path | The candidate's `/index/run` and `/ingestion/run` would write to production Qdrant. Not called. Remediation: stop the candidate after the decision. |

## 12. Academic rubric reassessment (indicative engineering assessment, **not** a professor's grade)

| Criterion | Weight | Previous | Candidate (if deployed and smoke-tested) | Justification |
|---|---:|---:|---:|---|
| Prompt Engineering | 20 | 13 | 13 | No prompt changes. The legal fix replaces generation with deterministic extraction, a safety gain but not new prompt-engineering evidence. |
| RAG | 25 | 17 | 19 | Exact-key retrieval for codes; contextual RNE 0 → 190/190; legal hallucination channel removed; 480/480 spans. Fee-decree selection and the false refusal remain; no semantic accuracy estimate. |
| Multi-Agent Architecture | 25 | 15 | 16 | Structured dialogue state (code and legal subject) now flows end to end through n8n and the bridge contract. Still a fixed pipeline; no n8n error branches; M8. |
| Multimodality | 15 | 10 | 10 | Unchanged; verified again (8/8 uploads plus error cases). |
| Demo, Report, Q&A | 15 | 10 | 11 | Demo questions now answer correctly on the Telegram path. Docs still stale on Telegram status; the report predates the fixes. |
| **Total** | **100** | **65** | **69** | Applies **only after** deployment and production smoke tests. **Production today remains at the previous assessment.** |

## 13. Verdict

**Release decision: CONDITIONAL GO. Candidate status: READY WITH LIMITATIONS.**

**Rationale:**
- Every original critical defect is independently verified as fixed in the candidate.
- No regression was found across 728 replayed cases, 821 unit tests, 40 integration tests, and new
  routing, multi-turn and legal probes.
- Every remaining failure (R1–R11) also exists in some form in production today, or is a usability
  trade-off of the safer extractive design.
- Deploying improves on the current production on every measured axis.

**Conditions (all must hold):**
1. **Deploy backend and bridge together.** The bridge carries the new context fields; deploying only the
   backend leaves Telegram users without code and subject retention.
2. **Deploy outside the demonstration window, and first stop the candidate stack** (`post-audit-candidate`,
   `post-audit-n8n`). This removes the Ollama contention and the shared-Qdrant write path.
3. **Re-hash** the 9 sources immediately before tagging (`RELEASE_READINESS_CHECKLIST.md` P4).
4. **Run production smoke tests S1–S10 and the S11 replay.** Roll back on any trigger in §6 of the
   checklist.
5. **Real Telegram acceptance** (checklist §5) with an authorised chat before claiming the fix is live for
   Telegram users.
6. **Document R1–R4 as known limitations** in the demo and Q&A material. Avoid live demos of fee-decree
   table questions and article-number follow-ups.

**Genuine deployment blockers:** none, provided the conditions above are met. Concurrent operation of both
stacks during the demonstration **is** a blocker for demo readiness, but not for the code release.
