# Audit of the Qdrant snapshots committed to Git (2026-10-18)

No history was rewritten and nothing was pushed.

## 1. What is tracked

| Path (tracked since commit `1cea1d7`, 2026-10-17 16:46) | Size | SHA-256 |
|---|---|---|
| `data/evaluation/post_audit_backup/qdrant/official_docs_structure-2291018569016737-2026-10-17-14-21-59.snapshot` | 4,432,384 bytes | `0d544f069673ad7921f379369a22c395616fffc6659b4ed285cf47d5fb834ec3` |
| `data/evaluation/post_audit_backup/qdrant/official_docs_recursive-2291018569016737-2026-10-17-14-22-06.snapshot` | 3,361,792 bytes | `0da06b9a625d83506d59324f3ef183cc5f3ec958e2096dec5bdffc3f13f89cfd` |
| `data/evaluation/post_audit_backup/qdrant/manifest.json` | small | – |

Both are only in commit `1cea1d7`, the repository's root commit. Total: about 7.4 MB (7,794,176 bytes).

## 2. Provenance
- **Created** by the Qdrant snapshot API on the project's own collections (`official_docs_structure`,
  `official_docs_recursive`) on 2026-10-17 at 14:21–14:22, as the pre-deployment backup of the post-audit release.
- **Cross-check.** The structure snapshot's SHA-256 equals the checksum of the snapshot still listed by the
  production Qdrant (`GET /collections/official_docs_structure/snapshots`).
- **Restore check (2026-10-18).** Both files were restored into a **disposable** Qdrant 1.19.0 (separate
  temporary volume, loopback port), then the container and volume were removed. Results: 272 and 174 points,
  status green, 1024-d cosine vectors. These are identical to the production counts.

## 3. Content scan (every payload of every point, read from the restored copy)
- **Payload fields:** `applicability, chunk_id, chunk_index, chunk_language, doc_id, document_type,
  heading_path, language, official_reference, page_end, page_start, procedure_category, publication_date,
  retrieval_timestamp, sha256, source_organization, strategy, text, title, url`.
- **Documents.** Every `doc_id` is one of the 12 indexed official documents of `data/raw/manifest.json`, and every
  `sha256` is a manifest checksum.
- **Search patterns:** e-mails, Tunisian phone numbers, Telegram tokens, JWTs, Windows/Unix user paths, the
  owner's name, private IPv4 addresses and 8-digit identifiers.
- **Findings.** The only hits are the RNE's **public institutional contact**, printed on the official forms
  F-001/F-002 and present in `data/processed/extracted`: `ncontact@registre-entreprises.tn`, `+216 70 248 170`
  and `+216 70 248 172`.
- **Not found:** user queries, uploads, personal data, tokens, keys or local paths.
- **Conclusion: no sensitive information.** The snapshots contain only public official text that the repository
  already publishes in `data/raw/` and `data/processed/`, plus their 1024-d embeddings.

**Related files in the same folder.** `active_workflow.json`, `active_workflow_after.json` and
`candidate_workflow.json` contain n8n `shared` metadata: opaque project and user UUIDs and "Unnamed Project". They
contain no names and no e-mails. This is low sensitivity, but it is internal server metadata. The canonical
workflows in `workflows/` already have it removed.

## 4. Publication options (choose one; none applied)

| Option | Effect | History rewrite? | Recommendation |
|---|---|---|---|
| A. Publish as-is | 7.4 MB of binaries in the root commit; reproducible backup evidence | no | acceptable: no sensitive content |
| B. Stop tracking from now on: `git rm --cached data/evaluation/post_audit_backup/qdrant/*.snapshot`, add `data/evaluation/post_audit_backup/qdrant/*.snapshot` to `.gitignore`, commit | Future checkouts do not contain them; they **remain in the history** of `1cea1d7` and would still be pushed | no | **recommended if you want to keep the "no snapshots in the tree" rule without rewriting history** |
| C. Publish a fresh repository (squashed export of the final tree without the snapshots) | GitHub never receives the binaries | no rewrite of the local history, but a new published history | best if the published history must contain no binaries |
| D. Rewrite history (`git filter-repo`) | removes them everywhere | **yes** | not recommended: forbidden without explicit approval, and breaks every existing commit ID |

**Also consider:** for B or C, strip the `shared` block from the three backup workflow JSON files, or move them
out of the published tree.

## 5. Other publication finding: local paths containing the owner's name
`git grep` finds the Windows user-profile path, which contains the owner's real name, in these tracked files:
- `data/evaluation/post_audit_integration.xml`, `post_audit_integration_candidate_v1.xml`, `post_audit_unit.xml`,
  `post_audit_unit_final.xml` (pytest JUnit reports);
- `deploy/n8n_review/second_synchronization_result.json`, `deploy/n8n_review/synchronization_result.json`,
  `docs/N8N_VALIDATION_REPORT.md` (n8n synchronization evidence);
- `report/build.log`, `report/main.log` (LaTeX build logs: build artefacts with no academic value).

There is no secret in these files. However, a real name inside a local path is personal data you may not want
on GitHub. The overnight documents were made path-neutral; these files were **not modified**.

**Options:**
1. Untrack the LaTeX artefacts (`git rm --cached report/*.log report/*.aux report/*.out` plus `.gitignore`).
2. Replace the user-profile prefix with `<repo>` in the JSON/XML/Markdown evidence in a new commit.
3. Use the squashed publication (option C above), which can include both.
