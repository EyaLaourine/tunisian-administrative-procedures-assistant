# Release readiness checklist: post-audit candidate → production

Prepared by the independent post-fix audit (2026-10-17).

- **Status of each item:** every item below is a **gate for the operator**. Items marked ✅ were
  verified by this audit **before** deployment; unmarked items must be executed and recorded at
  deployment time.
- **What may be deployed:** nothing in this checklist authorises deployment by itself. See the verdict in
  `docs/POST_FIX_INDEPENDENT_AUDIT.md`.

## 1. Pre-deployment checks

| # | Check | Command / evidence | Status |
|---|---|---|---|
| P1 | Candidate backend image is the reviewed one | `docker image inspect tunisian-admin-assistant-backend:post-audit-final --format "{{.Id}}"` → `sha256:7254fcf2401…` | ✅ verified |
| P2 | Candidate bridge image is the reviewed one | `…telegram:post-audit-final` → `sha256:befa1e0c0a81…` | ✅ verified |
| P3 | Image sources = reviewed repository files | SHA-256 of the 9 changed files equal in the repository, the candidate container and the bridge image (`contracts.py` 208d1585…, `bridge.py` 56188f7b…, `ui.py` 1753bb39…) | ✅ verified |
| P4 | Repository unchanged since review | Re-hash the 9 files immediately before tagging; any difference → STOP | at deployment |
| P5 | Unit suite on the same sources | `.venv\Scripts\python.exe -m pytest -m "not integration" -q` → 821 passed | ✅ verified (today) |
| P6 | Candidate integration suite | See `POST_FIX_REGRESSION_RESULTS.md` | see results |
| P7 | No production mutation during candidate testing | Qdrant payloads identical to the 11:44 UTC snapshot (272/174); workflow 03 `versionId 92f81ea7…` | ✅ verified |
| P8 | Stop the candidate stack before the demo or rollout | Avoids Ollama contention (see audit §10). Operator action, not performed by the audit. | at deployment |
| P9 | Stray Qdrant `0.0.0.0:6333` | Owner decision: bind to 127.0.0.1 or stop. Not touched by the audit. | open |

## 2. Backups (must exist before the switch)

| Item | Location | Status |
|---|---|---|
| Backend rollback image | `tunisian-admin-assistant-backend:post-audit-before` = `8adaf99471c5` = running production image | ✅ verified |
| Bridge rollback image | `tunisian-admin-assistant-telegram:post-audit-before` = `7eafea6e792d` = running bridge image | ✅ verified |
| Qdrant snapshots | `data/evaluation/post_audit_backup/qdrant/*.snapshot`; SHA-256 match `manifest.json` (272 / 174 points) | ✅ verified |
| Workflow 03 export | `post_audit_backup/active_workflow.json`, `versionId 92f81ea7…` (= deployed) | ✅ verified |
| Pre-change sources | `post_audit_backup/agents/*`, `backend/agents_api.py`, `telegram_contracts.py` (hashes = production) | ✅ verified (3 files spot-checked) |
| `.env` | Not copied anywhere. Keep the operator's own private backup. | operator |

## 3. Deployment prerequisites

1. All **blocking** items in `POST_FIX_INDEPENDENT_AUDIT.md` §13 are resolved or explicitly accepted by
   the project owner.
2. A maintenance window outside the demonstration slot. Recreating the bridge clears in-memory sessions.
3. Replace only the backend and the bridge. n8n, Qdrant, Ollama, workflow and corpus stay untouched
   (commands in `docs/POST_AUDIT_FIX_REPORT.md` → "Coordinated deployment").
4. Never print `docker compose config` without `--quiet`, or container environments.

## 4. Smoke tests (production, immediately after the switch; query-only)

| # | Request (webhook 127.0.0.1:5678) | Pass criterion |
|---|---|---|
| S1 | `{"text":"Quelle redevance pour RNE C 001 (Personne physique commerçant; Création) ?","language":"fr","context":{}}` | Body contains `Code procédure: RNE C 001` and `vingt dinars (20 TND)`; not a source-only reply |
| S2 | Same as S1 without `context` | Same row |
| S3 | `RNE I 001` fee, `context:{}` | Row `RNE I 001` and `Dix Dinars`, no C-row substitution |
| S4 | `Quelles pièces pour une CIN après une perte ?`, `context:{}` | Title "…pour cause de vol, de perte ou de détérioration", item `Attestation de déclaration de perte` |
| S5 | Arabic `من أجل` documents question (audit case `interior-passport-guide-ar:guide_scenario:018`) | Intent `required_documents`; `شهادة ضياع جواز السفر` present |
| S6 | `ماذا ينص الفصل 16 من قانون السجل الوطني للمؤسسات 52 لسنة 2018؟` | Body contains `قرينة بسيطة` (official Article 16); no generated paraphrase |
| S7 | `Que dit l'article 999 de la loi 2018-52 ?` | Refusal or insufficient evidence; no invented text |
| S8 | F-001 PDF upload, and again with `mode:"dossier"` | Recognised; 7 missing fields; `completeness_certified:false` |
| S9 | `Comment obtenir un extrait de naissance ?` | Not-covered reply |
| S10 | `/health`, `/healthz`, both Qdrant counts 272/174 | All healthy; counts unchanged |
| S11 | Full replay: `scripts/post_audit_regression.py --url http://localhost:5678/webhook/assistant --backend-url http://localhost:8000 --label production_after_review` | Same group results as the candidate (`POST_FIX_REGRESSION_RESULTS.md`) |

## 5. Real Telegram acceptance (authorised chats only; record evidence without personal data)

HTTP smoke tests do **not** prove Telegram delivery. Before declaring the release live:

1. The bridge log shows `telegram_bridge_started` after the recreate, and no `PollingConflict` or
   `TelegramAPIError` loop.
2. `/start`, `/help`, `/language` in all 4 languages.
3. S1, S3, S4 and S6 typed in a real chat; compare against §4.
4. RNE follow-up: `RNE C 012` fee → "Et le délai ?" → correction to `RNE C 010.1`.
5. Beneficial-owner access → "Et quelles sont les conditions ?": the subject is retained, or a clarification
   is asked.
6. Second authorised private chat with a different topic: no context leakage. **Do not test in group
   chats.** Sessions are keyed per chat, so group members share context (known limitation).
7. Upload the public blank F-001 PDF and a rendered PNG in `/form_check` and in `/dossier_check`.
8. `/cancel` mid-request; then a new question confirms the context was reset.
9. Record the sent message, the received reply (first lines), the date and the image digest.

## 6. Rollback triggers (any one → roll back immediately)

- Any S1–S9 failure.
- A source-only reply (icon + sources, empty body) on any RNE question.
- Any generated legal paraphrase or quotation that is not a verbatim extracted article.
- `completeness_certified` not `false`.
- Bridge restart loop, `PollingConflict`, or authentication failure.
- Qdrant counts ≠ 272/174, or n8n workflow `versionId` changed.
- p95 latency of the RNE/guide paths > 5 s with the candidate stack stopped.

**Rollback:** see `docs/POST_AUDIT_FIX_REPORT.md` → "Rollback" (re-tag `post-audit-before` and recreate
only the backend and bridge). Then re-run S1–S10 against the restored images.

## 7. Post-deployment verification

1. Re-hash `/app` sources in the new production backend and bridge containers; they must equal P3.
2. Run the S11 replay and archive it under a new label. Never overwrite the original baselines.
3. Scan the logs for metadata only (no question text, no base64, no token).
4. Update `docs/TELEGRAM_REPORT.md`, `docs/TELEGRAM_ACTIVATION.md` and demo docs with the observed
   live evidence (documentation is currently stale; see the earlier gap G-12).

## 8. Unresolved risks (accepted or to be accepted by the owner)

See `POST_FIX_INDEPENDENT_AUDIT.md` §12 for the evidence. In summary:
- Legal answers are long, untranslated verbatim excerpts.
- No semantic accuracy estimate exists.
- Group-chat context is shared.
- n8n has no error branches.
- Ollama contention on a 4 GB GPU.
- `applicability` of every legal text is unverified.
- No real-photo or handwriting evaluation.
