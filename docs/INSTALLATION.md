# Windows installation guide

This guide initializes a **new local installation**, not production. Commands are PowerShell, from the repository root. Repository: https://github.com/EyaLaourine/tunisian-administrative-procedures-assistant. The repository is private: the owner must invite the professor, who must authenticate with their own GitHub account before cloning.

## 1. Prerequisites

Mandatory: Git; Python 3.11 with the `py` launcher; Docker Desktop in Linux-container mode with Compose v2; native Ollama. Allow enough disk/RAM/VRAM for models and containers. No universal hardware minimum has been measured; CPU inference is slower. Internet is needed for packages/models and Telegram. A Telegram account/token is optional until real bot activation.

```powershell
git clone --branch release/github-ready https://github.com/EyaLaourine/tunisian-administrative-procedures-assistant.git tunisian-admin-assistant
Set-Location tunisian-admin-assistant
py -3.11 --version
docker version
docker compose version
ollama --version
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e ".[dev]"
```

Virtual-environment activation is optional when using explicit executable paths.

## 2. Models

Run native Ollama once; do not launch a competing server.

```powershell
ollama pull bge-m3
ollama pull mistral:latest
ollama pull translategemma:4b
ollama list
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

BGE-M3 produces 1024-dimensional embeddings; Mistral generates grounded answers; TranslateGemma translates checklist items FR-to-EN. Arabic/Derja also use official text and deterministic processing; universal translation quality is not claimed. Record model digests for exact reproduction. Containers use `host.docker.internal:11434`. The optional `ollama-docker` profile is unnecessary for this path.

## 3. Configuration

```powershell
Copy-Item .env.example .env
notepad .env
```

Replace `N8N_ENCRYPTION_KEY` with a privately generated long random secret. Preserve it for the lifetime of the n8n volume. Never share tokens in chat or reports.

| Variables | Purpose |
|---|---|
| `APP_ENV`, `LOG_LEVEL` | Runtime environment/logging |
| `DATA_DIR`, `SOURCES_REGISTRY` | Host data and registry paths; Compose supplies container paths |
| `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION_PREFIX` | Host vector connection, optional key, namespace |
| `QDRANT_HOST_PORT`, `BACKEND_HOST_PORT`, `N8N_HOST_PORT` | Loopback ports: 6343, 8000, 5678 |
| `OLLAMA_URL`, `OLLAMA_URL_FOR_CONTAINERS` | Host and container model-server URLs |
| `EMBEDDING_MODEL`, `EMBEDDING_DIM`, `LLM_MODEL` | Embedding and generation configuration |
| `TRANSLATION_MODEL`, `LLM_TIMEOUT_SECONDS`, `INTENT_LLM_FALLBACK`, `RETRIEVAL_MIN_SCORE` | Local model/routing overrides; Compose uses code defaults |
| `HTTP_USER_AGENT`, `HTTP_TIMEOUT_SECONDS`, `MAX_DOWNLOAD_BYTES`, `DEFAULT_CRAWL_DELAY_SECONDS` | Source acquisition settings |
| `MAX_UPLOAD_BYTES` | Upload limit, default 10 MiB |
| `N8N_ENCRYPTION_KEY`, `GENERIC_TIMEZONE` | Required n8n secret and timezone |
| `TELEGRAM_BOT_TOKEN`, `ASSISTANT_WEBHOOK_URL` | Optional bot token and host-run bridge destination |
| `ADMIN_API_KEY` | Enables privileged endpoints; empty disables them |
| `AGENT_API_KEY` | Optional backend authentication; n8n must send matching headers |
| `ASSISTANT_WEBHOOK_KEY` | Optional bridge header; configure n8n webhook authentication first |

Optional commented settings cover retrieval mode/diversity, evidence checks, OCR languages, request size, prompts and TLS paths. Exact defaults: `backend/settings.py`. **Compose forwards only variables listed in its service environment sections.** An unforwarded `.env` value does not override the container; use a reviewed Compose override if necessary.

Initially leave agent/webhook keys empty unless matching n8n authentication is configured. Services bind to loopback; do not expose unauthenticated endpoints publicly. `.env` is excluded from Git and Docker contexts.

## 4. Offline corpus reconstruction

```powershell
.venv\Scripts\python scripts/build_processed_corpus.py
```

This reads tracked official originals and writes ignored `data/processed/` extraction/chunk files. No downloading, embedding or Qdrant writes occur. Expected: **14 documents, 286 structural chunks, 186 recursive chunks**. One image-only decree is skipped. Historical production has **12 indexed documents, 272/174 points**; CIN/passport additions explain the fresh-index difference. Fifteen manifest records are not fifteen indexed documents.

## 5. Start the new stack

Verify ports are free. Compose has a fixed project name and bridge container name: do not run this alongside production without a reviewed isolation override. A different checkout alone does not isolate Docker resources.

```powershell
docker compose config --quiet
docker compose up -d --build
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:5678/healthz
docker compose exec backend tesseract --list-langs
```

The backend image installs Tesseract with French/Arabic packs. Native OCR tests additionally need Tesseract on PATH with `fra` and `ara` data. The public Sectigo intermediate in `config/certs/` repairs an incomplete official-server TLS chain; it is not a secret. Never disable TLS verification or bypass source policies.

## 6. Initial Qdrant indexing — NEW EMPTY INSTALLATION ONLY

`/index/run` **recreates collections**. First inspect the target:

```powershell
Invoke-RestMethod http://127.0.0.1:6343/collections
```

If valuable collections exist, STOP. On a new empty instance only, privately set a temporary `ADMIN_API_KEY` in `.env`, then load it into the new backend:

```powershell
docker compose up -d --no-deps backend
$adminSecret = Read-Host 'Temporary admin key' -AsSecureString
$adminPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($adminSecret)
try {
    $adminPlain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($adminPointer)
    $indexResult = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/index/run -Headers @{'X-Admin-Key'=$adminPlain} -TimeoutSec 1800
    $indexResult.collection_points
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($adminPointer)
    Remove-Variable adminPlain,adminSecret -ErrorAction SilentlyContinue
}
```

Expect 286/186 points for this snapshot. Remove the temporary admin key from `.env` and recreate only this new backend again. No ingestion/download is necessary. Workflow 01 must stay inactive and unexecuted.

## 7. Import and publish workflows — fresh n8n database only

Open `http://localhost:5678`, create the local owner account privately, then initialize:

```powershell
docker compose exec n8n n8n import:workflow --separate --input=/workflows
docker compose exec -e N8N_RUNNERS_BROKER_PORT=5690 n8n n8n publish:workflow --id=TnaaRetrieveApi1
docker compose exec -e N8N_RUNNERS_BROKER_PORT=5690 n8n n8n publish:workflow --id=TnaaAssistant01
docker compose restart n8n
```

The restart loads publication/webhook registration in this new installation. These initial-import commands are NOT the safe update procedure for existing live workflows. Existing synchronization needs backups, authenticated API updates and version/state verification.

Verify in the native editor:
- `TnaaIngestIndex1`: inactive, 5 executable nodes and 6 notes; never execute during installation.
- `TnaaRetrieveApi1`: published, 3 executable nodes and 4 notes; `/webhook/retrieve`.
- `TnaaAssistant01`: published, 17 executable nodes and 10 notes; `/webhook/assistant`.

HTTP nodes use `http://backend:8000` within Docker. Host clients use loopback ports. No real credential is embedded in the exports; API/owner credentials differ from webhook authentication.

## 8. HTTP checks and optional Telegram activation

```powershell
$question = @{text='Quels documents pour renouveler mon passeport ?';language='fr'} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5678/webhook/assistant -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($question)) -TimeoutSec 600
```

A clarification about residence may be appropriate. Check supporting sources, not one fixed wording. Upload JSON has `file` with `filename`, `mime_type`, `data_b64`, plus `language`. Dossier requests add `mode: "dossier"`; ordinary Form Check omits mode.

For a real bot, contact official verified `@BotFather`, send `/newbot`, choose a display name and available username ending in `bot`. Perform login/verification yourself. Enter the issued token only in private `.env`. Use a dedicated test bot, never a token already polled by production.

```powershell
docker compose --profile telegram up -d --no-deps --build telegram-bridge
docker compose ps
```

Without a token the bridge waits in `LIVE_CONNECTIVITY_PENDING`. Health does not prove delivery. Manually test `/start`, `/help`, `/language`, contextual questions, `/form_check`, `/dossier_check`, PDF/image uploads, refusal and `/cancel`. Do not share unsanitized logs. See [Telegram activation](TELEGRAM_ACTIVATION.md).

## 9. Automated and end-to-end testing

```powershell
.venv\Scripts\python -m pytest -m "not integration" -q
# Dedicated initialized test installation using the expected ports only:
.venv\Scripts\python -m pytest -m integration -q
```

Some integration modules/scripts hard-code localhost:5678/8000/6343. Environment overrides alone do not isolate them. Never run them beside production without inspecting destinations. Native OCR tests may skip without Tesseract. End-to-end acceptance includes the HTTP check and actual manual Telegram exchanges; do not claim the latter from unit tests.

## 10. Troubleshooting and safe shutdown

| Problem | Resolution |
|---|---|
| Missing encryption key | Set it privately; preserve keys already associated with a volume |
| Port/container-name conflict | Stop setup; do not remove unknown containers |
| Ollama unavailable/model missing | Check host server, container reachability and `ollama list` |
| Missing extraction/checklists | Run the offline builder in this checkout |
| Empty Qdrant | Confirm new empty instance before indexing |
| Webhook 404 | Verify publication, production webhook path and registration after startup |
| HTTP 503 | Check upstream availability; some workflow errors deliberately map to 503 |
| Index HTTP 403 | Admin endpoint is disabled without a configured key |
| OCR refusal | Use a clearer supported test form; do not lower thresholds blindly |
| Telegram 409 | Another poller uses the token; stop the test poller, not production |

```powershell
docker compose --profile telegram stop
docker compose --profile telegram start
```

Verify project ownership before lifecycle commands. Do not use `down -v`, volume prune or collection deletion for routine shutdown. Preserve private configuration and encryption keys; back up volumes before upgrades. Keep uploads, backups and credential exports out of Git.
