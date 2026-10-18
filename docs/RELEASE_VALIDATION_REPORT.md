# Release candidate validation (2026-10-18)

- **Branch:** `overnight/finalization` in a separate worktree (`../tna-overnight`).
- **Not done:** no deployment, no production restart, no merge, no push, no Qdrant write.
- **Isolated test stack (my own containers, loopback only, no restart policy):**
  - `rc-candidate`: image `rc-20261018b`, on 127.0.0.1:8003, read-only mounts;
  - `rc-n8n`: fresh n8n, no volume, on 127.0.0.1:5681, running workflow 03 with its URLs pointed at
    `rc-candidate`.

  Like `final-candidate`, the rc backend reads the shared Qdrant. Its admin endpoints are closed (no key), and
  none was called.

## 1. Root causes and fixes (the seven multilingual failures)

Each case was reproduced in-process with `scripts/trace_case.py`, through the same endpoints, in the n8n order.

| Case | Symptom on final-candidate | Stage | Root cause | Fix (commit) |
|---|---|---|---|---|
| R19 (FR), M11 (EN): late penalty | Arts. 53/55/57 (criminal sanctions) quoted instead of the late penalty | Evidence selection | The cross-lingual article vocabulary had no lateness concept. The generic "penalty" expansion (`يعاقب`, `بخطية`, `بالسجن`) gave arts. 53/55/57 a score of 8.33, against 7.74 for art. 51. | `LATE` concept → official wording `غرامة تأخير`, `الآجال القانونية`. The criminal-sanction expansion is skipped when the question is explicitly about lateness (`cc2ba29`). |
| R18 (AR): late penalty | LLM: "no information" (55 s) | Routing to the legal path | `غرامة` (the law's own word) was not a penalty word, so Law 2018-52 was not identified | `غرامة` added to `PENALTY` (`cc2ba29`) |
| M12 (Latin Derja): late penalty | RNE table row RNE C 009 | Routing | `khtiya` not recognised, so it went to the table instead of the law | `khtiya/5tiya/ghrama` added (`cc2ba29`) |
| R28 (AR): beneficial owner | Out-of-scope refusal (LLM fallback, 11 s) | Routing | The indefinite form `مستفيدا حقيقيا` matched no keyword | Indefinite/plural Arabic pattern added to the subject patterns and router keywords (`cc2ba29`) |
| M10 (Latin Derja): beneficial owner | Off-topic generated answer (140 s) | Evidence selection | `moustafid 7a9i9i` did not identify the decree, so an LLM answer was generated from unrelated passages | Latin-script pattern (`cc2ba29`) |
| M08 (Latin Derja): name reservation | Out-of-scope refusal (LLM fallback) | Routing | `chhedet 7ajz el esm` matched nothing | `7ajz/hajz … esm/ism/tasmi/chara` pattern (`cc2ba29`) |

- **Result.** All seven now quote the verified official span verbatim with the correct citation (Law 2018-52
  art. 51; Decree 2019-54; Decree 2019-53). They are deterministic and take under 0.6 s.
- **No legal content added.** Only search terms were added; nothing is translated or paraphrased.
- **Not independent evidence.** The motivating items are the ones these fixes target.

### Vehicle and driving-licence rule (validated, plus one correction)
- **What it does.** Refuses vehicle registration and driving-licence questions by rule. The audit of 846
  questions shows 0 changed routing decisions.
- **The correction.** "Pour la carte d **identité**, faut-il le permis de conduire ?" was refused, because the
  spelling `carte d identité` was not a national-ID keyword. The variant was added in `06e8887`, with 4 guard
  tests for messages that name a covered procedure next to a vehicle document.

## 2. Tests and benchmarks (exact counts)

| Suite | Result |
|---|---|
| Unit tests (`pytest -m "not integration"`) | **1097 passed, 5 skipped**: the skips need private n8n exports that are intentionally kept out of Git |
| … of which security (`test_api_security.py`) | 20 passed |
| … n8n contract and review tests | 120 passed, 5 skipped (the same private-export skips) |
| … Telegram bridge | 96 passed |
| … forms and dossier | 25 passed |
| … legal and residual-defect regressions (incl. 28 new) | 657 passed |
| New regression tests before the fix | 15 + 1 of the new tests failed on the old code, as intended |
| Rules-only routing, 145 labelled + 846 audit questions × 2 modes, vs `be787ca` | only the 10 targeted labelled questions change (18 decisions to the correct category, 6 to the correct act); **0 audit decisions change** |
| 728-case replay through n8n (`scripts/final_replay.py`, scored by `scripts/score_replay.py`) | **rc-20261018b equals final-candidate on all 17 metrics** (table below). The only differing response is the wording of one validated English translation, which is LLM nondeterminism. |
| Multilingual parallel set (36) + behaviour cases (13), through n8n | **final-candidate:** 11 evidence, 4 refusals, 14 clarifications, 7 failures; behaviour 12/13. **rc-20261018b: 18 evidence, 4 refusals, 14 clarifications, 0 failures; behaviour 13/13.** |
| Defect probes (A–D, through n8n) | 16/16 |
| Multimodal (13 upload cases, rc backend) | 13/13 |
| Integration tests (assistant, dialogue, Telegram with the Telegram API mocked), retargeted copies against the rc stack | **37/37 passed** |
| Integration not run | `test_integration_services` (3; writes a test collection to the shared Qdrant) and `test_demo_ui` (1; targets production). **BLOCKED.** |

**728-case replay** (same cases, same scorer):

| Metric | final-candidate | rc-20261018 | **rc-20261018b** |
|---|---|---|---|
| RNE fee/deadline with chat context, exact row and value | 190/190 | 190/190 | 190/190 |
| RNE without context, exact row first | 190/190 | 190/190 | 190/190 |
| Guide scenarios, all spans | 72/72 | 72/72 | 72/72 |
| Targeted official facts | 480/480 | 480/480 | 480/480 |
| Legal direct questions, passage contained | 26/30 | 26/30 | 26/30 |
| Legal multilingual / fee service / fee condition | 10/12 · 33/37 · 3/3 | same | same |
| Form instructions | 10/10 | 10/10 | 10/10 |
| Intent label agrees | 691/728 | 691/728 | 691/728 |
| Citation URLs official | 1547/1547 | 1547/1547 | 1547/1547 |
| Uploads: recognised / safe errors | 8/8 · 6/6 | same | same |
| Birth certificate refused · Art. 16 quoted | 4/4 · 1/1 | same | same |
| Median seconds per case | 0.188 | 0.172 | 0.157 |

**Scorer note.** `score_replay.py` reproduces the published final-candidate column exactly. The legal-passage
check (character 20-gram containment ≥ 0.8) is a reconstruction **calibrated** on the stored replays, which it
matches (26/30 final, 25/30 audited).

## 3. Candidate comparison and recommendation

| Image | Content | Evidence | Known failures |
|---|---|---|---|
| `final-candidate` `7bef874d` (commit `12828f3`) | validated release | replay 728 ✓, probes 16/16 | 7 multilingual failures; carte grise answered with ID-card evidence |
| `overnight-candidate` `3b849b35` (`a21141a`) | + vehicle rule | unit + routing, isolated smoke test; **no full replay** | the same 7 multilingual failures; the "carte d identité" + vehicle edge case |
| `rc-20261018` `c4e3abeb` (`cc2ba29`) | + seven fixes | replay 728 = final | the "carte d identité" edge case |
| **`rc-20261018b` `6124980f` (`06e8887`)** | + spelling variant | **replay 728 = final; multilingual 0 failures; behaviour 13/13; probes 16/16; multimodal 13/13; integration 37/37; unit 1097**; source hashes equal the commit | none known in the evaluated sets |

**Recommendation:** deploy backend **`rc-20261018b`** with the bridge **`final-candidate` (`517755a5`)**. The bridge
code is unchanged since `12828f3`, and the Compose configuration is unchanged. Do not deploy
`overnight-candidate` or `rc-20261018` (both superseded).

## 4. Remaining known limitations
- **Latin-script Derja retrieval** stays the weakest retrieval case (Hit@5 0.714). Today's fixes are vocabulary
  for specific phrasings, not general Arabizi understanding.
- **Passport questions** without application type or residence get a clarification question (14 of the 36), by
  design.
- **Legal direct questions:** 26/30 contain the official passage. The 4 misses and LLM latency (20–70 s) are
  unchanged.
- **Evaluation independence.** Labels were written by the team, and the items that motivated fixes are not
  independent.
- **Not executed:** live Telegram acceptance, and production deployment.

## 5. Deployment (requires approval; not executed)
1. **Back up:**
   - Qdrant snapshots of both collections, downloaded with checksums;
   - an n8n CLI export of the 3 workflows and a copy of the n8n database;
   - rollback image tags:

     ```
     docker tag 8adaf99471c5 tunisian-admin-assistant-backend:rollback-20261018
     docker tag 7eafea6e792d tunisian-admin-assistant-telegram:rollback-20261018
     ```

2. **Verify the release images:** backend `6124980fa905` and bridge `517755a5ad39`.
3. **Backend** (about 10–30 s of interruption; the workflow returns 503 meanwhile):

   ```
   docker tag tunisian-admin-assistant-backend:rc-20261018b tunisian-admin-assistant-backend:latest
   docker compose up -d --no-deps --no-build --pull never backend
   ```

   Then check `curl http://127.0.0.1:8000/health`.
4. **Bridge** (up to about 60 s; one poller only):

   ```
   docker tag tunisian-admin-assistant-telegram:final-candidate tunisian-admin-assistant-telegram:latest
   docker compose --profile telegram up -d --no-deps --no-build --pull never telegram-bridge
   ```

5. **Smoke tests:**
   - `python scripts/defect_probes.py http://127.0.0.1:5678/webhook/assistant <out>` should give 16/16;
   - `python scripts/multilingual_eval.py --url http://127.0.0.1:5678/webhook/assistant --out <out>` should give
     0 failures;
   - then the owner sends the demo messages on Telegram.

## 6. Rollback

```
docker tag tunisian-admin-assistant-backend:rollback-20261018 tunisian-admin-assistant-backend:latest
docker compose up -d --no-deps --no-build --pull never backend
docker tag tunisian-admin-assistant-telegram:rollback-20261018 tunisian-admin-assistant-telegram:latest
docker compose --profile telegram up -d --no-deps --no-build --pull never telegram-bridge
```

- **Workflows and data:** none are changed by this release, so no workflow or Qdrant rollback is needed.
- **Verify after rollback:** backend `/health`, the bridge health check, and an owner-sent Telegram text.

**Cleanup after the decision (my test containers only):**

```
docker rm -f rc-candidate rc-n8n
```

The superseded test images can be removed later, with `docker image rm` (not prune):
`tunisian-admin-assistant-backend:rc-20261018` and `:overnight-candidate`.

## 7. GitHub snapshots
See `docs/GITHUB_SNAPSHOT_AUDIT.md`:
- 2 snapshots, 7.4 MB, only in root commit `1cea1d7`;
- public official text and embeddings only;
- recommendation: option B (stop tracking in a new commit) or C (squashed publication); no history rewrite.
- also: 10 tracked files (test XML reports, n8n sync evidence, LaTeX logs) contain the local user-profile path with
  the owner's name. No secret, but personal data: options are in §5 of that document.

## 8. Readiness verdict: **READY FOR CONTROLLED DEPLOYMENT** of `rc-20261018b` + bridge `517755a5`
- **Evidence:** every executed automated suite passes, and the release candidate matches or improves on the
  validated candidate everywhere.
- **Remaining conditions:** your approval of steps 1–5, and an owner-sent Telegram acceptance on the deployed
  system.
