# RAG evaluation (for Section 4 of the talk)

All numbers come from committed files. The summary values of `data/evaluation/retrieval_results_improved.json`
were re-read on 2026-10-18 and match `report/tables/retrieval.tex` exactly. The live re-run result is in §7.

## 1. Corpus

| Item | Value | Source |
|---|---|---|
| Candidate sources in the registry | 18 | `config/sources.yaml` |
| Manifest records | 14 | `data/raw/manifest.json` |
| Indexed documents | **12** (Interior: passport FR, passport AR, national ID FR; RNE: formalities table, F-001, F-002; legal: Law 2018-52 AR, Decree 2022-298 fees FR, Decree-law 2022-18 FR, beneficial-owner decree AR, name-reservation decree AR, Order of 13 Jan 2026 FR) | manifest |
| Excluded, with a recorded reason | passport application-form page and birth-certificate source (robots/AI opt-out); a scanned 2022-298 upload without a text layer; two sources that do not exist | registry |
| Provenance per original | URL, HTTP metadata, retrieval timestamp, SHA-256; originals never overwritten | `ingestion/`, manifest |
| Applicability | `unverified` until a human confirms that a text is in force | registry rule |

## 2. Extraction, chunking, embeddings, store

- **Extraction.** PyMuPDF (PDF) and HTML parsing produce typed `TextBlock`s: heading, paragraph, list item,
  table row, with page numbers. Arabic presentation forms are normalised with NFKC (`rag/extraction.py`).
- **Two chunkers on the same blocks** (`rag/chunking.py`):

| Strategy | Rule | Chunks | Mean chars | Median chars |
|---|---|---|---|---|
| Structure-aware | headings, list sections and table rows kept together; max 1200 chars; heading path prefixed | **272** | 526 | 430 |
| Recursive | 1000 chars, 150 overlap, coarsest separator first | **174** | 867 | 911 |

- **Embeddings:** BGE-M3 (1024-d, multilingual) through Ollama.
- **Store:** Qdrant 1.19, collections `official_docs_structure` (272) and `official_docs_recursive` (174), cosine
  distance, full provenance in the payload. Both counts were confirmed read-only on 2026-10-18.

## 3. Retrieval configuration (production default: `RETRIEVAL_MODE=hybrid`)

1. The Intent Router gives the procedure category, which is used as a **payload filter**.
2. **An RNE code in the question** (e.g. "RNE C 012") bypasses similarity search: the exact table row is read by
   payload scroll.
3. Otherwise **reciprocal rank fusion** (k = 60) of three lists:
   - dense retrieval of the raw query;
   - dense retrieval of a query expanded with fixed bilingual terms for the routed procedure;
   - BM25 over the raw query with deterministic normalisation (company types, Arabizi words).
4. **At most 2 chunks per document** in the top 5.
5. There is no neural reranker (4 GB GPU). The agents then read complete official units (a section, a row, or
   an article located in the text). Citations are copied from the payload, never generated.

Note: workflow 02 (`POST /webhook/retrieve` → backend `/retrieve`) exposes filtered **dense** retrieval only.
The assistant uses the hybrid path through `/agents/retrieve`.

## 4. Test queries and metrics

- **Development set:** 84 questions (34 FR, 26 EN, 11 AR, 13 Derja, 9 of them in Latin script), of which 71
  have verified labels. Each label is an **evidence span** found verbatim in a named official document by
  `scripts/build_eval_set.py`.
- **Held-out set:** 20 questions written after all tuning and evaluated once.
- **Relevant chunk:** from the right document and containing the span, after NFKC normalisation with
  whitespace and diacritics removed.
- **Metrics:**
  - **Recall@k:** the share of evidence groups found in the top k.
  - **Hit@5:** at least one group is found in the top 5.
  - **MRR@5:** the mean reciprocal rank of the first relevant chunk (0 if none in the top 5).
  - **Citation correctness:** the cited URL and SHA-256 exist in the manifest.
  - **Unsupported-answer handling:** the share of unsupported or out-of-scope questions that are refused.

## 5. Results (71 labelled dev questions, k = 5)

| Configuration | Chunks | R@1 | R@3 | R@5 | MRR@5 | Hit@5 |
|---|---|---|---|---|---|---|
| Dense, raw query | structure | 0.465 | 0.676 | 0.718 | 0.575 | 0.732 |
| Dense, raw query | recursive | 0.528 | 0.725 | 0.803 | 0.642 | 0.817 |
| Agent retriever (Phase 2) | structure | 0.493 | 0.648 | 0.697 | 0.577 | 0.704 |
| Agent + term normalisation | structure | 0.507 | 0.662 | 0.711 | 0.591 | 0.718 |
| Hybrid RRF | structure | 0.549 | 0.768 | 0.831 | 0.668 | 0.845 |
| **Hybrid RRF + cap 2 (production)** | **structure** | **0.549** | **0.782** | **0.859** | **0.675** | **0.873** |
| Hybrid RRF + cap 2 | recursive | 0.507 | 0.711 | 0.768 | 0.613 | 0.775 |
| Hybrid RRF + cap 3 | structure | 0.549 | 0.768 | 0.852 | 0.669 | 0.859 |

**Structure vs recursive chunking.**
- With raw dense retrieval, recursive chunks win (0.817 vs 0.732): the 95 near-identical table-row chunks are
  short.
- With BM25 and the cap, structure chunks win (0.873 vs 0.775): one row is one chunk, so exact codes and
  company types select exactly that row.
- **The chunking strategy must be chosen together with the retriever.**

**Multilingual (parallel subset, Hit@5):**

| Query | Dense | Hybrid + cap |
|---|---|---|
| FR | 1.000 | 1.000 |
| EN | 1.000 | 1.000 |
| AR | 0.714 | 1.000 |
| Derja, Arabic script | 0.750 | 1.000 |
| Derja, Latin script | 0.000 | 0.714 |

**Held-out (20).** The hybrid ties dense retrieval on Hit@5 (0.750) and ranks lower on MRR@5 (0.531 vs 0.635).
Part of the development gain was overfitting: the term and Arabizi maps were built after looking at failures.

**Answer-level** (development set, final run):
- citations valid 145/145;
- unsupported-answer rejection 1.000 (after the answerability gate);
- faithfulness of quoted items 1.000;
- unsupported numbers in LLM answers 0/78 with the numeric verifier.

**End-to-end audit** (728 cases through n8n): citation URLs in the manifest 1547/1547, and targeted official
facts present 480/480 in the final candidate.

## 6. Limitations
- Labels were written by the team; human review is pending. The held-out set is small (20).
- Latin-script Derja retrieval is the weakest (0.714 on the parallel subset).
- Fee-decree questions (refunds, payment methods) still lose to RNE table rows; "which form" questions match
  field labels.
- Span-based relevance cannot detect a correct quotation of the wrong provision, so selected cases were
  checked by hand.
- Citation validity was 100 % even when an answer was wrong (the audit found a fabricated provision behind a
  valid citation). **Citation validity is not correctness.**

## 7. Live reproduction (2026-10-18)
See the section "Retrieval reproduction" in `docs/OVERNIGHT_FINALIZATION_REPORT.md`. The same script was run
read-only against the production Qdrant (no writes), with a separate results file.
