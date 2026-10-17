# Academic rubric compliance (audit, 2026-10-17)

Scores are **indicative**, based only on evidence verified in this audit (see `TECHNICAL_GAP_REGISTER.md`
and `ARCHITECTURE_VERIFICATION.md`). They are not a prediction of the examiner's grade. Functionality that
exists only in documentation or in the undeployed candidate code earns no credit.

## Mandatory requirements

| Requirement | Status | Evidence |
|---|---|---|
| n8n integration | VERIFIED | Workflow 03 active, 16 nodes, identical to the repository export. All Telegram, web and CLI traffic passes through its webhook. |
| ≥ 40 evaluation questions | VERIFIED | `eval_set.jsonl` 84, `heldout_set.jsonl` 20, plus test/test2/regression sets (41). Coverage suite: 846 cases. **Caveat:** all 84 dev labels have `human_review: pending`. |
| Two chunking strategies compared | VERIFIED | Structure-aware (≤ 1200 characters) vs recursive (1000/150), two Qdrant collections (272/174 points). Results in `retrieval_results_*.json` (dense, agent, hybrid, cap variants). |
| English report ≤ 8 pages | VERIFIED | `report/report.pdf`: 8 pages, English. Section 6 is outdated on Telegram status (G-12). |
| 15-minute demonstration readiness | PARTIALLY VERIFIED | `docs/DEMO_SCRIPT.md`, web fallback (8/8 scenarios), CLI verified. Step R01 fails on Telegram (G-01). LLM steps take 20–176 s (G-14). |
| Smart Administrative Dossier Validator (innovation) | VERIFIED (limited scope) | `/agents/dossier-check` through the n8n `Dossier mode?` branch. Telegram `/dossier_check`. Integration tests passed today against production n8n. Covers only the 2 official RNE forms; `completeness_certified` is always false. |

## Criterion assessment

### 1. Prompt Engineering — weight 20 % — indicative 13 / 20

**Evidence**
- `prompts/` holds 5 prompt families and 9 immutable versions, with a registry and a reference returned in
  each response (`prompt_ref`).
- Templates are YAML with variables, model role, options, and JSON output or schema.
- Grounding rules ("ONLY the numbered passages", cite `[n]`, copy amounts verbatim).
- "Untrusted data" injection guards in the dialogue and topic prompts.
- Measured v1 → v2 → v3 comparison (`agent_results_prompt_v3.json`, report Table 7).
- Probe INJECTION: the injected "5 dinars" was ignored, and the official 20/60-dinar passport fees were
  returned.

**Weaknesses**
- The LLM is used in only 4 runtime places: grounded answer, FR→EN translation, the router fallback, and
  dialogue extraction.
- The prompt comparison uses 12 items. Grounding instructions do not prevent fabricated legal content
  (G-02, G-03).
- The grounded-answer prompt has no injection clause (passages are trusted).
- v3 is not adopted; the topic prompt is disabled.

**Likely objections:** "Your prompt says 'never invent', yet Article 16 was invented — what did prompt
engineering achieve?" and "12 items is not a comparison."

**Improvements:** an extractive legal prompt (quote-then-explain), a larger prompt A/B on legal items, and
reporting failure examples next to metrics.

### 2. RAG — weight 25 % — indicative 17 / 25

**Evidence**
- **Provenance:** a registry of 18 sources with robots and AI-opt-out compliance; a manifest with SHA-256;
  exclusions documented.
- **Pipeline:** text-layer extraction plus HTML table parsing; two chunkers; BGE-M3 1024-d; hybrid dense
  (raw + expanded) + BM25, RRF k = 60, per-document cap 0.4·k; answerability gate; numeric verifier.
- **Retrieval quality:** dev Hit@5 0.704 → 0.873. Held-out Hit@5 0.750, equal to raw dense retrieval.
  Overfitting is disclosed honestly.
- **Coverage audit:** 846 cases, citation validity 1710/1710.

**Weaknesses**
- The requested-fact check passes only 281/480.
- Retrieval misses exact legal articles (G-02).
- Verbatim checklists are strong for guides but wrong-scenario cases exist (G-07, G-08).
- No reranker.
- The held-out gain is zero.
- Labels are not human-reviewed.
- The evaluation does not cover the production Telegram path (G-06).

**Likely objections:** "Hybrid does not beat dense on held-out — why keep it?" and "Faithfulness 1.0 is a
number-presence check, not entailment."

**Improvements:** exact article/code lookup, an entailment check, re-evaluation on the deployed Telegram
shape, and a human review of a label sample.

### 3. Multi-Agent Architecture — weight 25 % — indicative 15 / 25

**Evidence**
- Six specialised backend agents (router/dialogue, retriever, checklist builder, grounded answer, form
  helper, dossier validator) with typed Pydantic contracts.
- n8n performs the branching (4 IF nodes) and the hand-offs.
- Deterministic-first design, with an LLM used only where needed.
- Dialogue state is carried across turns through the bridge.

**Weaknesses**
- This is a **fixed sequential pipeline**: there is no agent autonomy, planning, tool selection or
  inter-agent negotiation, and `next_agent` is computed by one rule-based router.
- There is no error handling in n8n (G-10).
- Multi-turn context loses the legal subject (G-05).
- The deployed code diverges from the repository (G-04).

**Likely objections:** "Are these agents or microservices?" The defensible answer is "specialised,
orchestrated agent services, deliberately deterministic for safety." Also: "What happens when one agent
fails?"

**Improvements:** n8n error branches; present the design honestly as an orchestrated pipeline; optionally
add a verifier-driven retry loop (answer → verifier → re-retrieve).

### 4. Multimodality — weight 15 % — indicative 10 / 15

**Evidence**
- **Inputs:** PDF text layer (PyMuPDF), images and Telegram photos via Tesseract `ara+fra` OCR, OpenCV
  deskew, homography to the template, and an ink check.
- **Template matching:** against the official F-001/F-002 forms, with field statuses that feed the dossier
  report.
- **Verified paths:** upload integration tests (PDF, PNG, JPEG, photo, and dossier mode) passed today
  through production n8n.

**Weaknesses**
- Only 2 templates.
- No handwriting or real-photo evaluation set; inputs are rendered official blank forms.
- No real Telegram upload in the live logs yet.
- OCR is not used during ingestion (the scanned 2026 decree is excluded).
- No audio.

**Likely objections:** "Have you tested a filled, photographed form?"

**Improvements:** a small consented set of synthetic-but-neutral filled forms (placeholder text, no
personal data) photographed under real conditions, with field-level accuracy.

### 5. Demo, Report and Q&A Readiness — weight 15 % — indicative 10 / 15

**Evidence**
- **Report:** 8 pages, honest limitations, held-out overfitting disclosed.
- **Demo:** script, checklist and Q&A preparation; web fallback with screenshots; CLI fallback; Telegram
  live.

**Weaknesses**
- The report and Telegram docs say Telegram is not live (G-12).
- The report's metrics predate the dialogue layer (G-06).
- Demo R01 fails over Telegram (G-01).
- The candidate fixes are undeployed: a decision is needed before the demo.
- Slow LLM answers (G-14).

**Likely defence questions**
1. What is the accuracy of the answers, not the citations?
2. Why do Telegram and the web give different answers?
3. Show an answer about a legal article.
4. How do you prevent hallucinated legal content?
5. Were the evaluation labels reviewed by a human?
6. What exactly does "multi-agent" mean here?
7. What happens with a filled, photographed form?

## Indicative total

| Criterion | Weight | Indicative score |
|---|---:|---:|
| Prompt Engineering | 20 | 13 |
| RAG | 25 | 17 |
| Multi-Agent Architecture | 25 | 15 |
| Multimodality | 15 | 10 |
| Demo, Report, Q&A | 15 | 10 |
| **Total** | **100** | **65** |

**Most score-sensitive actions before the defence:**
1. Fix G-01 in production, or demo RNE via the web/CLI path only.
2. Avoid legal-article questions live, or fix G-02.
3. Correct the documentation about Telegram status.
4. Prepare honest answers to defence questions 1–6.
