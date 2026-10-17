# Live demonstration checklist

## The day before
- [ ] `docker compose ps`: qdrant, backend and n8n are `healthy`. Do not restart services that another
      developer is using without coordinating first.
- [ ] `curl http://localhost:8000/health` → `"status":"ok"`.
- [ ] `ollama list` shows `bge-m3`, `mistral:latest` and `translategemma:4b`.
- [ ] Workflow 03 is published: `.venv/Scripts/python scripts/demo_ask.py "bonjour"` returns the greeting.
- [ ] Run every command of `docs/DEMO_SCRIPT.md` once (this also loads the models into memory).
- [ ] `.venv/Scripts/python -m pytest -q -m "not integration"` passes.
- [ ] `report/report.pdf` opens and is 8 pages or fewer.
- [ ] Telegram (optional): bridge running, bot token set in `.env`, one real message answered.
      If this has not been verified that day, use option B of the demo script and say so.

- [ ] `pytest -q -m "not integration"` passes; `pytest tests/test_dossier_validator.py tests/test_verification.py` passes.
- [ ] Bonus: `.venv/Scripts/python scripts/demo_ask.py --dossier --file <F-001 or F-002 pdf> --language fr` prints a readiness report.
- [ ] Know which path each demo uses: n8n (deployed, older backend) vs `--local` / `--dossier` (current code, in-process).
- [ ] Topic check is OFF by default (`EVIDENCE_TOPIC_CHECK=false`); the numerical verifier is ON.

## 10 minutes before
- [ ] Close GPU-heavy applications: with 4 GB of VRAM, the models already share the GPU with the CPU.
- [ ] Warm up: run the P01 and P02 commands once (the first LLM call loads the model in 5–11 s).
- [ ] Open: n8n editor (workflow 03), http://localhost:8000/docs, `config/sources.yaml`, `report/report.pdf`.
- [ ] Prepare a terminal in the repository with `.venv` available.
- [ ] Use only the official blank forms in `data/raw/` for the form demo. Never use real personal documents.

## Fallbacks
| Failure | Action |
|---|---|
| Telegram does not answer | Use `scripts/demo_ask.py` (same n8n workflow) |
| n8n down | Call `/agents/route`, `/agents/retrieve`, `/agents/checklist` from http://localhost:8000/docs |
| An LLM path is too slow | Show the deterministic paths (FR/Derja checklists, RNE fees: about 0.2–0.4 s once models are loaded); explain the CPU offload |
| Docker or Ollama down | Present the recorded outputs in `data/evaluation/agent_results_final.json`, labelled as recorded |
