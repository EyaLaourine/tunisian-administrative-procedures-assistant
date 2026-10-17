# Academic report (LaTeX)

- `main.tex`: the report (A4, 10 pt, maximum 8 pages).
- `references.bib`: bibliography (BibTeX, `plain` style).
- `figures/*.tex`: TikZ diagrams (architecture, RAG pipeline, n8n agent workflow), included with `\input`.
- `tables/*.tex`: tables and chart data **generated** from `data/evaluation/*.json` by
  `scripts/make_report_tables.py`. Do not edit them by hand; re-run the script after a new evaluation.
- `report.pdf`: the compiled report.

## Build

Local (MiKTeX / TeX Live):

```bash
.venv/Scripts/python scripts/make_report_tables.py   # from the repository root
cd report
pdflatex main && bibtex main && pdflatex main && pdflatex main
```

Overleaf: upload the whole `report/` folder (including `figures/` and `tables/`), set the compiler to
pdfLaTeX and the main document to `main.tex`. No shell escape or external images are needed.

Arabic script is not typeset: pdfLaTeX cannot render it without additional packages. Arabic examples are
described in English in the text.

## To complete before submission

- Author names and institution: not recorded in the project files. Add them in the title block of `main.tex`.
