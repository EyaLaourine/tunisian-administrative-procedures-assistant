# n8n Git checkpoint

This checkpoint records the completed API synchronization and approved presentation polish. No production API or service operation was performed while preparing the commit.

Canonical `workflows/01_ingest_and_index.json`, `02_retrieve_api.json` and `03_assistant_multi_agent.json` now match the final presentation candidates in full node definitions/layout, connections, settings and intended active states (01 inactive; 02/03 published). Canonical files retain their portable repository structure; absent versus empty optional server state is normalized by the existing strict runtime comparison.

## Privacy sanitization

Before staging, server-managed `shared` project/owner metadata was removed from the three presentation candidates. Original approved bytes remain only under ignored `tmp/n8n-git-checkpoint-originals/`. No executable field, annotation or webhook changed. The presentation manifest retains original approved SHA-256 values alongside the sanitized candidate hashes. The hash-pinned presentation API adapter now uses sanitized hashes; it still requires its historical private baseline and does not run automatically. The generator and comparison exclude only this explicit ownership metadata in addition to allowed note fields. Historical release reports describe the original synchronization, not a new live update.

Private exports/backups, operation wrappers, screenshots, logs, DPAPI material, environment files and credentials remain outside this commit. Historical preparation documents are retained as evidence; the presentation synchronization result records final deployment status.

## Verification

Focused offline suites: workflow review, API payload planning, controlled synchronization/rollback mocks, export normalization and presentation checks. Final result: 125 passed, zero failures/skips, five dependency deprecation warnings. Canonical consistency and candidate ownership-metadata removal have dedicated checks. Secret scan covers every staged file, with no credential or personal email findings. Exact committed paths are recorded in `deploy/n8n_presentation/checkpoint_files.txt`.

The first focused run exposed six comparisons due solely to copying empty server-only optional fields into canonical files. Those unnecessary fields were removed; all existing tests passed unchanged. No production logic was changed to alter test outcomes.

This is a local Git checkpoint only. Backend deployment and functional acceptance still require separate authorization.
