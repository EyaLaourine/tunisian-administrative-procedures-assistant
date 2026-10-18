# Speaker notes: complete spoken script (six members)

The target pace is 135–140 words per minute, so about 450 words fit in 3 min 20 s. Member 6's script is shorter
because about 90 s of their time is the live demo. Word counts are given per member at the end. Every number
in this script appears on the slide or in its source file.

---

## Member 1: Introduction and Use Case (slides 1–3, 3:20)

### Slide 1: Title
Good morning. We are presenting the Tunisian Administrative Procedures Assistant: a local, source-grounded,
multi-agent system that answers questions about Tunisian administrative procedures in French, English, Arabic and
Tunisian Derja. I will introduce the problem and our objectives. My colleagues will then walk you through the
architecture, the prompt engineering, the retrieval, the agents, the multimodal part, a live demonstration, and
our results.

### Slide 2: The problem
Why this use case? Consider a citizen who wants to renew a passport or register a small company.
- **The information is fragmented.** The Ministry of the Interior publishes procedure guides in French and in
  Arabic. The National Business Register, the RNE, publishes a table of ninety-five procedures with fees and
  legal deadlines. The laws and decrees behind them are PDF files from the Official Journal.
- **There is a language gap.** The official text is in French or Arabic, but many people write in Derja, often
  in Latin script with digits. For example: "9adech ya5ou wa9t el passbor?", meaning "how long does a passport
  take?".
- **The sources are not even consistent.** The French and Arabic passport pages state different stamp duties:
  twenty and sixty dinars on one, twenty-five and eighty on the other.

A general chatbot would answer all of this fluently, and that is exactly the risk. An invented fee, a missing
document or a wrong deadline costs a citizen a trip to an office, time and money.

### Slide 3: Objectives and value
So we set five objectives:
1. Answer only from verifiable official documents, with citations.
2. Refuse, or ask a clarifying question, when the documents cannot answer.
3. Support four languages without ever altering the official text.
4. Check official forms and dossiers for missing information, without pretending to certify them.
5. Run everything on one laptop with a four-gigabyte GPU: no paid API, and no data leaves the machine.

Our scope is passports, the national identity card, and business registration at the RNE, including its legal
texts and the two official registration forms.
- **One exclusion is deliberate.** We wanted to cover birth certificates, but the only official source opts out
  of AI use in its robots file. We respected that, and the assistant says that this procedure is not covered.

The value is traceability. Every statement can be followed back to an official document with its address and
checksum. The system is also free, private, and usable in the language people actually write in.

Member 2 will now show you how the system is built.

---

## Member 2: System Architecture and Automation Workflow (slides 4–6, 3:20)

### Slide 4: Architecture
Everything you see here runs locally, behind the loopback address.
1. **The Telegram bridge.** A citizen writes to our Telegram bot. The bridge uses long polling: it pulls
   messages from Telegram, so the machine needs no public address and no open port.
2. **n8n.** The bridge sends the message, its language and a small conversation context to a webhook in n8n,
   our orchestrator.
3. **The FastAPI backend.** n8n calls six agent endpoints in the backend.
4. **Qdrant**, our vector database, holds two collections of official chunks: 272 and 174.
5. **Ollama** runs our three models on the host GPU: BGE-M3 for embeddings, Mistral 7B for the language
   tasks, and TranslateGemma for French-to-English translation.

A local web page and a command-line client use the same webhook as fallbacks. All ports are bound to
127.0.0.1, and uploaded documents are processed in memory and never indexed.

### Slide 5: Three n8n workflows
These are real screenshots of our three workflows in the n8n editor.
- **Workflow 01** downloads the official documents and rebuilds both indexes. It is deliberately inactive and
  calls privileged backend endpoints, so it cannot run by accident.
- **Workflow 02** is a small retrieval API: a webhook, one call to the retriever, and the passages returned
  with their sources.
- **Workflow 03** is the assistant itself: seventeen executable nodes. The coloured frames are sticky notes that
  document each stage. Every agent call has an error output that ends in a single sanitised error reply.

### Slide 6: One request end to end
Let me follow one request.
1. The webhook first checks whether a file is attached. Uploads go to the Form-Filling Helper, or to the
   Dossier Validator in dossier mode.
2. Text goes to the Intent Router. It detects the language, the procedure and the intent, using rules first and
   the language model only as a fallback.
3. If the router can answer directly, with a greeting, a clarifying question or a limits notice, n8n replies at
   once.
4. Otherwise the RAG Retriever finds the evidence, and n8n branches. Lists of required documents and fees go
   to the Checklist Builder, which quotes the official text. Other questions go to the Grounded Answer agent.

The latencies here are measured.
- **Deterministic paths are fast:** an RNE row in 0.08 seconds, a French checklist in 0.19, a PDF form check in
  0.16.
- **Language-model paths are slow** on our GPU: an English checklist needs translation and takes about 17
  seconds; a generated answer takes 20 to 70 seconds.

That difference shaped the whole design, as Member 3 will explain with the prompts.

---

## Member 3: Prompt Engineering (slides 7–10, 3:20)

### Slide 7: Prompt library
We use a language model only where rules cannot decide, and we keep prompts as versioned files.
- **Versioning.** Each prompt has its own folder, a registry selects the active version, and every response
  records which prompt version produced it. A version is never edited in place.
- **The four key prompts:**
  - the router fallback;
  - the grounded answer;
  - the dialogue fact extractor;
  - the checklist translator.

  A fifth, the topic checker, is disabled because its verdicts were unstable.
- **Techniques:** role prompting, grounding rules, checkable citations, JSON outputs, few-shot examples and
  untrusted-input framing.
- **Validation.** Every output is checked by code before it reaches the user.

### Slide 8: Before and after: grounded answer
Our grounded-answer prompt went through three versions, all stored.
- **Version 1** limited the output to 600 tokens, and we saw an Arabic answer cut in the middle of a sentence.
  Lists of documents were also being summarised.
- **Version 2** raised the budget to 900 tokens and added one rule: reproduce list items faithfully.

On the same twelve development questions, acceptance rose from 0.667 to 0.750, and the share of answers in the
correct language rose from 0.917 to one. Look at the same input on the right. With version 1, the answer was
rejected, so an English user received an Arabic passage. With version 2, they get a correct English answer,
"twenty percent or more of the capital", with citations.

The cost: version 2 paraphrased more. A version 3 that quotes first gained one verbatim quote but was seven
seconds slower, so we did not adopt it.

### Slide 9: Before and after: router and dialogue
For the router, only one version exists, so we wrote a clearly labelled control baseline without our role,
language notice and definitions. On 84 development questions, category accuracy rose from 0.714 to 0.881. The
baseline called most business-registration questions "general".
- **What did not improve:** Derja intent stayed weak, and the current prompt more often outputs a label outside
  the allowed list. The code rejects those labels.

For the dialogue extractor:
- **Version 1** invented facts, such as "first application" for a plain question.
- **Version 2** removed them.
- **Version 3** added a JSON schema: all 18 outputs became valid.

The code still removes invented quantities: prompts and validation work together.

### Slide 10: Translation and the lesson
For translation, a plain "translate this" baseline rewrote dates and dropped a photo size. Our prompt keeps
numbering and numbers, and the validator now accepts ten of eleven official checklists instead of four.

French-to-Arabic translation was withdrawn instead: it turned "widow" into "one-eyed woman", while passing
format checks.

The general lesson: no prompt made a 7B model paraphrase law reliably. So legal articles are now extracted
verbatim instead of generated. Member 4 explains how we find them.

---

## Member 4: Retrieval-Augmented Generation (slides 11–13, 3:20)

### Slide 11: Official corpus
Our knowledge base is small on purpose: twelve official documents, each downloaded with its provenance.
- **Provenance.** A registry lists eighteen candidate sources. The downloader respects robots files and AI
  opt-outs and verifies TLS. It stores every original unmodified, with its SHA-256 checksum.
- **What is indexed:**
  - the passport guides in French and Arabic;
  - the identity-card guide;
  - the RNE table of ninety-five procedures;
  - the two registration forms;
  - six legal texts.
- **Extraction.** Each document becomes typed blocks: headings, paragraphs, list items and table rows, with
  page numbers.
- **Two chunkers read the same blocks.** The structure-aware chunker keeps a heading with its list, or a table
  row as one unit, and produces 272 chunks. The recursive splitter cuts every thousand characters with overlap,
  and produces 174.
- **Embeddings.** Both collections are embedded with BGE-M3 in 1024 dimensions, one multilingual space for
  French, Arabic, English and Derja.

### Slide 12: Retrieval pipeline
At query time the router's category becomes a filter.
- **Exact codes.** If the question names an RNE code, we do not search by similarity at all: a code is a key,
  not a meaning, so we read that exact row.
- **Fusion.** Otherwise we fuse three ranked lists with reciprocal rank fusion: dense search on the raw
  question, dense search on an expanded question, and BM25 keyword search with normalisation of company types
  and common Arabizi words.
- **The cap.** At most two chunks per document reach the top five.
- **After retrieval.** Retrieval only locates the evidence. The agents then read the complete official unit,
  and citations are copied from the stored metadata, never generated.

### Slide 13: Evaluation
We measured retrieval against evidence spans verified verbatim in the official text, on 71 labelled development
questions.
- **Hit@5** asks whether at least one relevant chunk is in the top five. **MRR** rewards ranking it first.
- Raw dense retrieval reaches 0.732. Our earlier agent retriever was worse, at 0.704. Fusion raised it to 0.845,
  and the cap to 0.873, with MRR 0.675.

The chunking result is interesting: the winner depends on the retriever. With dense search alone, recursive
chunks win. With fusion and the cap, structure-aware chunks win, because one table row becomes one exact match.

Be careful with these gains. On 20 held-out questions the hybrid only ties dense retrieval, so part of the
improvement was overfitting. And Latin-script Derja remains our weakest language. Member 5 now explains the
agents that use these passages.

---

## Member 5: Multi-Agent Architecture and Multimodality (slides 14–15, 3:20)

### Slide 14: Orchestrated multi-agent architecture
We describe our system honestly as an orchestrated multi-agent architecture, not an autonomous one. n8n decides
the flow; no agent plans or chooses tools at run time.
- **The Intent Router** is a rule-first agent. It owns the language, procedure, intent and dialogue state, and
  asks clarifying questions. It calls the language model only when no rule applies.
- **The Retriever** is deterministic.
- **The Checklist Builder** quotes official sections verbatim and uses a model only to translate into English.
- **The Grounded Answer agent** decides between extracting an article or table row, generating a verified
  answer, or refusing.
- **The Form-Filling Helper and the Dossier Validator** use no language model at all.

Why separate them? Lists must be complete and verbatim. Codes are keys. Legal text must not be paraphrased by a
seven-billion-parameter model. Forms need geometry. And readiness must never be certified by a model.

We have direct evidence for this choice. When RNE follow-ups and legal questions went through one generic
path, all 190 RNE follow-ups returned only source links, and the official legal passage appeared in one answer
out of thirty. After the dedicated paths: 190 out of 190, and 26 out of 30.

### Slide 15: Multimodality
Citizens can also send a form as a PDF, a scan or a phone photo.
1. We check the type, the file signature and the size, up to ten megabytes.
2. A digital PDF is compared geometrically with the official blank form.
3. A photo is first deskewed and read with Tesseract OCR in Arabic and French. Then a RANSAC homography aligns it
   with the blank form, using anchor words.
4. Finally we measure the ink inside each field band, because OCR alone cannot read handwriting on dotted
   lines.

The table shows real results we ran on the candidate backend. Blank forms are recognised with every field empty.
A form with three filled fields, rotated as a JPEG photo, still shows three filled. Corrupt, unsupported and
oversized files are handled safely. Thirteen of thirteen cases behave as expected, and an image takes about 2.5
seconds. The filled text in these fixtures is the neutral word "placeholder", never personal data.

The Dossier Validator builds on this. It reports field status, quotes the official requirements verbatim, and
never certifies completeness, because no official list of RNE supporting documents exists.

Now Member 6 will show the system live.

---

## Member 6: Live Demonstration, Evaluation and Conclusion (slides 16–19, 3:20 including about 90 s of demo)

### Slide 16: Live demonstration (about 90 seconds live; see LIVE_DEMO_SCRIPT.md)
We chose four interactions on fast, deterministic paths, so that the demo does not depend on a slow model.
- **First,** I ask in French which documents are needed to renew a passport, living in Tunisia. You see the
  official list, quoted, with its source. *(Show the n8n execution briefly.)*
- **Second,** a follow-up: "and how much does it cost?". The context is kept, and we get the fee section,
  including the warning about the French and Arabic difference.
- **Third,** in Latin-script Derja: the fee for procedure RNE C 012. The exact official row comes back.
- **Fourth,** a photo of the blank F-001 form in form-check mode: seven fields reported empty.

If the bot is slow, we show the recorded results from today's evaluation run instead.

### Slide 17: Evaluation
Before release, an independent audit replayed 728 end-to-end cases through n8n.
- **What the earlier metrics missed.** Our citation metric had always been perfect, and it still hid two
  serious problems: every RNE follow-up returned only links, and one legal provision was fabricated behind a
  valid citation.
- **After the corrections, on the same cases:**
  - exact RNE rows went from 0 to 190 out of 190;
  - targeted official facts from 281 to all 480;
  - legal answers with the official passage from 1 to 26 out of 30;
  - form instructions from 0 to 10.
- **The fabricated provision is gone,** and every citation points to the official manifest. Today's
  multilingual and unit-test runs are on the slide.

### Slide 18: Limitations and future work
Our limits are real:
- a small corpus whose legal currency is not verified;
- no official list of RNE supporting documents;
- weak Latin-script Derja retrieval;
- slow model answers;
- no tests on real handwriting;
- labels written by the team.

Next we would add human-reviewed labels, activate the prepared security keys, validate legal translation with
experts, and add a semantic check between answer and evidence.

### Slide 19: Conclusion
To conclude:
- **Grounded by construction.** Lists, rows, articles and form instructions are quoted, and generation is
  fenced and verified.
- **Measured, not assumed.** Our evaluation reports failures as well as successes.
- **Local and multilingual,** on one laptop.

Our main lesson: perfect citation metrics can hide wrong answers. The fix that worked was architectural:
extract, do not paraphrase. Thank you. We are happy to take your questions.

---

## Backup slides (spoken only if asked)

### Slide 20
Backup divider: no speech.

### Slide 21
Security. The candidate closes the admin endpoints by default, and makes agent and webhook keys optional. We
will activate them in a separate, ordered phase, with callers configured first and enforcement last. The
reason: n8n turns any error, including authentication errors, into a 503, so a mismatch would look like an
outage.

### Slide 22
Full retrieval table. All eight configurations, plus Hit@5 per language on the parallel subset.

### Slide 23
Numeric verifier. Every digit in a generated answer must appear in the cited passage, as digits or as number
words. It removed every unsupported number on five sets, at a cost of about three milliseconds.

### Slide 24
Dialogue prompt detail. The raw and the validated metrics for v1, v2 and v3 on identical inputs.

### Slide 25
Router baseline vs v1 per language. The improvement is largest in English and smallest in Derja.

---

## Word counts and estimated durations (measured with `presentation/check_timing.py`)

See `PRESENTATION_TIMELINE.md` for the measured totals.
