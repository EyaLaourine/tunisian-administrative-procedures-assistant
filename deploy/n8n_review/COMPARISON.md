# n8n workflow drift and candidate validation

Generated from read-only CLI exports. No workflow was imported, executed or published.

| Workflow ID | Live executable | Repository executable | Candidate executable + notes | Live active | Repository active | Candidate runtime equals repository with live state |
|---|---:|---:|---:|---|---|---|
| TnaaIngestIndex1 | 5 | 5 | 5 + 6 | False | False | True |
| TnaaRetrieveApi1 | 3 | 3 | 3 + 4 | True | False | True |
| TnaaAssistant01 | 16 | 17 | 17 + 10 | True | False | True |

## Reviewed authority and drift

- Workflow 01: keep live inactive. The two backend writes remain unchanged and are never exercised by review tools.
- Workflow 02: repository says inactive; live is active. Candidate preserves the verified live state. It calls dense `/retrieve`, not hybrid `/agents/retrieve`.
- Workflow 03: retain the 17-node repository definition, including Claude’s six error outputs and shared 503 responder. This is a functional difference from live, not layout-only.
- All three add native Sticky Notes and node positions only relative to their selected executable baseline. No existing executable name, ID, expression, parameter, connection, webhook or setting is changed.
- Authentication is audited and specified in `security_mapping.json`; primary candidates do not turn on keys, change credentials or create unresolved credential references. Secure activation is a separate coordinated release gate.
- Native rendering/import, live failure simulations and authentication against real credentials have not been tested. Static compatibility uses the installed Sticky Note v1 schema and seven palette variants.

## Backup paths

- `tmp/n8n-review/20261017T220611Z/TnaaIngestIndex1.json`
- `tmp/n8n-review/20261017T220611Z/TnaaRetrieveApi1.json`
- `tmp/n8n-review/20261017T220611Z/TnaaAssistant01.json`

## Semantic comparison rules

Executable nodes exclude Sticky Notes; only node position and descriptive notes are ignored. Ordered IF output arrays, node names/IDs, expressions, parameters, credentials, onError, activation, settings, pin/static data and unknown top-level fields remain significant. Server version/timestamp/sharing metadata is excluded. Hashes accompany structured diffs; they are not the sole equivalence proof.
