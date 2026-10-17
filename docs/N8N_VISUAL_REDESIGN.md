# Native n8n visual candidates

Offline files: [candidate directory](../deploy/n8n_review/candidates/). Reproduce with `.venv/Scripts/python scripts/n8n_workflow_review.py --prepare --baseline tmp/n8n-review/20261017T220611Z` from the repository root; the private baseline is intentionally not committed. Reviewed candidates themselves are committed and tests can run without these private exports.

| Workflow | Live executable + notes | Candidate executable + notes | Organization |
|---|---:|---:|---|
| 01 | 5 + 0 | 5 + 6 | Triggers → official download → backend processing/chunking/embedding/indexing → summary; prominent reindex warning. |
| 02 | 3 + 0 | 3 + 4 | Webhook → dense backend retrieval → official passage response; auth and failure limitations in notes. |
| 03 | 16 + 0 | 17 + 10 | Entry left; documents above; text router middle; retrieval/checklist/answer right; shared error response below; internal legal/security/infrastructure notes separated. |

Only positions and native `n8n-nodes-base.stickyNote` version 1 annotations change relative to the chosen repository execution graph. Workflow 03's extra error node is existing repository functionality absent live, not a fabricated visual node. All executable node names, IDs, parameters, ordered branches and webhooks are preserved.

The installed n8n version is 2.41.3. Its actual Sticky Note schema supports `content`, `width`, `height`, `color`. Palette: input blue (5), routing purple (6), knowledge green (4), documents gold (2), answers blue (5), security red (3), infrastructure gray (7). Native teal is unavailable; blue is used and roles are labeled in text. Notes are explanations, never additional execution stages.

Current live graphs lack this sectioning; the retrieval editor was inspected in the actual n8n UI and Zoom to Fit was used without saving. Candidate JSON has **not** been imported or rendered in any running n8n environment. Native readability, text wrapping and wire crossings therefore remain acceptance gates. Geometry tests detect overlapping executable node boxes and note frames; they do not prove that editor-rendered labels or wires never overlap.

After approved application: open each editor from the architecture document, use **Zoom to Fit**, then zoom into the document and text lanes of workflow 03. Do not click Execute, Tidy Up, Save or Publish merely to inspect a graph. Any further layout edits require review. The wide overview communicates architecture; individual sections provide readable detail for screenshots.
