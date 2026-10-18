# Live demo script (slide 16, about 90 s, presented by Member 6)

**Status on 2026-10-18 (overnight):** no Telegram message was sent and no screenshot of a Telegram chat
exists. The four interactions below were verified **through the candidate n8n webhook** (final-n8n →
final-candidate). The behaviour column quotes what was observed in
`data/evaluation/multilingual_eval_results.json` and `data/evaluation/multimodal_eval_results.json`.

**Before the talk, decide which stack you demo** (see the action plan in `docs/OVERNIGHT_FINALIZATION_REPORT.md`):
- **If the candidate has been deployed to production** (with approval), demo on Telegram.
- **If not**, production still runs the older backend, which lacks the RNE and legal fixes. In that case demo
  through the candidate stack with `presentation/demo_client.py`, and say so openly. Do not present the
  production bot as the evaluated system.

## Preparation (T−30 min)
1. Close other GPU users (a second backend stack makes the LLM paths 10–200× slower).
2. Warm up the models once with a neutral question on each path (checklist, RNE row, form check), so that the
   first live request does not pay the model-load time.
3. Open these tabs:
   - n8n → workflow 03 → **Executions** tab (saved execution data is off, so only status and timing are
     visible; this is the intended privacy setting);
   - Telegram desktop with the bot chat, cleared;
   - a terminal at the repository root;
   - the file `data/evaluation/multilingual_eval_results.json`, as the fallback.
4. Have the blank official form ready: `data/raw/rne-form-f001-natural-person-registration/*.pdf`. Also have a
   phone photo of the **blank** printout. Never use a filled form with real personal data.

## The four interactions

| # | Channel action | Exact input | Expected path | Expected characteristics (observed on the candidate) | Budget |
|---|---|---|---|---|---|
| 1 | Telegram text (FR) | `Quels documents pour renouveler mon passeport ? J'habite en Tunisie.` | Router → Retriever → **Checklist Builder** | Official list quoted verbatim from the Interior passport guide, a sources footer with the official URL, the applicability disclaimer | ≈0.2–1 s |
| 2 | Same chat, follow-up | `Et combien ça coûte ?` | Router (context kept) → Checklist Builder, fee section | Fee section including "timbre"; FR/AR stamp-duty discrepancy warning if present in the rendered sections | ≈0.2–1 s |
| 3 | Telegram text (Derja, Latin script) | `9adech el ma3loum mta3 RNE C 012?` | Router (code detected) → exact payload lookup → Checklist/RNE row | The official row RNE C 012 quoted, with its fee and deadline; header in the user's language | <1 s |
| 4 | `/form_check`, then the photo of the blank F-001 | (photo) | Form-Filling Helper (OCR + homography + ink) | "RNE F-001" recognised, 7 fields reported empty, a reminder that this is not an official approval | ≈2.5 s |

Narrate while the bot answers (the slide-16 notes in `SPEAKER_NOTES.md`). After interaction 1, switch to n8n
Executions for about 5 s to show the successful run of workflow 03.

## Slow-response contingency
- **No answer after 10 s on interactions 1–3:** say "the local model is busy; here is the recorded run", and
  open the fallback JSON at the matching case: `FU-fr`, `RNE-derja-latin`, `A`-part `R01`.
- **No answer after 10 s on interaction 4:** show `multimodal_eval_results.json` case `M05` (blank F-001 PNG:
  recognised, 7 empty, 2.42 s).
- **Never** demo a generated legal or LLM answer live (20–70 s). If asked, show case R29 in
  `agent_results_hybrid.json` (prompt comparison) and `multilingual_eval_results.json`.

## Genuine recorded-result fallback
- `data/evaluation/multilingual_eval_results.json`: every request and its response start, the agent, and the
  latency (run on 2026-10-18 through the candidate n8n).
- `data/evaluation/multimodal_eval_results.json`: 13 upload cases.
- `data/evaluation/final_candidate_defect_probes.json` and the candidate defect probes (16/16).
- The n8n editor screenshots (`presentation/assets/n8n_workflow_0{1,2,3}.png`) are real.

## Manual actions needed (cannot be done overnight)
- Capture real Telegram screenshots **after** deployment, or on the candidate stack, using a test account.
  Crop out names.
- Decide on the demo stack (production after approval, or candidate) and rehearse twice with a timer.
