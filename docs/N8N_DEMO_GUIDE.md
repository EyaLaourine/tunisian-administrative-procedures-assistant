# Final n8n demonstration guide

The base annotated layout is synchronized and verified; the concise [presentation polish](N8N_PRESENTATION_POLISH.md) is a separate offline proposal awaiting approval. Existing editors are available at [local n8n](http://localhost:5678). Authenticate privately if prompted. Use the three editor links in [architecture](N8N_THREE_WORKFLOW_ARCHITECTURE.md), then **Zoom to Fit**; zoom into sections for readable detail. Do not execute workflow 01 or change publication for presentation.

## Fifteen-minute demonstration

| Time | Demonstration |
|---|---|
| 0–2 min | Explain official-source scope and actual deployment version; n8n orchestrates, backend implements specialized components. |
| 2–4 min | Workflow 01 graph only: acquisition, extraction/chunking/embeddings inside backend; inactive trigger and destructive reindex warning. |
| 4–5 min | Workflow 02 graph: independent dense retrieval API, not invoked by workflow 03. |
| 5–8 min | Workflow 03 graph: document lane vs text lane, router/direct clarification, retrieval, checklist/answer, error responder. Distinguish candidate error branch from live if not yet applied. |
| 8–11 min | Only in approved acceptance window: one multilingual contextual question and official evidence; explain fee conflicts and unsupported refusal. |
| 11–13 min | Only in approved acceptance window: blank public RNE form PDF and dossier report; show informational limitation, not legal completeness. |
| 13–15 min | Security/deployment status, tests actually run, limits, questions. No personal files/credentials on screen. |

## Two-to-three-minute English architecture narration

“This assistant helps users navigate Tunisian administrative procedures using a bounded corpus of official documents. Telegram is the main interface, with HTTP and a local web fallback. The architecture is orchestrated: n8n controls explicit routes, while FastAPI provides specialized services. Some services use local language models; others use deterministic processing.

The first workflow acquires official sources and requests indexing. Document extraction, recursive and structural chunking, BGE-M3 embeddings and Qdrant indexing happen inside the backend. These are explained by annotations, not artificial execution nodes. This workflow stays unpublished during the demonstration because indexing recreates collections.

The second workflow exposes a small, independent retrieval endpoint. It calls the backend's dense retrieval API and returns official passages. The main assistant does not call this workflow internally.

The third workflow receives assistant requests. Uploaded files go to form assistance or dossier validation according to the selected mode. Text goes through the Intent Router. Some requests receive a direct clarification; others retrieve evidence and then produce a checklist or a grounded answer. The reviewed candidate retains explicit, sanitized error responses. Those error branches are not evidence that every service failure has been tested live.

The system uses Mistral for selected language tasks, TranslateGemma for supported translation tasks, and BGE-M3 for embeddings. Retrieval and validation also contain deterministic logic. Legal extraction and several hardening improvements exist in the reviewed backend candidate; we distinguish them from the older production image until a separate deployment is approved.

Official citations make evidence inspectable, but a valid URL alone does not prove an answer correct. Evaluation must check the relevant passage, the user's scenario and numerical claims. A dossier report can identify potential omissions and explicitly unverified requirements. It cannot certify legal completeness or official approval.

Our workflow preparation was checked with structural and mocked security tests. No ingestion, reindexing or unsolicited Telegram messages were used. Live synchronization and credential enforcement require separate, explicit approval and acceptance checks.”

Follow [manual acceptance matrix](N8N_ACCEPTANCE_TESTS.md) for reproducible examples. Do not claim current coverage scores or real Telegram success from this preparation alone.
