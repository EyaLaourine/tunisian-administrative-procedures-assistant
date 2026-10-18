# Automatic language detection and procedure-state isolation

Date: 2026-10-18. Branch: `fix/auto-language` (from `overnight/finalization`), commit `525830e`. Production was
not modified: no deployment or restart, no workflow change, no ingestion, and no write to production Qdrant.

**Verdict: READY FOR ISOLATED VALIDATION**

## 1. Root-cause analysis

The Telegram acceptance transcript text was not available to me. The production logs record only routing metadata
(language, intent, category, agent; never message text). The analysis combines those metadata (11:37–11:47 UTC) with
a code inspection of every stage: bridge, `/language`, workflow 03, router, dialogue, detection, checklist/answer
rendering and conversation state.

| # | Observed | Root cause (code) | Evidence |
|---|---|---|---|
| 1 | Arabic question answered in French until `/language` was used | `telegram_bridge/bridge.py` sent the `/language` selection as `payload.language` with **every** text message. Workflow 03 forwards it to `/agents/route`, which treats it as a **forced** language and skips detection. Without a selection, the backend already detected the language per message. | A passport question was routed `fr` at 11:43:03 and `ar` at 11:43:29; `/language` never reaches the backend, so this fits a forced `fr` followed by a selection change |
| 2 | After selecting Derja, a French question answered in Derja | Same mechanism (forced selection) | Business-registration question routed `derja` at 11:45:23, then `fr` at 11:45:44 |
| 3 | Derja question answered in Modern Standard Arabic | For Derja users the checklist quotes the **official Arabic (MSA) guide verbatim** (`TARGET_LANGUAGE["derja"] = "ar"`). This is by design, because official text is never rewritten. Only the headings were in Derja, and nothing explained that the body is the official MSA text. | 11:44:13: route `derja`, document `interior-passport-guide-ar` |
| 4 | Short follow-ups could switch language unpredictably | Detection used the current message only: "في تونس" was MSA, "oui" or "ok" was French, and there was no conversation-language memory | Code inspection |
| 5 | Duplicate-passport request reused 4 photos declared for a renewal | `agents/dialogue.py` kept `declared_items` for the whole `passport` category. A new application type (renewal → duplicate/`loss`) replaced only the hints. | 11:43:51: `remaining_documents` right after a different passport case |

**Not a defect, unchanged on purpose:** French-only official sources (national identity card guide, RNE texts) are
quoted in French for Arabic and Derja users. Machine translation FR→AR was evaluated earlier and produced
meaning-changing errors (`agents/checklist_builder.py`, `TRANSLATION_TARGETS = {"en"}`). The answer's explanations,
headings, sources and disclaimer follow the user's language, and a note now states the original language in
personalised checklists too.

## 2. Files changed (commit `525830e`)

| File | Change |
|---|---|
| `agents/language.py` | Scored detector with a confidence flag; `resolve_language()` (AUTO rules); `detect_language()` API unchanged |
| `agents/schemas.py` | `DialogueContext.language` (conversation language) and `preferred_language` (optional preference) |
| `agents/intent_router.py` | One `resolve_language` call per request (replaces four `req.language or detect_language(...)`); the language is recorded in the returned context |
| `agents/dialogue.py` | Uses the router's resolved language; procedure-state isolation; Derja note for official MSA text and original-language note in personalised checklists |
| `agents/checklist_builder.py` | Derja note for official MSA text |
| `agents/i18n.py` | `official_msa` strings (4 languages) |
| `prompts/language_identification/v1.yaml`, `prompts/registry.yaml` | New fallback prompt (new version file; no existing prompt edited) |
| `telegram_bridge/bridge.py` | AUTO by default: no forced language on text messages; preference sent only as context; answer language remembered per chat; Auto button |
| `telegram_bridge/contracts.py` | Bridge context contract accepts `language` and `preferred_language` |
| `telegram_bridge/ui.py` | Auto option (first row), preference/Auto wording in 4 languages |
| `tests/test_auto_language.py` | 63 new regression tests |
| `tests/test_telegram_bridge.py` | One line: `conv_language` (a validated enum) allowed in the session privacy check |

## 3. Language-detection design

**Per message** (`detect_language_details`):
- **Arabic script.** Derja is scored against MSA:
  - strong Derja markers (e.g. شنوة, كيفاش, باش, نحب, متاع, يلزمني, الباسبور) count 2;
  - weak markers that also exist in MSA (عندي, وين, اللي, ساكن) count 1;
  - MSA function and question words (هل, ماذا, أين, يمكنني, التي, المطلوبة) count 1.
  - Derja wins when its score is higher. The decision therefore does not rely on the Unicode script alone.
- **Latin script.** French, English and Arabizi Derja are scored with lexicons; Arabizi digits inside words
  (`3`, `7`, `9`) score 2, and French accents add to French.
- **Confidence:** a clear margin, with stricter rules for messages of 2 words or fewer. Acknowledgements ("oui",
  "ok", "merci", "yes", "اي", "شكرا", "behi") are never confident.

**Response language** (`resolve_language`), in order:
1. **forced:** an explicit `language` from API clients (web demo, CLI, evaluation scripts) and from the bridge's
   procedure-menu commands, whose text is fixed English;
2. **confident detection** of the current message;
3. **model fallback**, only for Latin-script messages of 4 words or more in which no marker of any language was
   found. It uses the existing local model with prompt `language_identification` v1, and only `en`, `fr` or `derja`
   is accepted. In tests and evaluation sets it was never triggered;
4. **conversation language:** the language of the previous answer, carried in the dialogue context;
5. **preferred language** chosen with `/language`;
6. **best deterministic guess.**

**Not involved:** the retrieved documents' language never affects the decision. No new LLM call is made for normal
messages.

**Language preference behaviour** (documented for users in `/language`):
- **Auto (default, first button):** each message is answered in its own language.
- **A selected language is a preference, not a lock.** It applies to menus and to very short or ambiguous messages
  when there is no conversation language yet. A clearly written question in another language is still answered in
  that language. This is deliberate: a lock is what caused failures 1 and 2.
- **Return to Auto:** the **Auto 🌐** button removes the preference. Its confirmation is sent in the conversation
  language.
- `/cancel` clears everything.

**Derja:**
- Clarifications, headings, notes, refusals, disclaimers and generated explanations are in Derja (existing Derja
  strings).
- Official legal and administrative quotations stay verbatim in MSA (or in French for French-only sources). A Derja
  note says so: "النص الرسمي مكتوب بالعربية الفصحى، نقلناه كيما هو باش ما يتبدلّش معناه."
- Latin-script Derja is answered in Arabic-script Derja, the existing response format.

## 4. Conversation-state fix

- **Declared documents** ("I have 4 photos") belong to one procedure. They are cleared when the application type
  changes (first time ↔ renewal ↔ duplicate/loss ↔ modification) or when another procedure is named (passport,
  national ID, RNE, legal subject). A document declared again in the same message counts.
- **Kept across procedures:** residence (a fact about the person) and the conversation language and preference.
- **Within the same procedure, declarations are kept**, as before ("Qu'est-ce qui me manque ?" still uses them).
- **Contract unchanged:** a `None` context still means "no change". The bridge keeps the answer's language
  separately (`conv_language`, a validated enum; no message content).

## 5. Regression-test results

| Suite | Result |
|---|---|
| Unit suite (`pytest -m "not integration"`) | **1160 passed**, 5 skipped (1097 before + 63 new) |
| New `tests/test_auto_language.py` | 63/63. Covers: detection (17 messages, both Derja scripts), short follow-ups, preference, forced language, validated model fallback; FR→AR, AR→FR, FR→Derja, Derja→EN, EN→FR, Latin- and Arabic-script Derja; clarification answers; preference vs Auto; legal citations; refusal; state isolation (duplicate after renewal, national ID, RNE, legal subject); Derja MSA note on the real official guide; bridge AUTO, preference, Auto button, keyboard and menu commands |
| **Isolated end to end** (real bridge code → canonical workflow 03 → candidate backend; Telegram API mocked) | **26/26 turns** in 8 scenarios, on the final images |
| Defect probes (`scripts/defect_probes.py`), isolated | **16/16**, the same as `rc-20261018b` |
| Multilingual evaluation (`scripts/multilingual_eval.py`), isolated | Identical to the `rc-20261018b` baseline on every metric: part A language 28/36, all 22/36, part B 13/13, and the same 8 pre-existing language misses. This suite forces `language`, so it checks rendering, not detection. |
| Detection on all 84 labelled questions of `data/evaluation/eval_set.jsonl` | 84/84 (old detector also 84/84; no regression) |

**Isolation of the end-to-end tests:**
- **Network:** a dedicated Docker network `lang-iso`.
- **Qdrant:** a throwaway copy restored from the Phase A snapshots (272/174), with no host port.
- **Backend:** the candidate, aliased `backend`, with admin and agent keys empty and read-only mounts.
- **n8n:** a throwaway instance with the canonical workflows 02 and 03 imported and published, unchanged.
- **Shared resource:** host Ollama, for inference only.

All containers and the network were removed afterwards. The evidence is in
`C:\Users\Eya Laourine\tna-backups\lang-validation-20261018\` (cases, per-turn results, probe and evaluation outputs,
scripts, `SHA256SUMS`).

The scenario messages come from this specification and from the Phase B manual acceptance checklist. The original
transcript text could not be included because it is not stored anywhere.

## 6. Performance impact

- **Detection:** 11.1 µs per message for the new detector (8.6 µs before) and 16.1 µs for `resolve_language` with
  context. This is negligible next to a turn of 0.05 s (rule reply) to about 35 s (English checklist with machine
  translation, unchanged).
- **Model fallback:** only for long Latin messages without any marker; never triggered in any test or evaluation
  set.
- **Latency:** isolated median latency in the multilingual evaluation was 0.17 s (baseline 0.16 s).
- **Memory:** no new per-request work besides one context field.

## 7. n8n compatibility verdict

**COMPATIBLE — NO WORKFLOW CHANGE REQUIRED.**
- **Context path:** workflow 03 passes `body.context` unchanged to `/agents/route`. The response nodes (direct
  reply, checklist, answer) return the router's `context`, so the conversation language travels in the existing
  field.
- **Language field:** `body.language` remains optional and is still honoured as a forced language for API clients.
- **Testing:** the canonical workflow files were used unmodified in the isolated test.
- **Mixed versions (verified with the images):**
  - the old backend `rc-20261018b` accepts the new context fields (ignored);
  - the old bridge `final-candidate` accepts responses carrying them (ignored).
  - The backend and bridge can therefore be deployed in either order, and either can be rolled back alone.
- **Error branch:** the "agent error" response node uses `body.language` (now usually empty) for its fallback text.
  The bridge replaces failed responses with its own error message in the conversation language, so users are
  unaffected.

## 8. Proposed release candidate and deployment plan (NOT executed; requires approval)

| Image | ID | Provenance |
|---|---|---|
| `tunisian-admin-assistant-backend:rc-20261018-lang` | `sha256:cec1028a82e51f48a392a03321eb2694255263357756bc20bb11b0ed0c81d96c` | 63/63 copied files hash-identical to `525830e` |
| `tunisian-admin-assistant-telegram:rc-20261018-lang` | `sha256:c247749d5f7ffdf75fac02fe33e2df58830b73a9ecf7ede718f1432ccc6b7415` | 10/10 files hash-identical to `525830e` |

**Production state needed:** the production checkout's `prompts/` must contain
`prompts/language_identification/v1.yaml` and the updated `prompts/registry.yaml`, because the backend mounts
`./prompts`.
- Without them, only the rare model fallback is disabled (logged, then the conversation language is used).
- With them, the release is complete.
- This is the only file change needed in the production checkout. `config/` and `workflows/` are unchanged.

**Plan** (same pattern as Phase B; no POST to admin endpoints; one service at a time):
1. Refresh backups: Qdrant snapshots and the n8n database, as in Phase A. Rollback tags already exist
   (`backend:rc-20261018b`, `telegram:final-candidate`), and both are safe to roll back to (admin guard present).
2. Copy the two prompt files into the production checkout.
3. Deploy the backend:
   `docker tag …backend:rc-20261018-lang …backend:latest && docker compose -p tunisian-admin-assistant up -d --no-deps --no-build --pull never backend`
   Then verify: `/health`, the static admin-guard check, and the bounded smoke test `scripts/phaseb_smoke.py`.
4. Deploy the bridge:
   `docker tag …telegram:rc-20261018-lang …telegram:latest && docker compose -p tunisian-admin-assistant --profile telegram up -d --no-deps --no-build --pull never telegram-bridge`
   Then verify one poller and no 409.
5. Manual Telegram acceptance by the owner. Without using `/language`: French → Arabic → Derja → English → French;
   a Latin-script Derja question; "في تونس" or "oui" after a clarification; then `/language` → Derja → a French
   question (answered in French, menus in Derja) → **Auto**.
6. **Rollback** (per service):
   `docker tag …backend:rc-20261018b …backend:latest` or `docker tag …telegram:final-candidate …telegram:latest`,
   then the same `up -d --no-deps` command. No data, Qdrant or n8n rollback is needed.

## 9. Remaining limitations

- French-only official sources stay in French for Arabic and Derja users, by design (see section 1).
- Latin-script Derja users receive Arabic-script Derja.
- A bare "oui", "ok" or "merci" is still routed as before (general answer or greeting); now it comes in the
  conversation language.
- The detector lexicons cover common administrative phrasing. Unusual spellings fall back to the conversation
  language or, for long unmarked Latin text, to the local model.
