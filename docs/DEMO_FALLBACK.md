# Demonstration fallback (no Telegram needed)

**Telegram is the primary interface** of the assistant (`telegram_bridge/`; activation steps are in
`docs/TELEGRAM_ACTIVATION.md`). This local web page is a **fallback** for demonstrations when no bot token
or Telegram connectivity is available. It does not replace or change the bridge.

Both interfaces call the same n8n workflow 03 webhook with the same request format: `{text, language?}`
for questions, and `{file, language?, mode?: "dossier"}` for uploads. Any backend change therefore
applies to both. The orchestration runs in **n8n workflow 03**. Every answer shown comes from the real n8n
workflow, the five agents, Qdrant and Ollama. Nothing is mocked.

## Architecture

```
Browser (http://127.0.0.1:8090)
   │  page: demo_ui/static/index.html (vanilla HTML/JS, no external assets)
   ▼
demo_ui/app.py (FastAPI, local proxy)     validates text / language / file type / size / base64; adds no logic
   │  POST {text, language?}  or  {file:{filename,mime_type,data_b64}, language?, mode?="dossier"}
   ▼
n8n workflow 03  POST /webhook/assistant  (active, 16 nodes)
   ├─ text   → Intent Router → RAG Retriever → Checklist Builder | Grounded Answer (+ evidence verifier)
   ├─ file   → Form-Filling Helper                      (default, unchanged)
   └─ file + mode=dossier → Dossier Validator           (Smart Administrative Dossier Validator)
   ▼
FastAPI backend (Docker) ── Qdrant (Docker) ── Ollama (host GPU)
```

- **Why FastAPI + vanilla JS.** FastAPI and uvicorn are already project dependencies, so nothing new is
  installed. The page has no CDN or framework, so it loads without internet.
- **Why a proxy.** It validates requests before n8n, performs real health checks for the status badges, and
  keeps internal URLs out of the browser.
- **Privacy.**
  - Uploads are read in the browser and forwarded once; nothing is stored, and the proxy logs no request
    content.
  - The page keeps no history after a reload and holds no secrets.
  - The "RNE F-001 / F-002" buttons load the official **blank** forms from `data/raw/` through a fixed
    allow-list.

**Offline capability.** The page, proxy, n8n, backend, Qdrant and Ollama all run locally, with models
already pulled. No step needs internet. Source links in answers point to the official websites and need
internet to *open*, but they are not needed for the demo itself.

## Launch (Windows PowerShell, repository root)

1. Check that the required services are running:
   ```powershell
   docker compose ps                       # qdrant, backend, n8n: healthy
   ollama list                             # bge-m3, mistral:latest, translategemma:4b
   ```
2. Start the interface (leave this window open):
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\start_demo_ui.ps1
   # equivalent: .venv\Scripts\python.exe -m uvicorn demo_ui.app:app --host 127.0.0.1 --port 8090
   ```
3. Open **http://127.0.0.1:8090**. The badges at the top right must show "n8n: available" and
   "Backend: available (Qdrant ✓, Ollama ✓)". They are refreshed from real health checks every 30 s.

| URL | Purpose |
|---|---|
| http://127.0.0.1:8090 | Demo interface |
| http://127.0.0.1:8090/api/status | Real health of n8n and the backend (JSON) |
| http://127.0.0.1:5678 | n8n editor (show workflow 03) |
| http://127.0.0.1:8000/docs | Backend API (agents) |

## Verified scenarios (run 2026-10-16 with `scripts/demo_scenarios.py` through the proxy to live n8n; 8/8 passed)

Raw results are in `docs/demo_fallback/scenarios.json`. Full answer texts are in `docs/demo_fallback/outputs/`.
Times are measured end to end, with models already loaded.

| # | Exact input | Expected behaviour | Observed | Sources | Time | Screenshot |
|---|---|---|---|---|---|---|
| S1 | `Quelles pièces fournir pour une première demande de passeport ?` (eval P01) | Verbatim official checklist, FR/AR fee warning, citations | Checklist Builder; "Pièces à fournir" quoted; warning 20/60 vs 25/80 TND | services.interieur.gov.tn/wap/fr/docs/demarches/02.html (+ /ar/) | 0.6 s | `screenshots/02_french_checklist.png` |
| S2 | `What documents are needed to renew a Tunisian passport?` (P02) | English checklist (validated FR→EN translation) with citations | Checklist Builder; translated items; citations to both pages | same | 25.1 s (translation model) | – |
| S3a | `شنوة الأوراق اللازمة باش نجدد الباسبور؟` (P04) | Derja detected; official Arabic page | Derja; official Arabic page with Derja labels. **Note:** this run selected the "residents abroad" variant (see limitations) | same | 2.6 s | – |
| S3b | `chnowa el wra9 eli lezmin bech nejjedd el passbor?` (P05) | Latin-script Derja detected; passport checklist | Derja; Arabic page, "residents in Tunisia" variant | same | 0.5 s | `screenshots/05_derja_latin.png` |
| S4 | `Comment obtenir un extrait de naissance ?` (B01) | Safe refusal: procedure not covered | Intent Router: "Cette procédure n'est pas encore couverte…" | – (no source invented) | 0.3 s | `screenshots/06_unsupported_refusal.png` |
| S5 | Official blank RNE F-001, Form check | Form recognised, 7 empty fields | Form-Filling Helper; recognised; 7 missing | registre-entreprises.tn/…/RNE-F-001_….pdf | 0.5 s | `screenshots/04_form_check.png` (F-002) |
| S6 | Same form, Dossier validation | Readiness report; completeness never certified | 7 missing; e-mail and mobile mandatory (quoted); supporting-document list unavailable → completeness cannot be assessed | form PDF + home.registre-entreprises.tn/formalites/ | 0.5 s | `screenshots/03_dossier_validation.png` |
| S7 (optional) | `What is the penalty for making a false declaration to the National Business Register?` (RN1 = H14) | Unsupported figure refused | Grounded Answer refused: "I could not verify the figures…" (the model's figure was not in Law 2018-52 art. 55) | – | 20.0 s | – |

S7 depends on what the LLM generates. If the model happens to produce a supported answer, it is shown with
its citation instead. The reproducible version is
`.venv\Scripts\python.exe -m pytest tests\test_verification.py -v -k "invented_figure or supported_figures"`.

Screenshots were captured with headless Edge from the running interface: `docs/demo_fallback/screenshots/`.
In headless captures the per-message time reads "0.0 s" (virtual clock). Real browsers show the real time.
**No video was recorded.** To record one, use Windows Game Bar (`Win + Alt + R`) on the browser window while
running S1 → S7.

## In-browser presentation flow (about 6 minutes)

1. **Status.** Point at the two live status badges.
2. **S1.** Click "FR · Passport first application"; show the verbatim list, the FR/AR warning and the clickable
   official sources.
3. **Derja.** Click "Derja (Latin) · passbor"; show that the reply is in Arabic script, read right to left.
4. **Refusal.** Click "FR · Uncovered procedure"; show the explicit refusal.
5. **Form check.** Click **RNE F-001** with "Form check" selected.
6. **Dossier validation.** Select **Dossier validation** and click **RNE F-001** again. Show the field table,
   the official requirements with their quotes, "not verified by this tool", and "completeness never
   certified".
7. **Orchestration.** Open the n8n editor and show the "Dossier mode?" branch that handled step 6.

Suggested wording: *"Telegram is the primary interface; the bridge is deployed and tested, and is waiting
only for a bot token. The assistant itself is the n8n-orchestrated multi-agent workflow you are seeing.
This page sends exactly the requests the Telegram bridge sends."*

## CLI fallback (if the web page fails)

These were verified in PowerShell on 2026-10-16, against the live n8n webhook unless noted:

```powershell
$f1 = "data\raw\rne-form-f001-natural-person-registration\dbfa1f815312_RNE-F-001_declation_immatriculation_personne_physique.pdf"
.venv\Scripts\python.exe scripts\demo_ask.py "Combien coûte l'immatriculation d'une SARL ?"   # text via n8n
.venv\Scripts\python.exe scripts\demo_ask.py --file $f1 --language fr                        # form check via n8n
.venv\Scripts\python.exe scripts\demo_ask.py --mode dossier --file $f1 --language fr         # dossier via n8n
# In-process (bypasses n8n; use if n8n is down). Point to 127.0.0.1 to avoid the 2 s localhost delay:
$env:QDRANT_URL="http://127.0.0.1:6343"; $env:OLLAMA_URL="http://127.0.0.1:11434"
.venv\Scripts\python.exe scripts\demo_ask.py --local "Comment obtenir un extrait de naissance ?"
.venv\Scripts\python.exe scripts\demo_ask.py --dossier --file $f1 --language en
```

All scenarios at once: `.venv\Scripts\python.exe scripts\demo_scenarios.py`, which needs the interface to
be running.

## Emergency recovery

**Health checks (no side effects).**
```powershell
docker compose ps
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health | Select-Object -Expand Content
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5678/healthz | Select-Object -Expand StatusCode
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags | Select-Object -Expand StatusCode
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8090/api/status | Select-Object -Expand Content
```

Restart only the component that is down. Never run `docker compose down -v`: it would delete the vectors and
the n8n data.

| Failure | Symptom | Recovery |
|---|---|---|
| Web interface | Page does not load / port busy | Re-run `scripts\start_demo_ui.ps1` (it frees port 8090). Otherwise use the CLI commands above. |
| n8n | Badge "n8n: unavailable", HTTP 502 "workflow is not reachable" | `docker compose restart n8n` (about 30 s), then check the badge. While down, use `demo_ask.py --local` / `--dossier` (in-process, bypasses n8n). |
| n8n webhook returns 404 | Workflow inactive | `docker compose exec -e N8N_RUNNERS_BROKER_PORT=5690 n8n n8n publish:workflow --id=TnaaAssistant01`, then `docker compose restart n8n` (Git Bash: prefix `MSYS_NO_PATHCONV=1`) |
| Backend | Badge "Backend: unavailable", answers fail | `docker compose restart backend` (no rebuild). If the image is broken, see the rollback in `docs/TEST_RESULTS.md` (image `tunisian-admin-assistant-backend:before-rebuild`). |
| Qdrant | `/health` shows `"qdrant": false` | `docker compose restart qdrant`; the vectors are on the `qdrant_data` volume and survive restarts |
| Ollama | `/health` shows `"ollama": false`, or LLM answers time out | Start the Ollama app or run `ollama serve`; check `ollama list`. Retrieval needs Ollama (embedding model `bge-m3`), so text questions and the official-requirement part of dossier validation fail while it is down. The form check (S5) does not use Ollama. |
| Slow first answer | First LLM call takes 10–40 s | Normal model loading on a 4 GB GPU. Warm up with S1 and S2 before presenting. |
| Docker Desktop stopped | Nothing responds | Start Docker Desktop, wait for "Engine running", then `docker compose up -d` (same images, no rebuild) |
| Everything fails | – | Show the recorded outputs in `docs/demo_fallback/outputs/` and the screenshots, labelled as **recorded on 2026-10-16**, never as live |

## Known limitations

- **S3a.** The Arabic-script Derja question selected the "residents abroad" passport scenario in this run:
  no "abroad" hint was detected, but the passage for the residents-in-Tunisia variant was not among the
  retrieved candidates. The quoted text is official and cited, but it is the wrong variant for most users.
  This is a known retrieval and scenario-selection limitation; agents were not changed for the demo.
- **Labels.** Upload responses do not carry a `route`, so the message footer shows only the agent and time.
- **Interface language.** The interface labels are in English. Answers follow the user's language.
- **Telegram.** Not live yet: no bot token. The bridge is deployed in `LIVE_CONNECTIVITY_PENDING` mode
  and already supports every feature shown here, including dossier validation (`/dossier_check`).
  This was verified by 92 unit tests and 13 credential-free tests that go through the live n8n.
