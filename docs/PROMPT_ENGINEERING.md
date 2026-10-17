# Prompt engineering

Prompts are versioned files in `prompts/<name>/<version>.yaml`, selected by `prompts/registry.yaml`.
Each file declares its model role, options, an optional JSON-output flag, the system prompt and a user
template. Every LLM response records `prompt_ref` (e.g. `grounded_answer@v2`). A version is never edited
in place; `test_every_prompt_version_parses` checks that every version loads.

| Prompt | Active | Versions | Role | Output validation in code |
|---|---|---|---|---|
| `intent_router` | v1 | v1 | Fallback classifier when the keyword rules find no procedure | JSON; category and intent checked against fixed enums |
| `grounded_answer` | **v2** | v1, v2, v3 | Answer only from numbered official passages | At least one citation, no invalid passage number; numbers verified against the cited passages; otherwise the passages are quoted or the answer is refused |
| `translate_items` | v1 (FR→EN only) | v1 | Translate verbatim checklist items | Same numbered lines, same numbers; otherwise the original is shown |
| `evidence_topic` | v1 (topic check off by default) | v1 | Does the evidence describe the asked procedure? | JSON boolean; any error means refusal |

## Design principles

- **Grounding.** The `grounded_answer` rules:
  - "use ONLY the information contained in the numbered official passages";
  - never invent documents, fees, deadlines, offices or conditions;
  - copy amounts, deadlines and article numbers exactly;
  - say so in one sentence when the passages do not contain the answer.
- **Citations.** `[n]` after every factual sentence. The code accepts an answer only if it cites existing
  passages, and renumbers sources per document.
- **Language.** The answer language is passed as `{language_name}`, with Derja mapped to Tunisian Arabic in
  Arabic script. Official document names stay in their original language.
- **Hallucination prevention outside the prompt.** Checklists and RNE fees never go through an LLM: the
  Checklist Builder quotes official sections verbatim. Prompts are used only where no rule can do the job.
- **Unsupported questions.** These are mostly rejected before any generation: by the router rules, the
  answerability gate and unknown-code detection.

## Iterations (all observed during development; measurements in `data/evaluation/`)

| Version | Motivating failure | Change | Measured on the 12 answer-routed development questions | Decision |
|---|---|---|---|---|
| grounded_answer v1 | – | Initial grounded prompt (600 tokens) | Accepted 0.667, language OK 0.917, evidence span 3/11, median 29.2 s | Replaced |
| v2 | An Arabic answer was cut mid-sentence at 600 tokens (Phase 2) | 900 tokens; "reproduce list items faithfully" | Accepted **0.750**, language OK **1.000**, evidence span 1/11, median 26.5 s | **Active** |
| v3 | v2 paraphrased more (evidence span 1/11) | Rule 8: quote the official words before explaining | Accepted 0.750, evidence span 2/11, median 31.7 s (+7 s) | Not adopted: one item of difference, slower |
| translate_items v1, FR→AR | "veuve" (widow) translated as "العوراء" (one-eyed woman); "timbre" as "الطوابق" (floors). Both passed format validation. | Withdrawn rather than re-prompted: Arabic/Derja users get the official text | – | FR→EN only |
| evidence_topic v1 | H17: "carte grise" answered with national-ID evidence | LLM verdict on the topic | Unstable: the same question was judged consistent in one run and inconsistent in another | Kept for EN/Derja experiments; topic check **off** by default |

## Real examples (recorded outputs, development set; `agent_results_hybrid.json`, `agent_results_prompt_v3.json`)

**R29, "What shareholding threshold makes someone a beneficial owner?"** (answer only in Arabic, Government
Decree 2019-54)
- v1: LLM answer rejected; the assistant quoted the Arabic passage verbatim ("نسبة تُساوي أو تفوق 20 %"). The
  answer is grounded but in the wrong language for the user.
- v2: "a person becomes a beneficial owner if they directly or indirectly hold 20% or more of the capital…".
  Correct, in English. The evidence span cannot match verbatim (Arabic source), which is why the
  evidence-span metric is a lower bound.
- v3: same content, but cites "[1, 2a]". The citation parser recognises only `[n]` markers, so such combined
  markers are not validated individually (limitation).

**R27, "When is the trade name reservation certificate issued?"**
- v1, v2 and v3 all answer "on the same day as the request … valid for six months and can be renewed once",
  matching Government Decree 2019-53 art. 3. The versions differ only in wording. This is why v3's verbatim
  rule brought little measurable change.

**M11, "What is the late registration penalty at the RNE?"**
- All versions answer about the 2022 *remission* of penalties (Decree-Law 2022-18) instead of the penalty
  itself (half of the fee per month of delay, Law 2018-52 art. 51). The answers are grounded and cited but
  incomplete: a retrieval/ranking problem that no prompt version fixed.

**H14 (held-out), the unsupported number**
- With v2, Mistral wrote "a fine of up to 510,000 TND" for "خمسون ألف دينار" (50,000). This was not fixable by
  prompting reliably. It is now caught after generation by the numerical verifier, and the answer is refused
  rather than shown.

## Distinguishing the quality dimensions

| Dimension | Mechanism | Metric (development set, final run) |
|---|---|---|
| Grounding quality | Prompt rules + citation validation + numerical verifier | Faithfulness 1.000; unsupported numbers 0/78 |
| Language consistency | `{language_name}`, i18n labels, verbatim quotes exempt | Strict 0.821; assistant-text 0.929 |
| Verbatim quotation | Checklist Builder (no LLM) | Quoted items found verbatim: 1.000 |
| Refusal correctness | Router rules, answerability gate, unknown codes, verifier | False acceptance 0.000; false refusal 0.058 |
| Latency | Prompt length and `num_predict` | Grounded answer median ≈ 25 s (Mistral 7B, 40 % on GPU) |

## Rationale for the current selection

- **grounded_answer v2** has the best acceptance and language consistency at the lowest latency.
- **translate_items FR→EN** is the only direction whose output survived manual inspection.
- **The LLM topic verdict** is too unstable to run by default.

No prompt was tuned on the held-out or test sets.
