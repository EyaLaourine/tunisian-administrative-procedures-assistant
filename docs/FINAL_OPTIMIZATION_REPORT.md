# Final optimisation report (2026-10-17)

**Scope:** implementation, optimisation, testing and documentation on the **candidate** only. **Production was
not changed:**
- images `…backend:latest` = `8adaf99471c5` and `…telegram:latest` = `7eafea6e792d`, as before;
- workflow 03 `versionId 92f81ea7…`;
- Qdrant collections 272/174 with payloads identical to the audit snapshot (§6);
- no restart and no Telegram message.

## 1. Baseline protection

| Item | Value |
|---|---|
| Version control | The project had no VCS. A local Git repository was created; `.env` is ignored. A scan of tracked files found no token pattern (`.env.example` holds placeholders only). |
| Recoverable snapshot | Tag `candidate-baseline` = commit `1cea1d7`. This is the independently verified post-audit candidate (backend image `post-audit-final` `7254fcf2…`, bridge `befa1e0c…`). |
| Final candidate commits | `47626f2` (legal, routing, session fixes), `01752fc` (workflow error branches, admin key, report, annex, assessments), `0eb76af` (form instructions, table-vs-provision fix), `f9ac5ce` + `60dbeeb` (deterministic limits reply, then narrowed after a replay regression), `4763ece` (retrieval corroboration only breaks ties; applicability questions), followed by documentation/report commits. |
| Final candidate images | `tunisian-admin-assistant-backend:final-candidate` `sha256:c4c2362a7427…`; `tunisian-admin-assistant-telegram:final-candidate` `sha256:8e07af5912e7…` (new tags; no existing tag moved). All final results were produced on this backend image. |
| Final candidate stack | `final-candidate` (backend, 127.0.0.1:8002; data, config and prompts mounted **read-only**; explicit, secret-free environment) and `final-n8n` (127.0.0.1:5680; workflow copy `deploy/final_candidate/workflow_03_final_candidate_v2.json` whose 6 HTTP nodes point to `final-candidate`). |
| Shared services | Production Qdrant (read path) and host Ollama. No index or ingestion endpoint was called. |
| Rollback | `git checkout candidate-baseline` (code); images `:post-audit-final` and `:post-audit-before` untouched; Codex's `post_audit_backup/` untouched. |

### Hash manifest: changed source files (candidate-baseline → final candidate)

The container hashes were verified identical to the repository for every changed backend file and the bridge image.

| File | Baseline SHA-256 (12) | Final SHA-256 (12) |
|---|---|---|
| `agents/dialogue.py` | `06110116b611` | `974da25e0e48` |
| `agents/intent_router.py` | `0d47db766ff2` | `f65b5917fc16` |
| `agents/legal_evidence.py` | `c03c69be47f7` | `fc632bae7054` |
| `backend/main.py` | `223eb6d82ed7` | `44baa9c8e291` |
| `backend/settings.py` | `cbd87453e1c4` | `e9c7e3370899` |
| `telegram_bridge/bridge.py` | `56188f7bc812` | `db98a4757028` |
| `workflows/03_assistant_multi_agent.json` | `d3af3d8f3197` | `1893f28c3ea0` |
| `tests/test_final_fixes.py`, `scripts/make_prompt_annex.py` | new | new |

Unchanged:
- prompts and the prompt registry;
- `rag/`;
- the corpus (`data/raw`, `data/processed`);
- the evaluation ground truth;
- Codex's post-audit evidence;
- the production workflow in the n8n database.

## 2. Corrections: defects, root causes, fixes

| # | Defect (observed) | Root cause (verified) | Fix | Evidence |
|---|---|---|---|---|
| F1 | Fee-decree questions quoted the **wrong article**. "Que couvre le tableau 3 ?" returned Arts. 4/3/6; "Que prévoit le décret … pour les redevances ?" returned Arts. 5/7/6. | Raw term overlap was dominated by words of the act's own title ("décret", "2022", "présidentiel"), which occur in signature and repeal articles. Tables are not articles. | Table-level extraction (`Tableau n°N` segment of the article that holds it). IDF ranking that ignores the act's title words. A question about a provision that merely mentions a table (the reduction of Art. 4) selects that provision. | Tests `test_fee_decree_*`; final regression §3 |
| F2 | **False refusal on false-declaration penalties** (Law 2018-52 Art. 55 exists). | An English question that does not name the act never reached the legal extractor; the LLM path said "not in the passages". | False-declaration and penalty themes map to Law 2018-52; a cross-lingual *search* vocabulary (no legal content) lets an English or French question select the Arabic article. | Art. 55 quoted in EN/FR; tests |
| F3 | **Articles 20 and 27 of Law 2018-52 unreachable** (an "Art. 20" request would be refused). | Extraction artefacts: "ال فصل20" (space inside the word) and an article starting mid-block after a full stop; the text before a mid-block start was dropped from the previous article. | The regex accepts the split form. A mid-block start is accepted only as the **next number in sequence** after a sentence end, which excludes cross-references such as "من الفصل27". The preceding text stays in the previous article. | 64/64 articles parsed (was 62/64); Art. 26 complete; the other five acts unchanged |
| F4 | **Article follow-up lost the legal subject** ("Que dit l'article 5 ?" after a beneficial-owner question → out of scope). | The follow-up had no category keyword, intent or "et …" prefix, so the dialogue layer returned it to the stateless router, whose LLM fallback chose out of scope. | An explicit article reference is a contextual follow-up when a legal subject is in context. Without an identifiable act, the router asks which text (never guesses). | Tests; multi-turn M8 (§5) |
| F5 | **CIN / Derja routing gaps:** "njaded", "dhaya3t", "baddel", "سرقت" and "détériorée" (web path), and "my data changed" (EN) routed to the first-application scenario. | The two routing paths used different keyword lists; Latin-Derja and stem variants were missing. "My data changed" fell to LLM fact extraction, which misread it as declared documents. | Shared vocabulary in both paths (renewal, loss/theft/damage, modification including explicit data-change phrases). "baddel" maps to modification, consistent with the existing "nbaddel"; loss words take precedence. | 16 routing tests (8 phrases × 2 paths); matrix §4 |
| F6 | **Questions about a form's printed instructions** received the generic welcome (8 suite cases). | The `form_help` intent always produced the upload-help reply. | A question naming F-001/F-002 and asking what it says is answered by quoting the form's printed instruction block verbatim (or insufficient evidence). Generic form help is unchanged. | Tests; suite group `direct_factual` (§3) |
| F7 | **Group-chat members shared one session** (privacy). | Sessions keyed by `chat.id` only. | Per-member key `(chat.id, from.id)` in groups; private chats unchanged; `/cancel` and language callbacks per member. | Tests (isolation, cancel, language) |
| F8 | **No orchestrator error handling** (gap G-10). | No `onError` on any n8n node. | Error output on all 6 agent nodes → structured, localised `503` with `failed_agent`. | Exercised by stopping the candidate backend: 3/3 structured 503 replies in 4–5 s (§7 of the regression results) |
| F9 | **Unauthenticated state-changing endpoints.** | — | Opt-in `ADMIN_API_KEY` (constant-time comparison); default behaviour unchanged. | Unit test |
| F10 | Regression introduced and fixed in this cycle: the first table rule captured "quelle réduction … tableau 1" (expected Art. 4). | The table reference took precedence over the topic. | Topic words (reduction, refund, payment, taxes, repeal) give precedence to article ranking. | Found by the full replay (`fee_condition:electronic`); test added; re-run clean |
| F11 | **An LLM asserted that a procedure "est toujours en vigueur"** in reply to a guarantee request; meta-questions about applicability were answered with generated text. | Applicability is unverified for every document; the generic answer path could still assert it. | Deterministic four-language *limits* reply for requests to certify validity, acceptance or completeness, and for "what to verify before applying this text". A first, broader pattern also caught 24 scope questions (found by the replay) and was narrowed. | Tests; replay: 24 limits replies, 0 validity assertions |
| F12 | Through n8n, the generic fee-decree question still selected Arts. 5–7. | Retrieved passages gave corroboration points to articles that had no term evidence. | Corroboration only breaks ties between articles that already have evidence. | Test with retrieved Art. 5 passage; legal direct factual 26/30 |

## 3. Remaining defects (not fixed)

- **"Et si mon cas ne correspond pas à ce texte ?"** after a CIN, passport or RNE answer repeats the official text
  instead of asking for case details. The expected label is a clarification.
- **Meta-questions** ("what is this document's scope", "what must I verify", "guarantee it is in force")
  receive the full official checklist plus the non-certification notice. This is safe but not a direct answer.
- **Legal answers** are complete articles in their original language: long, and untranslated for English
  users.
- **Unnecessary clarifications:** the passport application-type clarification is sometimes asked although the
  type was stated (3 Telegram-shape cases).
- **Intent labels** differ from the original expectations in the remaining mismatch cases, analysed
  individually in `FINAL_REGRESSION_RESULTS.md` §6.
- **Infrastructure risks** (production `env_file` passing the token, the stray Qdrant on 0.0.0.0, no webhook
  authentication) need production approval: `FINAL_SECURITY_REVIEW.md` §2.

## 4. Architecture outcome

**Orchestrated multi-agent architecture** (see `MULTI_AGENT_ARCHITECTURE_ASSESSMENT.md`):
- **Orchestrator:** n8n;
- **Specialised agents:** six;
- **Generate with an LLM:** two;
- **LLM as a fallback classifier:** one;
- **Deterministic services:** three.

No autonomous agent was added; the improvements are evidence-aware escalation inside the answer agent,
dialogue state for legal subjects, and orchestrator error handling.

## 5. Evaluation and academic outputs

- **Results:** `FINAL_REGRESSION_RESULTS.md`.
- **Report:** `report/main.tex` restructured into the required 8 sections. The main report including references
  is within 8 pages; the prompt-library annex (`report/appendices/prompt_library.tex`) is generated from the
  actual prompt files by `scripts/make_prompt_annex.py`.
- **Also updated:** figures (`figures/agents.tex`, `figures/architecture.tex`), `references.bib`, and
  `docs/QA_PREPARATION.md`.

## 6. Production untouched: verification

Verified at the end of the work (`FINAL_REGRESSION_RESULTS.md` §9):
- production containers have the same IDs and start times as before;
- workflow 03 `versionId` is unchanged;
- Qdrant payloads are identical to the audit snapshot.
