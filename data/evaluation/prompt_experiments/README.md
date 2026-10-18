# Prompt before/after experiments (2026-10-18)

Run with `scripts/prompt_experiments.py`. Every call goes through the project's own `OllamaChatClient` and
`PromptLibrary`, one at a time, against the local Ollama on `127.0.0.1:11434`. The models are
`mistral:latest` (LLM role) and `translategemma:4b` (translation role). No backend, n8n, Qdrant or Telegram
component is involved.

- **Real versions** are loaded from `prompts/<name>/<version>.yaml` exactly as committed.
- **Controlled baselines** (`B0`) are labelled as such. They were written on 2026-10-18 for this
  experiment, because the prompt had only one stored version. They are **not** historical prompts. Each
  B0 removes the techniques used by the real prompt (role, language/script guidance, definitions,
  constraints) but keeps the same output format, model and options, so that the comparison is fair.
- **`dialogue_messages.jsonl`** is a **synthetic** set of user declarations (not administrative
  content), written for this experiment. The expected labels are the author's annotations.
- The router experiment uses the existing development set `data/evaluation/eval_set.jsonl` (84 labelled
  questions). It calls the LLM prompt directly. In the running system, the keyword rules answer first and
  the prompt is only a fallback.
- The translation experiment uses the 11 real French checklist scenarios parsed from the official
  Interior Ministry guides (`data/processed/extracted`). Outputs are validated with the production
  validators `_parse_numbered` and `_same_numbers`.

Each experiment writes `<prompt>_results.json`, containing the configuration, every raw output and the
summary metrics.
