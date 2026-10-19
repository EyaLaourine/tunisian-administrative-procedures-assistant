# Telegram demo fixes - 19 October 2026

Scope: release checkout, branch `release/github-ready`. No production deployment, restart, token change,
workflow update, ingestion or Qdrant write was performed. These corrections are not yet active in the real bot.

## Findings and corrections

| Finding | Cause and change |
|---|---|
| CIN dossier summary contained zeros above real missing-field findings | The recognized-form/no-dossier-rules return populated text but left all structured lists at their empty defaults. The unchanged n8n response expression forwarded those defaults. The backend now retains required-field findings, conditional roles, manual checks and citations. For the official blank CIN: 10 missing, 3 conditional, 6 manual checks. Administration fields are excluded. No dossier rules are invented; completeness is explicitly unevaluable. |
| Arabic/Derja CIN headings accompanied French items | Automatic FR-to-AR translation was deliberately disabled after semantic errors (including widow mistranslation). A bounded application translation now covers the exact normalized title/items of all four indexed CIN guide scenarios. Original items/citations remain intact. Numbers must match; unknown/changed text rejects the whole translation. Derja explanations surround Modern Standard Arabic items, explicitly labelled as an application translation, not an official Arabic source. Unsupported translation falls back with an explicit notice. Unrestricted Arabic machine translation remains disabled. |
| Blank RNE signature was absent from Form Check findings | RNE templates had no manual-only entries in the FormHelper role configuration, although dossier rules already listed signatures. SHA-pinned F-001/F-002 entries now expose printed signature/box labels under manual verification. No signature presence/authenticity detector is introduced. A neutral partially filled F-001 fixture retains exactly date, email, GSM and depositor ID as missing, with signature separate. |
| Passport fee conflict warning could disappear | ChecklistBuilder already compares aligned FR/AR sources, but free-form and passage-fallback answering bypassed that rendering. Those passport money answers now reuse the deterministic parallel-source discrepancy check and preserve both citations. Regressions cover all four languages, both retrieved source languages, fee/document intents and the free-form fallback. The exact historical French conversation was not available for replay. |
| Slow response | See measurement below. New metadata separates model loading/prompt evaluation/generation, embedding batches and total bridge webhook time/retry count. Existing backend endpoint timers remain. No questions, prompts, response text or document values are added to logs. |

## Verification

Commands (release checkout):

```powershell
# Focused suite, before the final three timing regressions were added:
python -m pytest tests/test_telegram_demo_regressions.py tests/test_phase_e.py tests/test_phase_g_forms.py tests/test_dossier_validator.py tests/test_checklist_builder.py -m "not integration" -q
# 126 passed, 2 skipped

python -m pytest tests/test_telegram_demo_regressions.py -q
# Final focused demo regressions: 28 passed

python -m pytest -m "not integration" -q
# Final complete run: 1427 passed, 7 skipped, 41 deselected; 6 dependency deprecation warnings
```

The existing suite covers commands including /start, context retention, citations, refusals and English.
New regressions exercise the actual official blank CIN and synthetic neutral F-001 copies. They verify
translation line/number preservation, the widow term, explicit fallback, both passport sources and
metadata-only timing logs. Two existing expectations were intentionally updated: CIN now translates
instead of always retaining French, and RNE Form Check now lists manual signature checks.

The actual WF03 response expression was executed offline against the new CIN DossierReport and parsed
by the real bridge contract/renderer: missing=10, manual=6, conditional=3 in field details; no official
checklist; original citation preserved. No live n8n workflow was edited or executed for this check.

## Latency measurement and limits

A single read-only HTTP probe used the already-running disposable `fresh-*` stack with its unchanged
backend, asking for renewal documents for a passport in Tunisia in French:

- HTTP round trip through n8n: **5.434 seconds**, status 200, checklist builder, two citations.
- Backend route timer: **21 ms**, deterministic rules.
- Retrieval timer: **5082 ms**.
- Checklist timer: **54 ms**.
- Remaining approximately **277 ms** includes transport, scheduling and workflow overhead; it is not a
  pure measurement of n8n execution time.

Retrieval dominated this probe. The reported three-minute Telegram response was not reproduced and
its original stage-level trace was unavailable. Cold model loading, translation, retries or resource
contention remain hypotheses, not verified explanations. There is no claimed before/after production
speed improvement. The bounded CIN Arabic path requires no model call. New model-duration metadata
allows future traces to distinguish loading from generation without recording user content.

## Files changed

- `agents/dossier_validator.py`, `agents/schemas.py`: structured field retention and manual-only metadata.
- `agents/form_helper.py`, `agents/form_roles.py`: RNE manual signature/box reporting, pinned to official hashes.
- `agents/checklist_arabic.py`, `agents/checklist_builder.py`, `agents/dialogue.py`, `agents/i18n.py`: bounded CIN Arabic translation and explicit notices/context rendering.
- `agents/answer.py`: parallel-source fee warning on money-related passport answers.
- `agents/llm.py`, `rag/embeddings.py`, `telegram_bridge/bridge.py`: metadata-only duration measurements.
- `telegram_bridge/dossier.py`, `telegram_bridge/ui.py`: distinguish field counts from unassessable dossier completeness.
- `tests/test_telegram_demo_regressions.py`, `tests/test_phase_e.py`, `tests/test_phase_g_forms.py`: new regressions and updated intended behaviors.
- This report.

## Remaining acceptance and publication

Manual Telegram tests with the updated backend/bridge remain pending. Deployment requires separate
approval; no production service was changed. New application translations should receive human language
review before broader use. Other untranslated sources remain explicitly labelled in their original
language; no new official Arabic documents are claimed. Signatures remain manual checks, not a detected
missing signature or authenticity verdict. Poor-image OCR and conditional-field interpretation limits remain.

Before push, GitHub reported a public repository with `master` as its default branch and no release
branch. This task preserves visibility and master; only `release/github-ready` is published. No merge,
force-push or production update is authorized here.
