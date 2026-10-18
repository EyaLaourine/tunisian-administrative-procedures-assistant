# Conversational understanding fix (Phase D)

Date: 2026-10-18. Branch: `fix/conversational-understanding` (from `fix/auto-language`), commit `5a2f195`.
Production was not modified, restarted or written to; no workflow change; no ingestion or indexing; no Telegram
message was sent.

**Verdict: READY FOR ISOLATED VALIDATION**

## 1. Root cause

The verbatim Telegram transcript was not available, because production logs record routing metadata only, never
message text. The production routing log of the acceptance session (12:43–12:49 UTC) matches the reported defects
one to one:

| # | Defect | Logged route | Root cause |
|---|---|---|---|
| 1 | "oui" after a passport discussion returned the generic refusal | 12:48:29 `out_of_scope`, method **llm** | No rule recognised affirmations. With no procedure word, the router fell through to the LLM category classifier, which answered "none/out_of_scope", so the refusal text was sent. The LLM call also took about 16 s. |
| 2 | "merci" returned the full welcome text | 12:48:55 `greeting`, method rules | `GREETING_KEYWORDS` contains `merci`, `thanks`, `شكرا` and `يعيشك`, which mapped gratitude to the welcome greeting |
| 3 | "نحب نبدّل الباسبور، شنوة يلزمني؟" was handled as a duplicate request | 12:45:31 `required_documents` → checklist from the Arabic guide | The verb "نبدّل" (change/replace) matched no application type, so the dialogue kept the **previous** case (`loss`, from the Arabic duplicate question at 12:44:45). The Latin "nbaddel" was even mapped to *data modification*. For a passport, "change" can mean renewal, replacement after loss or modification. |
| 4 | Derja wording could be more natural | — | The Derja passport clarification read as a literal translation |

Related gap found during the investigation: a courtesy word around a real question ("merci, et pour les frais ?")
was also routed as a greeting.

## 2. Changes (commit `5a2f195`)

| File | Change |
|---|---|
| `agents/conversation.py` (new) | Deterministic conversational intents (no LLM): `classify()` (affirm, deny, thanks, greeting, farewell in FR/EN/MSA/Derja, Arabic and Latin script, with repeated letters and multi-word phrases such as "يعطيك الصحة", "merci beaucoup", "au revoir"); `strip_courtesy()`; `pending_question()`; `reply()` with short replies in 4 languages |
| `agents/intent_router.py` | Small talk is answered first (before retrieval) with the dialogue context returned **unchanged**. Courtesy words before or after a real question are removed before routing. |
| `agents/dialogue.py` | For a passport, an ambiguous "change/replace" verb (`نبدّل`, `نبدل`, `تبديل`, `نغير`, `nbaddel`, `changer`, `remplacer`, `replace`) without an explicit case drops the inherited application type and procedure-specific declarations, then asks first time / renewal / replacement. Explicit data-change cues (address, name, data…) still mean modification, and the national-ID behaviour is unchanged. The Derja wording of that question was revised. |
| `tests/test_conversational_understanding.py`, `tests/fixtures/phase_c_acceptance_session.json` | 86 regression tests and the session fixture |

**Unchanged:** official facts, fees, quotations, citations, prompts, workflows and the Telegram bridge (its code is
identical to the deployed `rc-20261018-lang`).

## 3. Behaviour

| Message | With a pending clarification | Without one |
|---|---|---|
| Affirmation (oui, yes, نعم, إي, ey, ok, باهي…) | The open question is asked again with "Pour continuer, j'ai besoin de cette précision :". An either/or question cannot be answered by "oui", so the assistant never guesses. | "D'accord ! Vous pouvez me poser une autre question (frais, délai, lieu de dépôt)…" |
| Negation (non, no, لا, le…) | Same re-ask | "D'accord. Si vous avez besoin d'autre chose…" |
| Gratitude (merci, thanks, شكرا, يعطيك الصحة, ya3tik saha…) | Brief "Avec plaisir !…", never the welcome text | same |
| Greeting | Short greeting plus the pending question | Full welcome on a fresh chat; a short greeting in an ongoing conversation |
| Farewell (au revoir, bye, بالسلامة, bslema…) | Short goodbye | same |

- **Language:** replies use the message language when it is clear, otherwise the conversation language (Phase C
  rules).
- **Context:** the procedure, case, residence and declared documents are kept, so "merci" followed by
  "et pour les frais ?" continues the same renewal.
- **Scope:** only messages made **entirely** of these words are small talk. "oui, en Tunisie", "non, à l'étranger"
  and "يعطيك الصحة شنوة يلزمني للباسبور" still go through normal routing.
- **No facts:** replies contain no administrative facts (a test enforces this).

## 4. Tests

| Suite | Result |
|---|---|
| Unit suite (`pytest -m "not integration"`) | **1246 passed**, 5 skipped (1160 + 86 new) |
| Language-detection tests (`tests/test_auto_language.py`) | 63/63 (unchanged) |
| New `tests/test_conversational_understanding.py` | 86/86. Covers: classification (37 messages) and non-small-talk messages (13); courtesy stripping (9); the reconstructed Phase C session; re-asking passport and legal-act questions; yes/no without a pending question; gratitude in 4 languages with context preserved; gratitude followed by a contextual question; first vs ongoing greeting; farewells; no facts in replies; ambiguous change in Derja (Arabic and Latin script), French and English; resolving the ambiguity; explicit cases not treated as ambiguous |
| **Isolated end to end** (production bridge image `rc-20261018-lang`, Telegram mocked → canonical workflow 03 → candidate backend → Qdrant restored from snapshots) | Conversational scenarios **22/22**, including the 9-turn session fixture. The Phase C language suite **26/26** after regenerating its expected strings for the reworded Derja question. |
| Defect probes, isolated | **16/16** |
| Multilingual evaluation, isolated | Identical to the `rc-20261018b` baseline in all 49 records (part A language 28/36, all 22/36, part B 13/13) |

**Session fixture caveat:** the fixture is a reconstruction. Its message texts are the phrases you reported plus
the Phase C checklist messages that match the logged route sequence, and the logged metadata is recorded with each
turn. If you provide the verbatim transcript, it will replace the `text` values without changing the test logic.

**Evidence** (cases, per-turn results, probes, evaluation, scripts, `SHA256SUMS`):
`C:\Users\Eya Laourine\tna-backups\conv-validation-20261018\`. The isolated containers and network were removed.

## 5. Performance

- **Per message:** `classify` takes 13.7 µs and `strip_courtesy` 27.3 µs.
- **Routing:** a full route for "oui" now takes 0.10 ms, against about 16 s before (LLM fallback); "merci" takes
  0.03 ms. Normal questions take 0.56 ms of routing, unchanged in practice.
- **Pipeline:** no extra LLM call or retrieval.

## 6. n8n compatibility

**COMPATIBLE — NO WORKFLOW CHANGE.**
- **Response shape:** small-talk replies use the existing `next_agent = "reply"` branch (`intent = "greeting"`) and
  return the dialogue context unchanged, so no schema or contract changes.
- **Testing:** the canonical workflow files were used unmodified in the isolated test.

## 7. Proposed release (not deployed; requires approval)

**Backend only:** `tunisian-admin-assistant-backend:rc-20261018-conv`
`sha256:d9d9f8ca7962ce6135317a6e7ae9b2e7bd24eb0bfc9d9cd6cd2d00caa84e133c`. All 64 copied files are hash-identical to
`5a2f195`.
- **Bridge:** stays `rc-20261018-lang` (`c247749d5f7f`), already in production; its code is unchanged.
- **Prompts and config:** no change; production prompts already contain the Phase C files.

**Deployment** (same pattern as Phase C; no POST to admin endpoints):
1. Refresh the backups.
2. Run
   `docker tag …backend:rc-20261018-conv …backend:latest && docker compose -p tunisian-admin-assistant up -d --no-deps --no-build --pull never backend`.
3. Check `/health`, the static admin-guard check, the bounded smoke test and a small end-to-end subset with Telegram
   mocked.
4. Manual Telegram acceptance.

**Rollback:** `docker tag …backend:rc-20261018-lang …backend:latest` followed by the same `up` command (the Phase C
release, protected). Never roll back to `8adaf99`.

## 8. Limitations

- Small talk mixed with an unrelated question in one message is routed by its content only. The courtesy word is
  ignored, with no separate "thank you" reply.
- A bare "oui" with no pending question gets a generic follow-up offer. The assistant does not ask yes/no questions
  of its own, so no affirmation can confirm an action.
- Other Derja strings were reviewed and kept, because they already read naturally. Only the passport clarification
  was reworded.
