# Telegram activation guide

Telegram is the **primary** user interface. The local web page (`docs/DEMO_FALLBACK.md`) is only a
fallback for when no bot token or Telegram connectivity is available.

## Current status (verified 2026-10-16)

| Item | Status | Evidence |
|---|---|---|
| Bridge code includes dossier validation | PASS | `contracts.py` (`mode: "dossier"`, upload only), `ui.py` (`/dossier_check`, menu button, 4 languages), `dossier.py`, `bridge.py` |
| Running container = current source | PASS | SHA-256 of all 5 `telegram_bridge/*.py` files and of the shared `backend/settings.py` and `backend/logging_setup.py` are identical on the host and in the container. Image `tunisian-admin-assistant-telegram` `bb4f10f68906`, built 2026-10-16 17:58 UTC. |
| Bridge mode | `LIVE_CONNECTIVITY_PENDING` | Log: `TELEGRAM_BOT_TOKEN is not set`; `TELEGRAM_BOT_TOKEN=` is empty in `.env`. Status "healthy" here means only that the idle process responds. |
| Unit tests (Telegram and n8n mocked) | PASS, 92/92 | `tests/test_telegram_bridge.py` |
| Credential-free integration tests (Telegram mocked, **real** n8n, agents, Qdrant, Ollama) | PASS, 13/13 | `tests/test_telegram_integration.py`: FR/EN/AR/Derja checklists; PDF/PNG/JPEG/photo form check; PDF/PNG form check vs. dossier mode |
| Real Telegram connectivity (`getMe`, polling) | **NOT TESTED**: no token | – |
| Real message/reply exchange | **NOT TESTED**: no token | – |

**Telegram is not live** until the last two rows pass with a real bot.

## What the bridge sends to n8n

The bridge sends the same request format as the web fallback, to the same workflow 03 webhook
(`http://n8n:5678/webhook/assistant` inside Docker):

| User action | Payload |
|---|---|
| Text question | `{"text": "...", "language"?: "en"|"fr"|"ar"|"derja"}` |
| Upload after `/form_check` (or with no mode selected) | `{"file": {"filename", "mime_type", "data_b64"}, "language"?, "caption"?}` |
| Upload after `/dossier_check` | same as above, plus `"mode": "dossier"` |

The response must contain a non-empty `text`. The bridge rejects a dossier report with
`completeness_certified` other than `false`. Any change to the backend, agents or workflow must keep
this contract. Run both Telegram test files after any such change (see below).

## Activation, once you have the token (Windows PowerShell, repository root)

The stack (qdrant, backend, n8n and host Ollama) is assumed to be running already. Only the bridge is
recreated. No other service is rebuilt or restarted.

1. **Create the bot.** In Telegram, open the verified https://t.me/BotFather, send `/newbot`, and choose a
   name and a username ending in `bot`. Copy the token. Do not paste it into chats, screenshots, commands,
   commit messages or source files.

2. **Store it privately.** Edit only the existing empty line in `.env`:
   ```powershell
   notepad .env        # set:  TELEGRAM_BOT_TOKEN=<token>   (no quotes, no spaces), then save
   ```
   Check the format without displaying the token. The command prints only `True` or `False`:
   ```powershell
   Select-String -Path .env -Pattern '^TELEGRAM_BOT_TOKEN=\d+:[A-Za-z0-9_-]{30,}\s*$' -Quiet
   ```

3. **Recreate only the bridge.** `restart` does not reload `.env`; `up` does:
   ```powershell
   docker compose --profile telegram up -d --no-deps telegram-bridge
   ```
   The current image already contains the latest bridge code. Add `--build` only if `telegram_bridge/`
   has changed since 2026-10-16 17:58 UTC.

4. **Verify authentication.** The bridge calls `getMe`, `setMyCommands` and `deleteWebhook` at startup:
   ```powershell
   docker compose --profile telegram ps telegram-bridge
   docker compose logs --tail 20 telegram-bridge | Select-String "telegram_bridge_started|stopped|LIVE_CONNECTIVITY|poll_failed"
   ```

   | Log line | Meaning |
   |---|---|
   | `telegram_bridge_started` | Token accepted; long polling is running. |
   | `Telegram bridge stopped: TelegramAPIError` (repeating, container restarting) | Token rejected or Telegram unreachable. Check the `.env` line, then repeat step 3. |
   | `Telegram bridge stopped: PollingConflict` | Another process is polling with the same token. Stop it; run only one poller. |
   | `LIVE_CONNECTIVITY_PENDING` | The token was not picked up. Check `.env` and use `up`, not `restart`. |

   The bridge silences `httpx`/`httpcore` logs and prints only exception types, so the token never
   appears in the logs. Never run `docker compose config` without `--quiet`, and never print the container
   environment.

5. **Real end-to-end validation** (the "Live acceptance checklist" below). Record the date, the message
   type and the observed reply. Never record the token or personal documents.

**Return to pending mode:** clear the value (`TELEGRAM_BOT_TOKEN=`) and repeat step 3.

**Fresh machine:** follow the README setup, then run `docker compose --profile telegram up -d --build`.

## Credential-free checks (run after any relevant change)

```powershell
.venv\Scripts\python.exe -m pytest tests\test_telegram_bridge.py -q        # Telegram + n8n mocked
.venv\Scripts\python.exe -m pytest tests\test_telegram_integration.py -q   # Telegram mocked, real n8n/agents
```

These tests prove the bridge logic and its compatibility with the live workflow. They do **not** prove
Telegram connectivity. The integration tests use the official blank RNE forms, not personal documents.
They call the production handlers directly, so they never contact Telegram and never compete with a
running poller.

## Live acceptance checklist (needs the token)

Mark Telegram live only after these checks pass with a real bot.

1. **`/start`.** Check the welcome message, disclaimer and main menu (procedures, language, form check,
   dossier validation).
2. **Commands.** Check that the command picker lists all 12 commands: start, help, language, procedures,
   passport, birth_certificate, business, checklist, form_check, dossier_check, privacy, cancel.
3. **Language.** Select English, French, Arabic and Derja in turn; the choice must persist. Ask
   `chnowa el wra9 eli lezmin bech nejjedd el passbor?`. Expect an Arabic official checklist with
   citations; official text keeps its original wording.
4. **Administrative questions.**
   - French: `Quelles pièces fournir pour une première demande de passeport ?`. Expect the verbatim list,
     the FR/AR fee warning and interieur.gov.tn links.
   - English: `What documents are needed to renew a Tunisian passport?`. Expect a translated checklist
     (about 25 s).
   - Uncovered: `Comment obtenir un extrait de naissance ?`. Expect an explicit "not covered" reply.
5. **Form check.** Run `/form_check`, then send the official blank RNE F-001 PDF. Expect "recognised" and
   7 missing fields. Repeat with a PNG/JPEG export and with a Telegram photo.
6. **Dossier validation.** Run `/dossier_check`, then send the same PDF. Expect:
   - filled / missing / unreadable / cannot-verify counts;
   - officially supported requirements, with citations;
   - requirements that cannot be verified;
   - the non-certification disclaimer.

   Then send a text question and confirm it is answered normally (text never carries `mode`). Run
   `/form_check` and confirm that uploads return to the form check.
7. **Rejections.** Send a ZIP, a file over 10 MB and a renamed non-PDF. Each must be rejected with a helpful
   message.
8. **Cancel and privacy.**
   - Run `/cancel` during a long request; no late answer must arrive.
   - New question clears the procedure context but keeps the language.
   - `/privacy`, then `/cancel`, clears the preferences.
9. **Long answers.** Check that messages are split within Telegram limits and that navigation appears on the
   last message only.
10. **Restart.** Run `docker compose --profile telegram up -d --no-deps --force-recreate telegram-bridge`.
    Commands must be re-registered and polling must resume.
11. **Record the evidence.** Record one real incoming message and the bot's reply, without the token or any
    personal data. Then mark connectivity and conversation PASS in `docs/TELEGRAM_REPORT.md`.

## Form-analysis limits

- **Corpus coverage.** The backend recognises only forms in its official corpus (RNE F-001, F-002). The
  passport application form is not in the corpus.
- **No certification.** Recognition, empty-field detection and dossier validation do not certify
  legibility, truthfulness, correct completion, legal completeness or approval. The dossier report always
  carries `completeness_certified: false`.
- **Human review.** Handwriting and low-quality photos have not been evaluated; uncertain scans need human
  review.
