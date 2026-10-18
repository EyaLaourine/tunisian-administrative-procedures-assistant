"""Generates the PROPOSED workflow 01 patch (not applied to live n8n).

The hardened backend (final-candidate, rc-20261018b) disables /ingestion/run and /index/run unless ADMIN_API_KEY is set,
and then requires the X-Admin-Key header. Workflow 01 sends no header, so it fails with HTTP 403 at its first node.
The patch changes only the two HTTP Request nodes: authentication through an n8n Header Auth credential (the key
value lives in the credential, never in the workflow). Node IDs, names, URLs, bodies, options, connections, notes and
settings are unchanged. The credential ID is the one created in production n8n on 2026-10-18 (TnaaAdminKeyCred).

usage: python deploy/proposed/make_workflow_01_admin_key.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "workflows" / "01_ingest_and_index.json"
OUT = ROOT / "deploy" / "proposed" / "01_ingest_and_index_admin_key.json"
CREDENTIAL = {"httpHeaderAuth": {"id": "TnaaAdminKeyCred", "name": "TNAA Backend Admin"}}
TARGETS = {"Download official documents", "Build chunks and index (both strategies)"}


def main() -> None:
    w = json.loads(SRC.read_text(encoding="utf-8"))
    changed = []
    for n in w["nodes"]:
        if n["name"] in TARGETS:
            n["parameters"]["authentication"] = "genericCredentialType"
            n["parameters"]["genericAuthType"] = "httpHeaderAuth"
            n["credentials"] = CREDENTIAL
            changed.append(n["name"])
    assert sorted(changed) == sorted(TARGETS), changed
    OUT.write_text(json.dumps(w, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("written", OUT.relative_to(ROOT), "| changed nodes:", changed)


if __name__ == "__main__":
    main()
