# Exact annotation changes — offline proposal

Only note content and the listed note geometry change. Colors, executable positions and all functional fields remain exact.

## TnaaIngestIndex1 · Guide: 01 · Triggers

Node ID: `8ce91565-208c-5b53-986e-154fcc3256dd`

```diff
- ## 01 · Triggers
- Manual entry or Monday 03:00 schedule.
- **UNPUBLISHED: schedule is not running.**
- Do not execute during the demonstration.
+ ### 01 · Trigger
+ Manual or scheduled entry point.
+ Inactive: do not execute during the demonstration.
```

## TnaaIngestIndex1 · Guide: 02 · Official acquisition

Node ID: `1cf049dd-a774-52de-aea8-6c37bb5c3ec7`

```diff
- ## 02 · Official acquisition
- **POST /ingestion/run** → FastAPI.
- Registry approval, robots/AI opt-outs, TLS, type validation and SHA-256 provenance/deduplication.
- Returns counts/results; no new download in this review.
+ ### 02 · Official Sources
+ Download approved official documents with provenance checks.
+ Source policies and document validation remain enforced.
```

## TnaaIngestIndex1 · Guide: 03 · Processing and chunks

Node ID: `9d7c3a80-d6b7-5177-82f9-36ffa32b45e5`

```diff
- ## 03 · Processing + two chunkers
- **POST /index/run** → FastAPI.
- PyMuPDF text layer; HTML/table structure; normalization and metadata.
- **Structure-aware** and **recursive** chunks.
- Image-only corpus PDFs are skipped; this ingestion path does not OCR them.
+ ### 03 · Document Processing
+ The backend extracts text and document structure.
+ Structural and recursive chunks prepare the evidence.
```

## TnaaIngestIndex1 · Guide: 04 · Embeddings and Qdrant

Node ID: `235fbff3-4cbd-53c3-9be9-5987ad81a7a9`

```diff
- ## 04 · Inside the indexing request
- Ollama **bge-m3**, 1024 dimensions.
- `official_docs_structure` + `official_docs_recursive`.
- Vectors + document/page/heading/URL/SHA metadata.
- **Indexing recreates both collections.** No separate executable embedding node.
+ ### 04 · Embeddings & Qdrant
+ BGE-M3 embeds chunks into two Qdrant collections.
+ These stages run inside the indexing service.
```

## TnaaIngestIndex1 · Guide: 05 · Runtime summary

Node ID: `ad13f9e5-1f43-54a9-a1ce-4b1952c66dfc`

```diff
- ## 05 · Runtime summary
- `ingestion_counts`, `documents_indexed`, `documents_skipped`, `collection_points`.
- Values come from the run, not historical metrics.
- Failures stop the chain; no dedicated error response node.
+ ### 05 · Run Summary
+ Report ingestion, indexing and collection counts.
+ No live run is required to explain the pipeline.
```

## TnaaIngestIndex1 · Guide: Safety and legend

Node ID: `15e3219f-1ceb-5869-9c30-9c8351860ee5`

```diff
- ### Safety gate
- Admin endpoints require **X-Admin-Key** on the hardened backend; without a configured admin key they fail closed. Credential setup and release require approval. No ingestion, indexing, schedule activation or Qdrant write is authorized by this diagram.
- ### Legend · annotations do not execute
- **Icons + wires:** real n8n execution. **Notes:** explanations only.
- Blue = input/answer (closest available to teal); purple = routing; green = knowledge; gold = PDF/processing; red = safety; gray = infrastructure.
- LLM components and deterministic services run **inside FastAPI**; none plans or negotiates autonomously.
+ ### Pipeline Safety
+ Backend stages: extraction → chunking → embeddings → indexing.
+ Indexing recreates collections. Keep this workflow inactive.
```

Geometry: `[-80, 610]`, height `220` → `[-80, 610]`, height `180`.

## TnaaRetrieveApi1 · Guide: 01 · Retrieval request

Node ID: `79c43674-f411-5539-99ac-0a1f2e9fee58`

```diff
- ## 01 · POST /webhook/retrieve
- Independent retrieval API.
- Body: `query`, `strategy`, `top_k`, `filters`, `min_score`.
- This webhook does **not** invoke Intent Router or conversation memory.
+ ### 01 · Retrieval Request
+ POST /webhook/retrieve accepts a retrieval query.
+ This entry point is independent of the assistant workflow.
```

## TnaaRetrieveApi1 · Guide: 02 · Dense retrieval backend

Node ID: `420a9704-ecaa-5b2a-ab1c-4997bd4b63ee`

```diff
- ## 02 · POST /retrieve
- FastAPI → Ollama **bge-m3** → filtered Qdrant cosine search.
- Select structure or recursive collection; filter metadata and minimum score.
- **This endpoint is dense retrieval, not workflow 03’s routed hybrid retriever.**
- X-Agent-Key is required only when backend enforcement is enabled.
+ ### 02 · RAG Retriever
+ BGE-M3 embeddings drive filtered, dense Qdrant search.
+ This endpoint returns passages; it does not generate answers.
```

## TnaaRetrieveApi1 · Guide: 03 · Evidence response

Node ID: `56af7f04-c365-5a33-9326-e9eac85b3a95`

```diff
- ## 03 · Return passages
- List of `RetrievedPassage` items: `score`, `text`, `chunk_id`, `citation`.
- Citation: document, URL/SHA, language, page/heading, applicability metadata.
- No answer generation. HTTP failures currently stop execution; safe error output is a separate future change.
+ ### 03 · Grounded Evidence
+ Return ranked passages with official-source citations.
+ Evidence supports downstream answers and manual review.
```

## TnaaRetrieveApi1 · Guide: Relationship and legend

Node ID: `60fd5d2c-a2eb-52ce-a5a2-0271b850d1b1`

```diff
- ### Separate entry points
- Workflow 03 calls **/agents/retrieve directly**, not this workflow. Both access the same project Qdrant collections; their retrieval contracts and ranking paths differ. No Execute Workflow node or workflow-to-workflow arrow is implemented.
- ### Legend · annotations do not execute
- **Icons + wires:** real n8n execution. **Notes:** explanations only.
- Blue = input/answer (closest available to teal); purple = routing; green = knowledge; gold = PDF/processing; red = safety; gray = infrastructure.
- LLM components and deterministic services run **inside FastAPI**; none plans or negotiates autonomously.
+ ### Retrieval Boundary
+ Workflow 03 calls its backend retrieval agent directly.
+ This API uses dense retrieval; it does not orchestrate dialogue.
```

Geometry: `[-80, 540]`, height `280` → `[-80, 540]`, height `200`.

## TnaaAssistant01 · Guide: 01 · User input

Node ID: `3e071f8a-2801-5bc8-9ed2-248dc4166d50`

```diff
- ## 01 · Telegram / HTTP
- External bridge → **POST /webhook/assistant**.
- Text/language/public context OR PDF/image. Chat/user IDs stay in the bridge; not sent as a session ID to n8n.
- **File attached? true → document path; false → Intent Router.**
+ ### 01 · Request Entry
+ Telegram / HTTP requests enter the assistant webhook.
+ File detection separates document and text requests.
```

## TnaaAssistant01 · Guide: 02 · PDF and dossier

Node ID: `db801a9a-ffe7-5405-8e10-93636f7d4ccb`

```diff
- ## 02 · Document assistance · deterministic FastAPI services
- **Dossier mode?** true → `/agents/dossier-check`; false → `/agents/form-check`.
- Typed uploads → PyMuPDF / Tesseract ara+fra, OpenCV alignment and ink checks; official RNE F-001 / F-002 templates. Dossier adds supported requirements and unverifiable items.
- Fields are not legal approval; no private upload indexing or field values in logs.
+ ### 02 · Document Processing
+ PDF/image uploads → Form Helper or Dossier Validator.
+ Only the competent administration can approve a dossier.
```

## TnaaAssistant01 · Guide: 03 · Orchestration

Node ID: `0ec226ae-52ff-5d69-b29a-9ffaaba8aa96`

```diff
- ## 03 · Intent routing
- `/agents/route`: rules first; Mistral fallback.
- Language, category, public facts → next agent.
- **Direct reply? true → response; false → RAG.**
+ ### 03 · Intent Routing
+ Select the procedure and response path.
+ Return clarification directly when needed.
```

## TnaaAssistant01 · Guide: Direct response

Node ID: `cefc3dd6-c4d3-5910-ab67-e9a9cb464eef`

```diff
- ### Direct response
- Clarification, greeting or supported refusal.
+ ### Direct Response
+ Greeting, clarification or supported refusal.
```

## TnaaAssistant01 · Guide: 04 · Routed retrieval

Node ID: `100058aa-ba37-553a-897e-9e061f33cd74`

```diff
- ## 04 · POST /agents/retrieve
- Typed query + route → passages.
- Hybrid raw/expanded BGE-M3 + BM25, RRF fusion and per-document cap. No cross-encoder reranker.
- **Reviewed backend candidate adds exact RNE-code lookup; not in the current production image.**
- Checklist route? true → checklist; false → answer.
+ ### 04 · Evidence Retrieval
+ Retrieve official passages for the selected procedure.
+ Pass evidence to checklist or grounded-answer services.
```

## TnaaAssistant01 · Guide: 05 · Response composition

Node ID: `73ef7bc1-9c82-5de8-8746-d8b6eb3804b6`

```diff
- ## 05 · Specialised composition
- `/agents/checklist`: official sections/rows; optional validated FR→EN translation.
- `/agents/answer`: gated Mistral answer + citation/number checks or source fallback. **Reviewed backend candidate adds deterministic legal extraction.**
- ComposeRequest → typed result → original response nodes.
+ ### 05 · Specialized Agents
+ Checklist Builder extracts source-backed requirements.
+ Grounded Answer composes a cited response.
```

## TnaaAssistant01 · Guide: Legal evidence

Node ID: `8e530284-59f4-5d5c-ba7d-5af612a60424`

```diff
- ### Candidate legal service · NOT DEPLOYED
- Reviewed source/candidate backend: exact articles/tables, source excerpts and limits handling. Production image has no legal_evidence module yet.
- No legal-validity or dossier-approval certification. Citation-index and numeric checks do **not** prove semantic entailment. Topic checking is configuration-dependent (default off).
+ ### Scope & Limitations
+ Assistance does not certify legal completeness.
+ Enhanced legal extraction is not deployed in the running backend.
```

Geometry: `[1100, 1060]`, height `350` → `[1100, 1060]`, height `240`.

## TnaaAssistant01 · Guide: 06 · Errors and safety

Node ID: `6303eb59-daf3-5e46-9096-4ab56c09906b`

```diff
- ## 06 · Shared backend-error response
- Six HTTP error outputs → **503 agent_unavailable** + failed_agent; four-language notice. Retains Claude’s repository candidate.
- This is a **functional addition versus live 16-node workflow**, not a visual-only change. No raw backend error body is returned. Authentication/validation errors also map to 503; review that limitation.
+ ### 06 · Error Handling
+ Six backend error outputs share a sanitized HTTP 503 response.
+ Authentication and validation failures may also appear as 503.
```

## TnaaAssistant01 · Guide: External infrastructure

Node ID: `ba9d7eb6-b8c6-5050-9f32-a243195ded16`

```diff
- ### External / backend-internal · not additional n8n agents
- Telegram long polling and in-memory 30-minute sessions: private chat or group-member isolation in the **candidate bridge**. Production image must be checked separately.
- FastAPI on `backend:8000`; project Qdrant on `qdrant:6333`; local Ollama through `host.docker.internal:11434`.
- No n8n session database; no workflow 02 call; successful/error/manual execution payload retention remains disabled.
+ ### Backend Services
+ n8n orchestrates; FastAPI runs specialized services.
+ Local models and Qdrant support inference and retrieval.
```

Geometry: `[-80, 840]`, height `320` → `[-80, 840]`, height `240`.

## TnaaAssistant01 · Guide: Legend and review boundary

Node ID: `a46f7939-572f-54b9-8ca9-cf460c75a6d1`

```diff
- ### Legend · annotations do not execute
- **Icons + wires:** real n8n execution. **Notes:** explanations only.
- Blue = input/answer (closest available to teal); purple = routing; green = knowledge; gold = PDF/processing; red = safety; gray = infrastructure.
- LLM components and deterministic services run **inside FastAPI**; none plans or negotiates autonomously.
-
- **Draft for review only.** Live n8n remains unchanged. API keys are configured via Header Auth credentials in a separately coordinated release; no values are stored here.
+ ### Reading the Diagram
+ Colored panels identify stages; wires show execution.
+ Services are orchestrated, without autonomous planning.
```

Geometry: `[-80, 1220]`, height `300` → `[-80, 1140]`, height `240`.
