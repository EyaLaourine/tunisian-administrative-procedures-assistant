# Final release validation - 19 October 2026

## Release scope

The final release includes the deployed bounded Derja conversation closing fix, the tested passport
residence regression and an explicit abroad-fee category recap. The latter is a display-only release
addition and is not claimed as part of the owner's real Telegram transcript.

The closing source files were checked against the saved deployment hash plan; both match. No running
container, workflow, index, model, credential or Docker volume was modified during this publication task.

## Automated and static validation before integration

- Full offline suite: **1470 passed, 7 skipped, 41 integration tests deselected**, 6 dependency deprecation warnings.
- Compose validation: passed with `.env.example` and a non-secret placeholder encryption value; no stack started.
- Workflow JSON: three expected IDs, unique node IDs, valid connection targets and no embedded credential references.
- README/installation relative links: passed. Printable English installation guide rendered and inspected (4 pages).
- Original official files: **15/15 SHA-256 values match the manifest**.
- Reachable publication history (release plus remote master): **682 blobs** scanned, including **330 archive members**.
- Credential-signature/path findings: **0**. Reviewed working-tree files were included in the scan.

The security scan checks known token/private-key/JWT patterns and sensitive paths; it is not a proof
against every possible form of sensitive content. Historical official-corpus Qdrant snapshots remain in
Git history and are not required for installation. No history rewrite was performed.

## Real Telegram acceptance

See `FINAL_TELEGRAM_ACCEPTANCE_20261019.md` for the owner-supplied transcript findings and their limits.
These observations are kept separate from offline tests. No new Telegram messages were sent by this task.

## Master integration

The remote master contains four intentional deletion commits after the common ancestor: presentation/,
report/, CLAUDE.md and AGENTS.md. There are no competing application changes. Preserve those deletions
and all master ancestry; retain the functional release additions. Do not force-push or change visibility.
The deleted academic files remain available in prior Git commits.

Post-integration tests and the final branch ancestry/tree comparisons must pass before the master push.
Final remote commit identities are reported after successful publication rather than predicted here.

## Windows clone line endings

The first post-merge Windows clone converted three hash-validated n8n JSON candidates to CRLF.
Three tests failed while 1467 passed. Git attributes now disable text conversion for official raw
originals and workflow JSON artifacts, preserving recorded bytes without changing expected hashes.
This is a packaging fix, not a workflow or production change. Post-fix validation is required before
master publication.
