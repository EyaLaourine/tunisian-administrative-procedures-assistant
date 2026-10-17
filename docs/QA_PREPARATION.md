# Technical Q&A preparation

All numbers come from `data/evaluation/` (built and run on 2026-10-16) and the report tables.

**Why RAG instead of fine-tuning?**
Every administrative statement must be traceable to an official document (URL, official reference, SHA-256)
and must change when a decree changes. RAG updates by re-ingesting, without retraining. Fine-tuning would
blend facts into the model weights, where they cannot be cited. It is also infeasible to fine-tune a 7B
model on a 4 GB GPU.

**Why n8n?**
The agent chain is visible and editable as a workflow (workflow 03), schedulable (weekly re-ingestion,
workflow 01), and independent of the Python code. Each agent is an HTTP node, so a single step can be
replaced or tested in isolation. Trade-off: two extra HTTP hops per request (small next to LLM time).

**Why multiple agents?**
Different tasks need different guarantees:
- **Routing:** deterministic rules plus an optional LLM call.
- **Retrieval:** no LLM.
- **Checklists:** verbatim quotation, no LLM.
- **Free answers:** an LLM, with validated citations.
- **Forms:** OCR and computer vision.

Separating them keeps the LLM away from the parts where it could invent requirements, fees or deadlines.

**Why Qdrant?**
Payload filtering (procedure category, document type, language), with full provenance stored next to each
vector. It is a single Docker container with persistent storage. Two collections allow the two chunking
strategies to be compared on equal terms.

**Why local Ollama?**
- **Privacy:** questions and identity documents never leave the machine.
- **Cost:** no paid API.
- **Reproducibility:** fixed model tags.

The cost is speed. Mistral 7B runs 40 % on the 4 GB GPU, so free answers take about 20–40 s; the deterministic
paths take well under a second.

**How are hallucinations reduced?**
1. Checklists, fees and deadlines are quoted verbatim from the official structure. Faithfulness of quoted
   items: see report Table 5.
2. LLM answers are rejected if they cite nothing or cite a non-existent passage; the passages are then quoted.
3. Translation is limited to FR→EN and rejected if any line or number changes. FR→AR was withdrawn after it
   changed meanings.
4. Unsupported questions are refused (birth certificates, codes that do not exist, missing RNE checklist).
5. Citations are copied from metadata, never generated.

**How are sources verified?**
An allow-listed registry of official domains and a robots.txt / AI opt-out check run before download.
SHA-256 and HTTP metadata are recorded in the manifest. Official references and dates are copied from the
document itself. Applicability stays `unverified` (publication does not prove a text is in force).

**How are conflicting sources handled?**
The FR and AR passport pages are aligned scenario by scenario. When the stamp-duty amounts differ
(20/60 vs 25/80 TND), both sources are cited and a warning tells the user to confirm with the
administration. The system never picks one silently.

**How is retrieval evaluated?**
84 questions, of which 71 carry labels. Every relevance label is a verbatim evidence span verified
programmatically against the official text, never written by hand. Metrics: Recall@1/3/5, MRR@5, Hit@5 and
latency, on identical questions, routes and k for every configuration. Results by language, script, category
and on a parallel multilingual subset. Limitation: the labels were made by the developers and await human
review, and part of the tuning used the same set.

**What is the role of chunking?**
It decides what one retrievable unit is:
- **Raw dense retrieval:** recursive chunks won (Hit@5 0.817 vs 0.732), because the 95 short structure chunks
  of the RNE table are near-identical.
- **With BM25, fusion and the per-document cap:** structure chunks won (0.873), because one table row is one
  chunk, which exact codes can match.

The checklist builder does not depend on chunk boundaries: it reads the full official section.

**How are uploaded documents protected?**
- Processed in memory only: never written to disk, never logged, never indexed.
- n8n does not store executions of workflow 03.
- Services are bound to 127.0.0.1, and the Telegram bridge needs no inbound port.
- Users are told to send redacted copies. Demos use only blank official forms.

**What are the limitations of multilingual retrieval?**
On the parallel subset:
- FR, EN, AR and Derja in Arabic script all reach Hit@5 1.0.
- Latin-script Derja reaches 0.714. Raw dense retrieval gets 0.0, because Arabizi words match neither script.

The Arabizi map that fixes part of this was compiled after seeing the failures (optimistic estimate).
Official passages are never translated for retrieval. Arabic and Derja users read French originals when no
Arabic version exists.

**What are the current performance bottlenecks?**
- **LLM generation on 4 GB VRAM:** CPU offload and model swapping (embedding model ↔ Mistral ↔ translategemma).
- **Measured retrieval latency:** about 0.4 s per query, including a batched embedding.
- **A host-side artefact found during evaluation:** `localhost` on this Windows host adds 2.1 s per HTTP call
  (IPv6 fallback). Host tools should use 127.0.0.1. Container-to-container calls are not affected.

**Is the Telegram bot verified?**
Only up to authentication, and with a mocked Telegram API that drives the real n8n chain. A live conversation
must be verified on the demo day (the bridge is maintained separately).

## Update 2026-10-16: verifier, independent evaluation, bonus

**Why version prompts? How were iterations evaluated?**
Each version is a file selected by a registry, and every answer records `prompt_ref`, so results are
traceable to a version. Iterations were compared on the same 12 answer-routed development questions, with
the same passages: acceptance, language consistency, evidence span and latency. Example: v3 was not adopted
because it differed by one item and was 7 s slower (`docs/PROMPT_ENGINEERING.md`).

**Why hybrid retrieval?**
Dense BGE-M3 misses exact procedure codes and company types among 95 near-identical table rows. BM25 matches
them. Fusing the raw-query and expanded-query dense lists keeps both specificity and cross-lingual reach.
- Development Hit@5: 0.704 (Phase 2) → 0.873.
- Held-out: 0.750, equal to plain dense retrieval, with a lower MRR. We report this overfitting openly.

**Why does independent evaluation differ from development?**
The fusion parameters, term normalisation and Arabizi map were chosen on development failures. The held-out
and test sets were written after tuning and are never tuned on, and they show smaller gains.

**How are numerical claims validated?**
Each digit-written number in an LLM answer must appear in the passage cited by the same sentence. Source
numbers are parsed from digits and from FR/EN/AR number words ("خمسون ألف" = 50,000). Unsupported sentences
are removed; if nothing cited remains, the answer is refused. Unsupported numbers: 0 on all five sets with the
verifier on (2/85, 1/9, 1/9, 2/19 and 2/7 without it). Limitation: numbers the LLM writes as words are not
checked.

**Citation validity vs factual faithfulness?**
Citation validity means the cited document exists with the same URL and SHA-256 (100 % everywhere).
Faithfulness means the content is actually in the cited text: quoted items are verbatim (1.0) and numbers are
supported (verifier). A valid citation can still accompany an incomplete answer (M11).

**Why is the topic check off?**
It removed the known "carte grise" failure, but on two independent test sets it did not reduce false
acceptance and added false refusals: synonyms like "tarif" vs "redevance", and word forms like "fixe". The
LLM verdict was unstable. It is kept for experiments.

**Which results are independent?**
- **Test set 2** (12, evaluated once).
- **Test set 1** (14; evaluated twice, with two verifier versions).
- **The held-out set** for retrieval. It is not independent for H09, H14 and H17.
- **The development and regression sets** were used for design.

**Main failure cases?**
- **Router:** the LLM fallback refuses answerable questions without keywords (test 2: 5 of 6).
- **Retrieval:** fee-decree questions rank below table rows; Latin-script Derja legal questions.
- **Topic:** subjects named with corpus words ("attestation de travail").
- **Answer completeness:** M11.

**What makes the Dossier Validator innovative? How does it reuse the agents?**
It turns the form check into a readiness report that separates three things:
1. Field status: filled, missing, unreadable, cannot_verify.
2. Official requirements, quoted verbatim from the form's printed instructions and the RNE table.
3. Dossier completeness, which it never certifies.

It reuses the Form-Filling Helper (recognition, field status), the RAG Retriever and Checklist Builder (does an
official supporting-document list exist?), and the existing citations and i18n.

**What does the validator verify, and what can it not?**
- **Verified:** which detected fields look filled or empty; which fields the form itself makes mandatory
  (e-mail, mobile).
- **Not verified:**
  - whether supporting documents are attached;
  - payment of the fee;
  - the signature;
  - whether the values are correct;
  - which RNE procedure applies.

**Why is it not a legal certification tool?**
Only the administration decides. The official sources do not list the RNE supporting documents, and
handwriting and real photographs were not evaluated.

**How does it handle missing official requirements?**
It asks the existing Checklist Builder whether an official document list exists. If none exists, the
requirement is `official_requirement_unavailable` and the summary says that completeness cannot be assessed.
It never builds a list with an LLM.

**How are uploads protected in the validator?**
Same path as the Form-Filling Helper: in memory only. It reports field statuses, never field values; logs
contain counts only (tested); nothing is indexed.

## Final candidate (2026-10-17): likely defence questions

**Is this really a multi-agent system?**
It is an *orchestrated* multi-agent architecture, not an autonomous one. n8n owns the control flow and calls
six specialised agents with typed contracts:
- **Generate text with an LLM:** two agents (grounded answer; FR→EN checklist translation).
- **Uses an LLM only as a fallback classifier:** the router.
- **Deterministic:** retriever, form helper and dossier validator.

No agent plans or negotiates. That is a deliberate choice: in an administrative and legal domain the control
flow must be predictable and auditable. See `docs/MULTI_AGENT_ARCHITECTURE_ASSESSMENT.md`.

**Why not let the LLM answer legal questions?**
Measured, not assumed:
- The generic LLM path contained the official legal passage in 1 of 30 legal questions.
- It fabricated an "Article 16" provision behind a valid citation.
- Prompt versions v2 and v3 did not fix paraphrasing.

The legal path now locates the requested article or table and quotes it verbatim, or refuses if the article
does not exist.

**Your citations were 100 % valid: why was that not enough?**
A citation proves that the document exists, not that the answer says what the document says. The
end-to-end audit found empty RNE answers and a fabricated provision while every citation was valid. Since
then, targeted checks look for the official fact itself in the answer body.

**What does 480/480 mean?**
Every targeted official fact (380 RNE rows with and without dialogue context, 72 guide scenarios, 16 guide
fees, 12 CIN/passport profiles) appears verbatim in the answer. It is **not** an overall accuracy figure:
other question types (free legal questions, form-instruction questions) are evaluated separately, and some
still fail.

**Can two Telegram users see each other's context?**
- **Private chats:** no, one session per chat.
- **Groups:** since the final candidate, one session per (chat, member). Only the numeric user id is used.
- **Lifetime:** sessions expire after 30 minutes and are cleared by `/cancel`.

**What happens if an agent fails?**
Each n8n agent node has an error output that returns a structured 503 naming the failed agent. The bridge
retries, then shows a localised error. An LLM failure in the answer agent falls back to quoting passages.

**What is still not done?**
- Real-handwriting evaluation.
- Human review of the evaluation labels.
- Production deployment of the corrected candidate and a real Telegram acceptance test of it.
- Authentication of the local API (documented, opt-in key implemented).
