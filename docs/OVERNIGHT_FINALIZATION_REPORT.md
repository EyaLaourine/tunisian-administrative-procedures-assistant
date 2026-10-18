# Overnight finalization report (2026-10-18, 00:00–06:30 Africa/Tunis)

**Work location:** the isolated worktree `C:\Users\Eya Laourine\tna-overnight`, on the new branch
`overnight/finalization` (base `be787ca`). The main checkout (`codex/final-n8n-workflows`, `be787ca`) was not
touched. Nothing was pushed, merged, deployed or restarted.

## A. Executive summary

**Done:**
- **Prompt-engineering evidence for every key prompt.**
  - Three new controlled experiments, with labelled baselines where history is missing.
  - The recorded grounded_answer evidence was re-extracted.
  - A compliance matrix is complete for all four runtime prompts.
- **Multimodal evaluation:** 13/13 upload cases behave as expected.
- **Multilingual end-to-end evaluation:** 36 parallel questions and 13 behaviour cases, through the candidate n8n.
- **Retrieval reproduction:** identical to the recorded results.
- **One P1 defect found and fixed** with 15 regression tests. "Carte grise" (vehicle registration) was answered
  with the national-ID procedure.
- **Report updated:** 8 main pages + annexes.
- **A complete 20-minute presentation:** 25-slide editable PPTX, speaker notes for six members (measured 18:54
  spoken), timeline, demo script, 36 Q&A answers, diagrams, design guide.
- **Phase-2 security plan, README and `.env.example` fixes.**

**Remaining (needs you):**
- Review the overnight commits.
- Choose `final-candidate` or `overnight-candidate`.
- Approve the deployment.
- Do the Telegram acceptance and capture screenshots.
- Rehearse.
- Merge and push.

**Verdict: CONDITIONALLY READY.**

## B. Code and tests

| Commit | Content |
|---|---|
| `4f2ae80` | fix: refuse known uncovered procedures (carte grise, driving licence) by rule. `agents/intent_router.py` +10 lines; `tests/test_agents_routing.py` +27 lines (15 tests) |
| `7ad1128`, `a21141a` | style: restore the original line endings and bytes; net diff vs `be787ca` is +37 lines, 0 deletions |
| `c202d18` | eval: `scripts/prompt_experiments.py`, `multimodal_eval.py`, `multilingual_eval.py` and their result files; read-only retrieval reproduction |
| `a03b504` | report: Annex B (prompt experiments, generated), three-workflow description, security status line |
| (final commit) | presentation/, docs (this report, security phase-2 plan, prompt-engineering pointer), README first-indexing fix, `.env.example` security keys |

### The defect fixed (P1: wrong administrative claim)
- **Reproduction.** Through the candidate n8n, "Comment renouveler une carte grise ?" was answered *"Pour
  renouveler une carte grise, il faut suivre les étapes de renouvellement de la carte d'identité nationale [1]"*.
  The Derja "البطاقة الرمادية" was routed to the **passport** checklist.
- **Cause.** No keyword rule matched, so the LLM fallback chose "general" (or "passport"), and the agents
  answered from unrelated evidence. This is the same failure type as held-out H17.
- **Fix.** A deterministic out-of-scope rule for vehicle registration and driving licences (FR/EN/AR/Derja). It
  applies only when no covered procedure keyword is present, and runs before the dialogue path and the LLM
  fallback.
- **Verification:**
  - 12 of the 15 new tests failed before the fix;
  - unit suite **1069 passed, 5 skipped** (the skips need private n8n exports that are intentionally kept out of Git);
  - rules-only routing of all **145 labelled questions × 2 modes**: only the 7 vehicle/driving-licence questions
    changed, each to the labelled "none";
  - an isolated container smoke test of the new image (no network, read-only mounts, removed afterwards).
- **Caveat.** H17 and RT1–RT6 motivated the rule, so they are not independent evidence.

**Images.**
- `tunisian-admin-assistant-backend:overnight-candidate` = **`3b849b35`** (commit `a21141a`): the validated
  candidate plus this fix.
- `final-candidate` `7bef874d` and the bridge `517755a5` were **not touched**.

### Tests executed

| Test | Result | Class |
|---|---|---|
| Unit suite, worktree, before changes | 1054 passed, 5 skipped (private-export tests) | PASS / SKIPPED |
| Unit suite after the fix | 1069 passed, 5 skipped | PASS |
| Routing equivalence, 145 questions × 2 modes | only the 7 intended changes | PASS |
| Prompt experiments (3 prompts, 244 LLM calls) | see C | PASS (executed) |
| Multimodal eval, candidate backend | 13/13 as expected | PASS |
| Multilingual eval, candidate n8n | 11 evidence, 4 correct refusals, 14 clarifications, **7 failures**; behaviour 12/13 | PASS with documented FAILs |
| Retrieval re-run, read-only | identical metrics in 4/4 configurations | PASS |
| Isolated smoke test of `overnight-candidate` | router + form check as expected | PASS |
| LaTeX build | 15 pages, main ≤ 8, no undefined references | PASS |
| PPTX structural check | 25 slides, 16:9, notes on all but the divider, no shape out of bounds, real-render review of every slide | PASS |
| Bandit static scan (48 files) | 0 high; 4 medium reviewed (B113 false positive; B108 container-local `/tmp` health file); 4 low | PASS (documented) |
| Secret scan of every tracked and new file and the PPTX | no token or key; only public RNE contact e-mails in official text; a neutral sandbox fixture password | PASS |
| Integration tests that write to Qdrant (`test_vectorstore`-type, `test_qdrant_roundtrip`) | not run | BLOCKED (would write to the shared Qdrant) |
| Live Telegram tests | not run | BLOCKED (no messages without you) |

## C. AI quality

**Prompt engineering** (`presentation/PROMPT_ENGINEERING_EVIDENCE.md`; report Annex B):

| Prompt | Before → after | Result |
|---|---|---|
| grounded_answer | v1 → v2 (historical) | accepted 0.667 → 0.750, language 0.917 → 1.000; evidence span 0.273 → 0.091 (trade-off); v3 not adopted |
| intent_router | B0 (labelled baseline) → v1 | category 0.714 → 0.881, both labels 0.452 → 0.643; **Derja intent not improved** |
| dialogue_understanding | v1 → v2 → v3 (historical) | schema-valid 7/4/18; invented scenario facts 15/0/0; after validation precision 0.727/0.818/0.632, recall 0.421/0.474/0.632 |
| translate_items | B0 (labelled baseline) → v1 | validator-accepted 4/11 → 10/11 (B0 rewrote dates and dropped "3/4 cm") |

**RAG.** Hit@5 0.873 / MRR@5 0.675 (hybrid + cap, structure chunks), reproduced exactly today. The held-out set
ties dense retrieval at 0.750. Structure vs recursive chunking reverses with the retriever.

**Multilingual** (candidate stack, `data/evaluation/multilingual_eval_results.json`):
- **Genuine failures:** R18, R19, M11, M12 (late-registration penalty: wrong article or row); R28, M10
  (beneficial owner: AR indefinite form refused, Latin-script Derja off-topic answer); M08 (Latin-script Derja
  name reservation refused).
- **Clarification questions** (14) are designed behaviour in Telegram mode.

**Multimodality.** F-001/F-002 PDFs and renders are recognised. A 3°-rotated JPEG with 3 filled fields gives 3
filled. Corrupt, unsupported and oversized files are handled safely. OCR takes about 2.4 s. Not tested on real
handwriting.

**Performance.** Deterministic paths take 0.03–0.2 s. The LLM paths take 6–140 s with Mistral 7B partially on a
4 GB GPU (grounded answer R18 55 s; M10 140 s). No optimisation was adopted: none had a reproducible benchmark
gain. Demo timing uses only the deterministic paths.

## D. Academic report
- **Source:** `report/main.tex`; build `report/main.pdf` = `report/report_final.pdf` (worktree, 15 pages).
- **Layout:** main body pages 1–8 (references end on page 8). Annex A (prompt library, generated) and Annex B
  (prompt experiments, generated) start on page 9.
- **Build log:** 0 undefined references or citations, 0 LaTeX warnings, 1 pre-existing 3 pt overfull box.
- `report/report.pdf` in the main checkout was not touched (it was previously locked by a viewer).

## E. Presentation (`presentation/`)
- **Deck:** `FINAL_PRESENTATION.pptx`, editable, 16:9. 19 main slides in the professor's exact section order,
  a divider, and 5 backup slides.
- **Content:** 3 native charts, 15 native tables, native-shape diagrams, and 3 **real** n8n editor screenshots.
  Every number is read from an evidence file at build time (`build_presentation.py`).
- **Speaker notes:** `SPEAKER_NOTES.md`, also embedded in the deck. Measured at 135 wpm
  (`check_timing.py`), in m:ss: M1 3:03, M2 3:08, M3 3:22, M4 3:03, M5 2:56, M6 3:24 including demo time.
  **Total 18:54 spoken; about 19:34 with handovers.**
- **Supporting files:**
  - `SLIDE_CONTENT.md` (exported from the deck);
  - `PRESENTATION_TIMELINE.md`;
  - `DIAGRAM_SPECIFICATIONS.md` (5 Mermaid diagrams from the code);
  - `PROMPT_ENGINEERING_EVIDENCE.md` (compliance matrix: all four key prompts COMPLETE, baselines labelled);
  - `RAG_EVALUATION.md`;
  - `LIVE_DEMO_SCRIPT.md` + `demo_client.py`;
  - `QA_PREPARATION.md` (36 Q&A);
  - `VISUAL_DESIGN_GUIDE.md`;
  - `BACKUP_SLIDES.md`.
- **Missing:**
  - **real Telegram screenshots** (no messages were sent);
  - **member names** (slides say "Member 1–6").

## F. GitHub readiness
- **Secret scan:** clean (B).
- **Docs:**
  - README: the first-indexing step was fixed. The old step executed workflow 01, which now returns 403
    without an admin key.
  - README: the layout table now lists `report/` and `presentation/`.
  - `.env.example` documents the three security keys.
- **Decision for you:** two Qdrant snapshot files (about 7.6 MB, official corpus vectors only) have been tracked
  since commit `1cea1d7` (`data/evaluation/post_audit_backup/qdrant/`). Removing them from history would need a
  rewrite, which was not done. They contain no secrets or personal data. Optionally:
  `git rm --cached data/evaluation/post_audit_backup/qdrant/*.snapshot` plus a `.gitignore` entry in a new commit.
- **Not done:** push and merge to `master`.

## G. Production status
- **No production change.** The backend, bridge, n8n and Qdrant containers keep the same IDs, images and start
  times, with 0 restarts.
- **Workflows:** 03 `af6ad259`, 02 `f4849a5c` and 01 `819f02d9` (inactive) are unchanged; 0 n8n executions
  since 22:00 UTC.
- **Data:** Qdrant 272/174; no Telegram send; Ollama is still on loopback (0.40.4, not restarted).
- **Candidate stack:** received read-only queries only. The candidate backend shares the production Qdrant, but
  its admin endpoints are closed (no key). No admin endpoint was called.
- **Blocked actions** (approval needed): deployment, Telegram acceptance, Qdrant-writing integration tests,
  security activation, push and merge.

## H. Today's action plan
1. **Review** `git log be787ca..overnight/finalization` (6 commits) and this report.
2. **Choose the image.** `final-candidate` (`7bef874d`; validated by the 728-case replay) or
   `overnight-candidate` (`3b849b35`; adds the carte-grise rule, a +10-line deterministic change). For
   `overnight-candidate`, optionally re-run the defect probes and the multilingual eval on an isolated stack.
3. **Back up** (approval): Qdrant snapshots of both collections (download and checksum); n8n CLI export and
   database copy; rollback tags `docker tag 8adaf99471c5 …:rollback-20261018` and the same for the bridge
   `7eafea6e792d`.
4. **Deploy** (approval; about 30 s + 60 s interruption): retag the chosen backend as `latest`;
   `docker compose up -d --no-deps --no-build --pull never backend`; health check; then the bridge with
   `--profile telegram`. One poller only.
5. **Test:** `scripts/defect_probes.py http://127.0.0.1:5678/webhook/assistant`; `presentation/LIVE_DEMO_SCRIPT.md`
   steps on Telegram (owner-sent); capture screenshots.
6. **Security phase 2:** separately, later (`docs/SECURITY_PHASE2_ACTIVATION_PLAN.md`).
7. **Finalise:** add member names and real screenshots to the deck; rehearse twice with a timer; check the
   report PDF.
8. **Git** (approval): merge `overnight/finalization` into `codex/final-n8n-workflows` or `master`, then push.

## I. Final verdict: **CONDITIONALLY READY**
- **Evidence for:** the system works end to end on the validated candidate; evaluations are reproducible;
  every key prompt has before/after evidence; the report and presentation are complete.
- **Conditions:**
  - approved deployment (production still runs the older backend, whose admin endpoints are unauthenticated);
  - Telegram acceptance on the deployed system;
  - the known failures disclosed: late-penalty legal questions, Latin-script Derja weaknesses, LLM latency.
