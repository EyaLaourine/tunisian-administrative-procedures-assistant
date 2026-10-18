# Q&A preparation (10 minutes): 36 likely questions with accurate answers

**Rule for answering:** if a number is not in this file or on a slide, say "we did not measure that" rather than
estimate it. Every member should be able to answer every block. The suggested first responder is in brackets.

## A. Use case and scope
1. **Why this use case?** [M1] The information is fragmented across ministry pages, the RNE site and Official
   Journal PDFs, in French and Arabic, while users write in Derja. Errors are costly, and the sources even
   disagree: the FR/AR passport stamp duties are 20/60 vs 25/80 TND.
2. **Why not cover birth certificates?** [M1] The only official source found opts out of AI use in its
   robots.txt. We respect it, and the assistant states that the procedure is not covered.
3. **Is the legal information current?** [M1/M4] We do not certify it: every document has
   `applicability: unverified` until a human confirms it is in force. A request to certify validity gets a
   fixed "limits" reply.

## B. Architecture and n8n
4. **Why n8n rather than a Python pipeline or LangGraph/AutoGen?** [M2] The orchestration is visible and editable
   (17 nodes in workflow 03), each agent is an HTTP node that can be tested alone, and there are per-node error
   outputs and a weekly ingestion schedule. Autonomous frameworks add non-deterministic control flow that a
   citation-bound domain does not need. The cost is two extra HTTP hops, which is small next to LLM time.
5. **What does each workflow do?** [M2]
   - **01:** ingest and index. 5 nodes, inactive, calls admin-only endpoints.
   - **02:** retrieval API. 3 nodes, dense retrieval only.
   - **03:** the assistant. 17 nodes, branching on file, dossier mode and the router decision.
6. **What happens if an agent fails?** [M2] Each of the six HTTP nodes has an error output leading to one
   sanitised HTTP 503 reply. The bridge retries, then shows a localised message. Limitation: an authentication
   error would also look like a 503.
7. **How does Telegram reach a local machine?** [M2] Through long polling: the bridge pulls updates
   outbound. There is no public URL, tunnel or open port.
8. **Is anything sent to a cloud API?** [M2] No. Ollama runs locally, and all ports are bound to 127.0.0.1.

## C. Prompt engineering
9. **Show a before/after for each key prompt.** [M3] See slides 8–10 and backup 24–25:
   - **grounded_answer:** v1 → v2, acceptance 0.667 → 0.750.
   - **intent_router:** labelled baseline → v1, category 0.714 → 0.881.
   - **dialogue_understanding:** v1 → v3, schema-valid 7 → 18 of 18; invented scenario facts 15 → 0.
   - **translate_items:** labelled baseline → v1, accepted 4/11 → 10/11.
10. **Are the baselines real historical prompts?** [M3] Only grounded_answer and dialogue_understanding have
    stored earlier versions. For intent_router and translate_items we wrote clearly labelled **controlled
    baselines** on 2026-10-18, with the same model, options and output format, and the techniques removed.
    We never present them as history.
11. **Why is grounded_answer v3 not active?** [M3] One more verbatim span (2/11 vs 1/11), the same acceptance,
    and 7 s slower.
12. **Did any prompt change fail to help?** [M3] Yes:
    - v2 paraphrased more than v1 (evidence span 3/11 → 1/11);
    - the router prompt did not improve Derja intent (0.308 → 0.231);
    - dialogue v3 raised recall but lowered precision compared with v2 after validation (0.818 → 0.632).
13. **How do you defend against prompt injection?** [M3/M6] User text is framed as data. The legal, checklist
    and RNE paths generate no text. LLM outputs are validated against enums, a schema and the citations.
    Injected "say the fee is 1 dinar" was ignored in our tests (today's multilingual run includes an injection
    case). The retrieved official text is trusted, which is acceptable only because the corpus is curated.
14. **Why temperature 0?** [M3] Reproducibility. Every evaluation uses it.

## D. RAG
15. **Why RAG rather than fine-tuning?** [M4] Answers must be traceable and must update when a decree changes.
    A 7B model cannot be fine-tuned on a 4 GB GPU anyway.
16. **Why BGE-M3?** [M4] One multilingual embedding space for FR, AR, EN and Derja queries over FR and AR
    documents. Cross-lingual retrieval works for FR, EN and AR (Hit@5 1.0 on the parallel subset with the
    hybrid).
17. **Define Hit@5 and MRR.** [M4] Hit@5 means at least one relevant chunk is in the top 5. MRR@5 is the mean of
    1/rank of the first relevant chunk. "Relevant" means that the chunk contains a verified official span.
18. **Structure vs recursive chunking: which is better?** [M4] It depends on the retriever. Recursive is better
    for raw dense (0.817 vs 0.732); structure is better for hybrid + cap (0.873 vs 0.775).
19. **Is 0.873 an overfit?** [M4] Partly. On the 20 held-out questions the hybrid ties dense retrieval at
    Hit@5 0.750, with a lower MRR (0.531 vs 0.635).
20. **Why no reranker?** [M4] GPU memory. It is listed as future work.
21. **How are citations generated?** [M4] They are not generated: title, URL, page and SHA-256 are copied from
    the chunk payload. Citation validity was 145/145 (dev) and 1547/1547 (audit). Citation validity is not the
    same as correctness.

## E. Multi-agent
22. **Is this really multi-agent?** [M5] It is *orchestrated* multi-agent: specialised components with
    contracts, coordinated by n8n. No agent plans or negotiates at run time. Two components use an LLM to
    generate text, the router uses one as a fallback, and three are deterministic. We state this in the report
    (Table 1).
23. **Why not one LLM agent with tools?** [M5] Measured cost of the generic path: 0/190 RNE follow-ups with the
    exact row, and the legal passage in 1 of 30 answers. After the dedicated paths: 190/190 and 26/30.
24. **Where is state kept?** [M5] In the client (the Telegram bridge): category, hints, declared items, RNE code
    and legal subject, with no identity values. It is held for 30 minutes and is per member in group chats.
25. **What does the router do when information is missing?** [M5] For passports it asks a targeted
    clarification (application type, residence) instead of guessing.

## F. Multimodality
26. **How do you detect filled fields on a photo?** [M5] Deskew, then Tesseract OCR (ara+fra), then a RANSAC
    homography to the blank form using anchor words, then the ink in each field band compared with the blank.
    OCR text alone is unusable on dotted lines.
27. **How accurate is it?** [M5] On fixtures derived from the official F-001/F-002: 13/13 cases as expected
    today, including a 3°-rotated JPEG with 3 filled fields. Not evaluated on real handwriting or real phone
    photos (a stated limitation).
28. **Do you store uploads?** [M5] No. They are processed in memory and never indexed or logged, and the n8n
    workflow saves no execution data.
29. **Does the Dossier Validator say a dossier is complete?** [M5] Never. No official RNE list of supporting
    documents exists, so it says completeness cannot be assessed.

## G. Evaluation and demo
30. **How did you evaluate without an LLM judge?** [M6] All checks are deterministic:
    - verified evidence spans;
    - manifest URL and hash for citations;
    - numbers in answers present in the cited passages;
    - language detection;
    - refusal patterns.
31. **What was the worst failure you found?** [M6] A fabricated provision for Law 2018-52 Art. 16, behind a
    valid citation. The fix was verbatim article extraction with refusal of non-existent articles.
32. **Why is the generated answer slow?** [M6] Mistral 7B runs about 40 % on a 4 GB GPU: 20–70 s per answer.
    The deterministic paths take under 0.3 s, which is why the demo uses them.
33. **Is the demo the production system?** [M6] Answer according to the deployment status on the day. As of
    2026-10-18 the validated candidate is **not yet deployed**. If the demo runs on the candidate stack, say so.

## H. Security and limitations
34. **What security controls exist?** [M6/M2] All of these are in the candidate:
    - loopback-only ports;
    - admin endpoints closed unless a key is set;
    - an optional agent key and webhook key;
    - 413 above 15 MB, and uploads limited to 10 MB with signature checks;
    - least-privilege environment variables;
    - no logging of queries or uploads.

    The keys are activated in a separate, ordered phase 2.
35. **Main limitations?** [M6]
    - 12 documents, with legal currency unverified;
    - Latin-script Derja the weakest;
    - slow LLM;
    - no real-handwriting tests;
    - labels written by the team (human review pending).
36. **What would you do with more time?** [M6]
    - human-reviewed labels and a larger held-out set;
    - a reranker on a bigger GPU;
    - expert-validated legal translation;
    - a semantic answer-evidence check;
    - more procedures from sources that allow reuse.
