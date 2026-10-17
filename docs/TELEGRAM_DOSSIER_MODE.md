# Telegram Dossier Validator mode

Implemented and verified on October 16, 2026 (Tunisia local time).

## Changes

- `telegram_bridge/contracts.py`: optional upload-only `mode: "dossier"` and typed dossier response
  metadata. Ordinary uploads serialize without a mode field. A response claiming completeness is
  certified is rejected rather than displayed as a certification.
- `telegram_bridge/ui.py`: `/dossier_check`, a Dossier Validation main-menu button next to Form Check,
  prompts, six status-category labels and an informational-only disclaimer in English, French,
  Arabic and Tunisian Derja. The existing main menu, Back and New question remain available.
- `telegram_bridge/bridge.py`: capture the selected upload mode, forward it only on files, process
  the new callback, render dossier results, and clear the mode on Form Check, New question or /cancel.
- `telegram_bridge/dossier.py` (new): compact counts for filled, missing, unreadable and unverifiable
  fields; officially supported requirement count; unverified requirement explanations; original
  backend report and citations; limitations and non-certification disclaimer.
- `tests/test_telegram_bridge.py`: unit coverage for the new command, all menu languages, callbacks,
  PDF/PNG/JPEG/photo modes, mode reset, normal text isolation, formatting, privacy, unsupported/error
  replies and malformed/certifying responses.
- `tests/test_telegram_integration.py`: four additional cases through the live n8n webhook, exercising
  PDF and PNG uploads in both ordinary Form Check and Dossier Validation modes.
- `docs/TELEGRAM_DOSSIER_MODE.md` (this file): implementation, payloads, verification and manual checks.

No agents, backend, RAG, n8n workflow, academic report, environment secrets or Compose configuration
were modified. Only the Telegram bridge image/container was rebuilt/recreated.

## Usage

Use `/start` → Dossier Validation, or `/dossier_check`, then upload a PDF, PNG, JPEG or Telegram photo.
The selected upload mode persists until Form Check (`/form_check`), New question, `/cancel`, session
expiry or process restart. Language selection persists independently. Text questions never acquire
`mode`, even when Dossier Validation is selected. Existing procedure/checklist behavior is preserved.

The report separates six categories:

1. Filled fields.
2. Missing fields.
3. Unreadable fields.
4. Fields that cannot be verified.
5. Requirements supported by official sources.
6. Requirements that cannot be verified.

Counts reflect the backend's explicit lists/statuses. Missing metadata and unsupported documents are
labelled not assessed/not reported instead of being presented as zero omissions. The backend report,
field labels, official quotations, citations, readiness summary and limitations are preserved.
No extra administrative requirement is inferred or translated by the bridge.

Dossier validation is informational. It does not certify legal completeness or official approval.
Human verification by the competent administration remains necessary.

## Request payload examples

These examples are schematic; replace the base64 placeholder with bytes from a supported upload.
The production bridge obtains those bytes from Telegram using its existing bounded in-memory download.

Ordinary Form Check (no `mode` field):

```json
{
  "language": "en",
  "file": {
    "filename": "form.pdf",
    "mime_type": "application/pdf",
    "data_b64": "<base64-encoded file>"
  }
}
```

Dossier Validation:

```json
{
  "mode": "dossier",
  "language": "en",
  "file": {
    "filename": "form.pdf",
    "mime_type": "application/pdf",
    "data_b64": "<base64-encoded file>"
  }
}
```

Both use `POST /webhook/assistant`. Deployed workflow 03 routes ordinary files to
`/agents/form-check` and dossier-mode files to `/agents/dossier-check`. The bridge calls neither
backend endpoint directly and duplicates no analysis or orchestration.

## Privacy and errors

Existing PDF/JPEG/PNG signatures, upload byte limits, Telegram download checks, request timeouts,
retries, cancellation, rate-limit handling, message splitting and plain-text output remain in effect.
Uploads are held in memory, never written to temporary or permanent files, and never indexed.
No questions, personal field values, uploaded file contents or field labels are added to logs.
Unsupported forms, unreadable files and malformed upstream replies fail safely. A form that cannot
be read is not described as having empty fields. Every successfully formatted dossier result includes
the informational-only disclaimer, including unsupported-document replies.

## Verification

- Telegram unit suite: **92 passed** (includes the existing 72 and 20 new cases).
- Full unit suite: **247 passed**, 30 integration tests deselected; six existing dependency warnings.
- Live n8n Telegram-adapter integration suite: **13 passed** in 142.60 seconds, including the four
  new PDF/PNG mode-selection cases. Ordinary uploads returned `form_helper`; dossier-mode uploads
  returned `dossier_validator` with official citations, eight missing fields on the blank RNE form,
  and `completeness_certified: false`. Telegram and file download APIs were mocked; requests traversed
  real n8n, FastAPI, official-source retrieval and local form analysis.
  Tests use an official blank RNE form and its PNG rendering, never private identity documents.
- Compose configuration validation passed.
- Only this deployment command was executed:

```powershell
docker compose --profile telegram up -d --no-deps --build telegram-bridge
```

Shared backend, n8n and Qdrant services were not rebuilt or restarted.

## Manual live acceptance, deferred until credentials exist

1. Run `/start`; check that Form Check and Dossier Validation appear together.
2. Select each of the four languages; check prompts and report headings.
3. Select Dossier Validation and upload a supported official blank form, then a supported image.
4. Confirm six distinct categories, source links and the informational/non-certification disclaimer.
5. Select Form Check and upload the same file; verify the ordinary form-helper reply.
6. While dossier mode is selected, send a text question; verify normal question routing.
7. Use New question and /cancel; verify later uploads return to ordinary Form Check.
8. Try an unrelated PDF, malformed upload, unsupported format and oversized file; confirm safe errors.
9. Observe a real Telegram incoming message and bot reply before claiming live Telegram success.

Real Telegram connectivity and real messaging remain **BLOCKED: TOKEN NOT PROVIDED**. No token was
requested and no real Telegram messaging was tested. Existing official-corpus and OCR limitations
still apply; this bridge update does not certify arbitrary forms or handwriting.

Docker verification after rebuilding: bridge **healthy**, restart count **0**, logs confirm
`LIVE_CONNECTIVITY_PENDING`. Shared backend, n8n and Qdrant retained their existing running containers.
No credential-dependent validation was performed.
