# Technical report update: summary of changes (18 October 2026)

**Previous version:** `report/main.tex` at commit `f9d5018`, describing release candidate `rc-20261018b`. It is
archived unchanged in `report/archive/2026-10-18_before_phaseG_update/` (`main.tex`, `main.pdf`,
`report_final.pdf` and both previous annex sources).

**New version:** the same LaTeX source, restructured to the eight required sections:
1. introduction and requirements;
2. architecture and tools;
3. models;
4. RAG;
5. agents;
6. evaluation;
7. security;
8. limitations and conclusion.

The main report is 7 pages including references; the annexes start on page 8.

## Major corrections

| Before | After | Evidence |
|---|---|---|
| "Fully local assistant"; "no data leaves the machine" | Model inference, retrieval and storage are local. Telegram transport and acquisition of official sources need the Internet, and messages transit Telegram's servers. | Architecture; Telegram Bot API |
| "12 indexed official documents" used as the corpus size | Four counts kept apart: 19 registry entries; 15 stored originals in the manifest; 12 indexed documents (272/174 chunks); 4 form templates, of which the 2 Interior forms are not indexed | E11 |
| Production "still runs the previous images"; the passport application form is "uncovered" | Deployed release `rc-20261018-g` (commit `3d84557`); CIN and passport application forms recognised; 4 supported form templates | E1, E2 |
| Abstract: "orchestrates six specialised agents" (the body already said "orchestrated, not autonomous") | Consistent throughout. Components classified from code: n8n orchestration; rule-first router with three LLM fallbacks; deterministic retriever, checklist, form and dossier services; one LLM-driven, verified answer path. Explicitly not an autonomous multi-agent system. | Table 4; code |
| Prompt annex missing `language_identification` | Generator extended. All 6 families and 10 versions, each with file path, status (registry-selected / historical / not adopted / disabled), component, input variables, expected output, constraints and test evidence. | Annex A; `scripts/make_prompt_annex.py` |
| Security controls listed as implemented | Each control has its production status. Admin endpoints fail closed (no key set). Agent key, webhook key and Qdrant key are **not enabled**. Containers are non-root but have no read-only root filesystem. WF02 execution storage is not verified. | Table 6; E11 |
| "n8n keeps no executions" | Only workflow 03 is configured to save no execution data; workflow 02 uses n8n defaults (not verified) | E11 |
| "Telegram acceptance verified live for text questions" | The only recorded manual session is the owner's Phase E session (6 defects, all fixed in F+G). Manual testing of the deployed release is **pending**. | E6, E1 |
| Isolated, candidate and production results mixed | Table 5 gives the release, environment, suite size and evidence id of every result. Production checks are stated as HTTP with Telegram mocked, and suites are not summed. | Table 5 |
| Model choice partly argued as the "strongest" model | Rationale only: hardware, licence and language coverage. No comparative benchmark was run. | Section 3 |
| — | New: Phase F+G production results, Interior form field roles and scan results, OCR limitations, evidence index (Annex B) | E2, E5 |

## Content removed for length (still available in the archive and in `docs/`)

- **Removed tables:** prompt iteration (`tables/prompts.tex`), numeric verifier (`tables/verification.tex`) and
  full development/held-out (`tables/heldout.tex`). Their key numbers are in the text and in Table 5, and the
  prompt iterations are in Annex C.
- **Removed:** the multilingual Hit@5 bar chart and the residual-defect and latency paragraphs. Latency is cited
  once (E13).

## Facts that could not be verified

- Whether n8n stores workflow 02 executions: the API key is not scoped to read executions (403).
- Byte identity of the stored Interior forms with the files on `services.interieur.gov.tn`: automated retrieval
  is disallowed by `robots.txt`.
- How many Mistral layers are offloaded to the GPU (the previous report stated about 40 %). This was not
  re-measured; the report now only states that the 4.07 GiB weights exceed the 4 GB of VRAM.
- The 728-case replay, retrieval benchmark and answer-level metrics were not re-run on `rc-20261018-g`; the
  report labels them with their own release and date.
- Author names and institution are not recorded in the project files (placeholder comment in `main.tex`).
