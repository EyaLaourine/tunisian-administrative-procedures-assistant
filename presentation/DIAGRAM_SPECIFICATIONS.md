# Diagram specifications

Every diagram below was derived from the code and the committed workflow files on branch
`overnight/finalization` (base `be787ca`). The **source of truth** is named under each diagram. The editable
PowerPoint versions are drawn with native shapes in `FINAL_PRESENTATION.pptx` (slides 4, 5, 6, 12, 14, 15).

Colour code (see `VISUAL_DESIGN_GUIDE.md`):
- navy: orchestration;
- teal: deterministic service;
- amber: LLM-powered step;
- grey: stores and model servers;
- red: error path.

---

## 1. Overall architecture

Sources: `docker-compose.yml`, `telegram_bridge/bridge.py`, `backend/main.py`, `backend/agents_api.py`.

```mermaid
flowchart LR
  U[Citizen on Telegram] -->|long polling| B[Telegram bridge<br/>python, no inbound port]
  W[Local web page / CLI] --> N
  B -->|POST /webhook/assistant<br/>text, language, context, upload| N[n8n 2.41.3<br/>workflow 03]
  N -->|HTTP/JSON| A[FastAPI backend<br/>/agents/*]
  A --> Q[(Qdrant 1.19<br/>official_docs_structure 272<br/>official_docs_recursive 174)]
  A --> O[(Ollama 0.40.4 on host<br/>bge-m3, mistral 7B, translategemma 4B)]
  A --> C[(Extracted corpus<br/>data/processed + manifest)]
  I[n8n workflow 01<br/>ingest + index, inactive] -.->|admin key required| A
  R[n8n workflow 02<br/>POST /webhook/retrieve] --> A
```

Notes for the slide:
- All published ports are bound to `127.0.0.1`.
- The backend reaches Ollama through `host.docker.internal`, and Ollama listens on loopback only.
- Nothing leaves the machine. There are no paid APIs.

## 2. n8n orchestration (workflow 03, 17 executable nodes)

Source: `workflows/03_assistant_multi_agent.json`, which is identical to the live published version
`af6ad259` as verified on 2026-10-18.

```mermaid
flowchart TD
  WH[POST /webhook/assistant] --> F{File attached?}
  F -->|yes| D{Dossier mode?}
  D -->|yes| DV[Dossier Validator<br/>/agents/dossier-check]
  D -->|no| FH[Form-Filling Helper<br/>/agents/form-check]
  F -->|no| IR[Intent Router<br/>/agents/route]
  IR --> DR{Direct reply?}
  DR -->|yes| R1[Respond: direct reply]
  DR -->|no| RR[RAG Retriever<br/>/agents/retrieve]
  RR --> CR{Checklist route?}
  CR -->|yes| CB[Checklist Builder<br/>/agents/checklist]
  CR -->|no| GA[Grounded Answer<br/>/agents/answer]
  CB --> R2[Respond: checklist]
  GA --> R3[Respond: answer]
  FH --> R4[Respond: form check]
  DV --> R5[Respond: dossier check]
  IR -. error .-> E[Respond: agent error 503]
  RR -. error .-> E
  CB -. error .-> E
  GA -. error .-> E
  FH -. error .-> E
  DV -. error .-> E
```

- **Workflow 01** (5 nodes, inactive): Manual trigger / Weekly refresh → `POST /ingestion/run` →
  `POST /index/run` → Run summary.
- **Workflow 02** (3 nodes, published): `POST /webhook/retrieve` → `POST /retrieve` → Return passages.

## 3. RAG pipeline

Sources: `ingestion/`, `rag/extraction.py`, `rag/chunking.py`, `rag/hybrid.py`, `agents/retriever.py`,
`backend/settings.py`.

```mermaid
flowchart LR
  S[config/sources.yaml<br/>18 candidate sources] --> DL[Downloader<br/>robots.txt + AI opt-out + TLS]
  DL --> RAW[data/raw<br/>originals + SHA-256 manifest<br/>12 indexed]
  RAW --> EX[Extraction<br/>PyMuPDF / HTML -> typed TextBlocks]
  EX --> CS[Structure-aware chunker<br/>max 1200 chars, heading path]
  EX --> CRc[Recursive chunker<br/>1000 chars, overlap 150]
  CS --> EMB[BGE-M3 1024-d]
  CRc --> EMB
  EMB --> QD[(Qdrant: 272 + 174 points)]
  Qy[Query + route] --> CODE{RNE code in query?}
  CODE -->|yes| SC[Exact payload scroll<br/>table row by key]
  CODE -->|no| H[Hybrid: dense raw + dense expanded + BM25<br/>RRF k=60, category filter]
  H --> CAP[Max 2 chunks per document in top 5]
  SC --> OUT[Passages + citation payload]
  CAP --> OUT
```

## 4. Multi-agent sequence (text question)

Source: `workflows/03_assistant_multi_agent.json`, `backend/agents_api.py`, `agents/*`.

```mermaid
sequenceDiagram
  participant T as Telegram bridge
  participant N as n8n (wf 03)
  participant R as Intent Router
  participant V as RAG Retriever
  participant C as Checklist Builder
  participant G as Grounded Answer
  T->>N: {text, language, context}
  N->>R: /agents/route
  R-->>N: RouteDecision {language, intent, category, next_agent, reply?, context}
  alt reply present (greeting, clarification, limits)
    N-->>T: direct reply + context
  else retrieval needed
    N->>V: /agents/retrieve {query, route}
    V-->>N: passages (hybrid or exact code)
    alt next_agent = checklist
      N->>C: /agents/checklist {query, route, passages}
      C-->>N: verbatim official sections (+ validated FR->EN translation)
    else next_agent = answer
      N->>G: /agents/answer {query, route, passages}
      G-->>N: legal-article extract OR verified LLM answer OR refusal
    end
    N-->>T: text + citations + updated context
  end
```

LLM use, from the implementation:
- **Router:** the LLM (`intent_router@v1`) is used only when no keyword rule matches.
- **Dialogue facts:** `dialogue_understanding@v3` is used only without a rule cue.
- **Checklist Builder:** the LLM is used only for FR→EN translation (`translate_items@v1`).
- **Grounded Answer:** `grounded_answer@v2` generates, then the citations and numbers are verified.
- **Retriever, Form Helper and Dossier Validator** are deterministic.

## 5. Multimodal processing

Sources: `agents/form_helper.py`, `agents/dossier_validator.py`.

```mermaid
flowchart TD
  UP[Upload: PDF / PNG / JPEG / Telegram photo] --> VAL{Type, signature,<br/>size <= 10 MB}
  VAL -->|invalid| ERR[Safe error message]
  VAL --> PDF{Digital PDF with text layer?}
  PDF -->|yes| GEO[Words + geometry<br/>vs blank-form template]
  PDF -->|no / image| DSK[Deskew] --> OCR[Tesseract ara+fra] --> HOM[RANSAC homography<br/>to blank form via anchor words]
  HOM --> INK[Ink in each field band<br/>vs blank form]
  GEO --> ST[Field statuses: filled / empty / unreadable / cannot_verify]
  INK --> ST
  ST --> FHr[Form-Filling Helper reply]
  ST --> DV[Dossier Validator: field status + official requirements<br/>quoted verbatim; completeness never certified]
```

Field templates come from the official blank forms F-001 (7 fields) and F-002 (8 fields). Uploads are
processed in memory and never indexed.
