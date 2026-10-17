# Final demonstration — 15-minute script

Every demo input below is an item of the verified evaluation set (`data/evaluation/eval_set.jsonl`).
Its expected evidence was checked verbatim against the official documents. "What to point out"
describes behaviour observed in recorded runs (`data/evaluation/agent_results_final.json`). It is not a
promise about the live output: read the live answer and comment on what actually appears.

Live path options:
- **A. Telegram.** Only if the bot token is configured and the Telegram bridge has been tested that day.
  The Telegram bridge is maintained separately; check its status first (`docs/DEMO_CHECKLIST.md`).
- **B. HTTP through n8n.** `scripts/demo_ask.py` sends the same JSON the bridge sends to
  `POST /webhook/assistant` and prints the reply. This exercises n8n and every agent.
- **C. Backup.** See the last section.

| Time | Segment | Content |
|---|---|---|
| 0:00–1:30 | Problem and objectives | Fragmented official information (Ministry of the Interior pages, RNE site, JORT PDFs), FR/AR only, Derja-speaking users. Risk: an LLM inventing fees or documents. Goal: answers quoted from official sources with citations, local processing. |
| 1:30–3:00 | Architecture | Report Fig. 1: Telegram/HTTP → n8n workflow 03 → five FastAPI agents → Qdrant + Ollama. Open the n8n editor (http://localhost:5678) and show workflow 03 with its branches. |
| 3:00–4:30 | Official data | `config/sources.yaml`: approved, excluded (idaraty.tn, robots.txt AI opt-out) and not-found entries with reasons. `data/raw/manifest.json`: URL, SHA-256, retrieval time, `applicability: unverified`. |
| 4:30–5:30 | RAG pipeline | Report Fig. 2: extraction to TextBlocks; structure-aware and recursive chunking; BGE-M3; Qdrant; routed retrieval. |
| 5:30–7:00 | Passport (FR) | **Input P01**: `Quelles pièces fournir pour une première demande de passeport ?` Point out: verbatim "Pièces à fournir" section, scenario title, the FR/AR stamp-duty warning (20/60 vs 25/80 TND), the two official sources. |
| 7:00–8:00 | Multilingual | **Input P04 (Derja)**: `شنوة الأوراق اللازمة باش نجدد الباسبور؟` → the official Arabic page with Derja labels. **Input P02 (English)**: `What documents are needed to renew a Tunisian passport?` → validated FR→EN translation note. Mention the ~20 s latency of the translation path. |
| 8:00–8:45 | Birth certificate | **Input B01**: `Comment obtenir un extrait de naissance ?` → reported as not covered. Explain why: the only source found opts out of AI use in robots.txt. This is a deliberate refusal, not a bug. |
| 8:45–10:00 | RNE | **Input R01**: `Combien coûte l'immatriculation d'une SARL ?` → official table row RNE C 012 (50 TND, thirty-day deadline) and links to the official forms. **Input R34**: `Quelles pièces fournir pour créer une SARL ?` → explicit statement that no official checklist exists in the corpus. |
| 10:00–11:30 | Form analysis | Send the official blank form F-002 (`data/raw/rne-form-f002-legal-entity-registration/*.pdf`). Point out: form recognised, 8 fields listed as empty. Optionally send a scan/photo of a printed blank copy. Use only blank or placeholder-filled forms, never real personal data. |
| 11:30–13:30 | Evaluation | Report Tables 2–4: retrieval metrics by configuration, chunking comparison, answer-quality checks and their failures. |
| 13:30–15:00 | Limitations and conclusion | Not covered: real handwriting tests, live Telegram (unless verified that day), speech input, legal currency of texts. |

## Exact commands (option B)

```bash
.venv/Scripts/python scripts/demo_ask.py "Quelles pièces fournir pour une première demande de passeport ?"
.venv/Scripts/python scripts/demo_ask.py "شنوة الأوراق اللازمة باش نجدد الباسبور؟"
.venv/Scripts/python scripts/demo_ask.py "What documents are needed to renew a Tunisian passport?"
.venv/Scripts/python scripts/demo_ask.py "Comment obtenir un extrait de naissance ?"
.venv/Scripts/python scripts/demo_ask.py "Combien coûte l'immatriculation d'une SARL ?"
.venv/Scripts/python scripts/demo_ask.py "Quelles pièces fournir pour créer une SARL ?"
.venv/Scripts/python scripts/demo_ask.py --file data/raw/rne-form-f002-legal-entity-registration/f68cfaa0a715_RNE-F-002_declation_immatriculation_personne_motale.pdf
```

## Backup strategy (option C)

1. **If Telegram fails:** switch to option B. It runs the same n8n workflow and the same agents.
2. **If n8n fails:** call the agents directly in the order n8n uses:
   - `POST /agents/route`
   - `POST /agents/retrieve`
   - `POST /agents/checklist` or `POST /agents/answer`

   Use the FastAPI docs at http://localhost:8000/docs.
3. **If Docker or Ollama fails:** present the recorded outputs in `data/evaluation/agent_results_final.json` (field
   `response` for each item) and the report tables. Say explicitly that these are **recorded outputs from
   the evaluation run of 2026-10-16**, not live executions.
4. Never present a recorded or simulated response as live.

## Evidence verification (3–4 minutes)

The evidence verifier (`agents/verification.py`) is in the current code. Until the backend container is
rebuilt, demonstrate it with `--local`. This mode calls the same agent endpoints in the order of workflow 03,
in-process, and prints the verification report. Say that it is not going through n8n.

| # | Purpose | Command | What to point out |
|---|---|---|---|
| 1 | Supported question | `.venv/Scripts/python scripts/demo_ask.py --local "Combien coûte l'immatriculation d'une SARL ?"` | Keyword-routed: no extra check needed; verbatim table row RNE C 012 with citation |
| 2 | Question outside the corpus | `.venv/Scripts/python scripts/demo_ask.py --local "Comment renouveler une carte grise ?"` | `verification: topic … missing_terms ['grise']`: the subject word occurs in none of the official documents, so the assistant refuses instead of answering with national-ID evidence (the held-out failure H17) |
| 3 | Unsupported number | `.venv/Scripts/python -m pytest tests/test_verification.py -v -k "invented_figure or supported_figures"` | Scripted answers checked against the real wording of Law 2018-52 art. 55 ("خمسون ألف دينار"): an answer stating "510,000 TND" is refused; "50,000 TND" is accepted. Live, the same question (`--local "What is the penalty for making a false declaration to the National Business Register?"`) was refused in the recorded runs because Mistral produced an unsupported figure. LLM output can vary, so present the scripted test as the reproducible demonstration. |
| 4 | Correct refusal with an explanation | `.venv/Scripts/python scripts/demo_ask.py --local "كيف أجدد رخصة السياقة؟"` | The refusal explains why (no official source for this procedure) and asks the user to contact the administration |

Wording to use: the verifier reduces unsupported answers. It does **not** guarantee legal correctness, and
the official texts' current validity is not verified.

## Final run of show (rubric-aligned, about 15 minutes)

Use the n8n path (`scripts/demo_ask.py "…"`) for features that exist in the deployed backend. Use `--local` or
`--dossier`, which run in-process on the current code, for the evidence verifier and the Dossier Validator
until the backend container is rebuilt. Say which path is used.

| Time | Rubric criterion | What to show | Command / artefact |
|---|---|---|---|
| 0:00–3:00 | Prompt engineering | `prompts/registry.yaml`; grounded_answer v1→v2→v3 table and the v3 non-adoption; FR→AR translation withdrawn ("veuve"); H14 caught by the numerical verifier | `docs/PROMPT_ENGINEERING.md`; `pytest tests/test_verification.py -v -k "invented_figure or supported_figures"` |
| 3:00–7:00 | RAG | Official corpus with provenance (`config/sources.yaml`, `data/raw/manifest.json`); chunking comparison; development vs held-out Hit@5 (overfitting shown openly); a cited checklist with the FR/AR fee warning | `scripts/demo_ask.py "Quelles pièces fournir pour une première demande de passeport ?"`; report Tables 1–3 and 7 |
| 7:00–11:00 | Multi-agent | n8n workflow 03 in the editor; agent table; a real trace (route 5 ms → retrieve ≈ 0.6 s → checklist 6 ms); a Derja question; an unsupported question refused | `docs/traces/trace_checklist_fr.txt`; `scripts/demo_ask.py "شنوة الأوراق اللازمة باش نجدد الباسبور؟"`; `scripts/demo_ask.py "Comment obtenir un extrait de naissance ?"` |
| 11:00–13:00 | Multimodality and bonus | Official blank form F-002 → 8 empty fields; Dossier Validator report: mandatory e-mail and mobile quoted from the form, "completeness cannot be assessed" because no official document list exists | `scripts/demo_ask.py --file data/raw/rne-form-f002-legal-entity-registration/*.pdf`; `scripts/demo_ask.py --dossier --file data/raw/rne-form-f001-natural-person-registration/*.pdf --language ar` |
| 13:00–15:00 | Results and limitations | Test counts; Table 8 (verifier off/on); router fallback limits; no real handwriting tested; Telegram status | `docs/RUBRIC_COVERAGE.md`, report section 8 |

For the `--file` arguments, use the exact file name in the folder (Windows shells do not expand `*`).

## Update: Dossier Validator through n8n (deployed 2026-10-16)

The backend and workflow 03 are now deployed with the latest code. Both upload paths run live through n8n:

| Path | Command | Agent in the response |
|---|---|---|
| Form check (unchanged default) | `.venv/Scripts/python scripts/demo_ask.py --language fr --file data/raw/rne-form-f002-legal-entity-registration/f68cfaa0a715_RNE-F-002_declation_immatriculation_personne_motale.pdf` | `form_helper` |
| Dossier readiness report | `.venv/Scripts/python scripts/demo_ask.py --mode dossier --language fr --file data/raw/rne-form-f001-natural-person-registration/dbfa1f815312_RNE-F-001_declation_immatriculation_personne_physique.pdf` | `dossier_validator` |

**What to point out.**
- The response separates `report.form_fields` (field status) from `report.dossier`, where
  `completeness_certified` is always `false`.
- The mandatory e-mail and mobile number are quoted from the form.
- "Dossier completeness cannot be assessed" appears because no official list of supporting documents exists.

**Telegram.** The bridge sends `"mode": "dossier"` after `/dossier_check` or the Dossier Validation menu button
(see `docs/TELEGRAM_DOSSIER_MODE.md`); plain uploads keep the form check. Live use waits for a bot token.

**Fallback.** `--dossier` runs the same endpoint in-process. `--local` is no longer required, because the
deployed backend has the verifier.
