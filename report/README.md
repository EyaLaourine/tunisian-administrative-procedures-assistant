# Academic report (LaTeX)

- `main.tex`: the report (A4, 10 pt).
  - **Main report:** Sections 1–8 plus the references, at most 8 pages.
  - **Annex A (prompt library):** starts on a new page after `\appendix` and is outside the page limit.
- `references.bib`: bibliography (BibTeX, `plain` style).
- `figures/*.tex`: TikZ diagrams (architecture, RAG pipeline, n8n workflow 03), included with `\input`.
- `tables/*.tex`: tables.
  - **Generated:** most come from `data/evaluation/*.json` via `scripts/make_report_tables.py`.
  - **Hand-written:** `tables/final_regression.tex` summarises the final replays recorded in
    `docs/FINAL_REGRESSION_RESULTS.md` and `data/evaluation/final_candidate_*`.
- `appendices/prompt_library.tex`: **generated** from the actual prompt files by `scripts/make_prompt_annex.py`.
  Do not edit it by hand.
- `report.pdf` / `report_final.pdf`: the compiled report. `report_final.pdf` was written because `report.pdf`
  was locked by an open viewer during the last build; both come from the same `main.tex`.

## Build

Local (MiKTeX / TeX Live), from the repository root:

```bash
.venv/Scripts/python scripts/make_report_tables.py     # only after a new evaluation
.venv/Scripts/python scripts/make_prompt_annex.py      # after any prompt change
cd report
pdflatex main && bibtex main && pdflatex main && pdflatex main
```

**Overleaf:**
- Upload the whole `report/` folder (`main.tex`, `references.bib`, `figures/`, `tables/`, `appendices/`).
- Set the compiler to pdfLaTeX and the main document to `main.tex`.
- Required packages are all in TeX Live (`fvextra`, `pgfplots`, `tikz`, `tabularx`, `booktabs`).
- No shell escape or external image is needed.

**Arabic script** is not typeset (pdfLaTeX cannot render it without extra packages). Arabic examples are
transliterated or described in English. The prompt files contain no Arabic.

## To complete before submission

- Author names and institution are not recorded in the project files. Add them in the title block of
  `main.tex`.
