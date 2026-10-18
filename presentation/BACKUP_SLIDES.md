# Backup slides (not part of the 20-minute talk)

The backup slides are in `FINAL_PRESENTATION.pptx` after the divider (slide 20). Show them only when a
question needs them. Each one reads its numbers from the evidence files, like the main slides.

| Slide | Title | Use it when asked about | Presenter | Evidence |
|---|---|---|---|---|
| 21 | Security controls and phase-2 activation | authentication, API keys, exposure, why keys are not yet active | any | `backend/main.py`, `backend/agents_api.py`, `docs/SECURITY_PHASE2_ACTIVATION_PLAN.md` |
| 22 | Full retrieval comparison (8 configurations) + Hit@5 per language | "show all configurations", chunking, multilingual retrieval | Member 4 | `retrieval_results_improved.json` (re-run identically on 2026-10-18) |
| 23 | Numeric evidence verifier (off → on) | hallucinated numbers, the H14 case, verification cost | Member 6 | `report/tables/verification.tex` |
| 24 | dialogue_understanding outputs on identical inputs | the details of the prompt iteration, raw vs validated | Member 3 | `prompt_experiments/dialogue_understanding_results.json` |
| 25 | intent_router B0 vs v1 by language | the per-language effect of the router prompt, Derja weakness | Member 3 | `prompt_experiments/intent_router_results.json` |

## Further backup material (documents, not slides)
- **API architecture:** `presentation/DIAGRAM_SPECIFICATIONS.md` §2 and §4 (workflow 03 node list, sequence diagram).
- **More evaluation:** `presentation/RAG_EVALUATION.md`; `data/evaluation/multilingual_eval_results.json`
  (per-question outputs); `data/evaluation/multimodal_eval_results.json`.
- **Technical limitations:** `presentation/QA_PREPARATION.md` §H; report §8.
- **Prompt evidence, every key prompt:** `presentation/PROMPT_ENGINEERING_EVIDENCE.md` (compliance matrix in §4).
