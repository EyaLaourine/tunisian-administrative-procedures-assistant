"""Apply (or verify) the workflow 01 admin-key patch on live n8n through the public API, keeping it INACTIVE.

usage: N8N_REVIEW_API_KEY=<in memory> python scripts/n8n_patch_workflow01.py {check|apply} --backup <cli-export.json> --out <dir>

- check : GET only; verifies the live workflow against the backup and prints the planned change.
- apply : PUT /workflows/TnaaIngestIndex1?publishIfActive=false with ONLY the two HTTP nodes changed (Header Auth
          credential "TNAA Backend Admin"); never calls /publish or /activate. Verifies the saved draft and restores
          the original draft automatically if anything else changed.
The API key is read from the environment only and never printed; snapshots are written to --out (outside Git).
"""

import argparse
import json
import os
import sys
from copy import deepcopy
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.n8n_api_plan import writable_payload  # noqa: E402

WID = "TnaaIngestIndex1"
EXPECTED_VERSION = "819f02d9-349d-4567-bdeb-ed3f68092b4f"
TARGETS = {"Download official documents", "Build chunks and index (both strategies)"}
CREDENTIAL = {"httpHeaderAuth": {"id": "TnaaAdminKeyCred", "name": "TNAA Backend Admin"}}
AUTH = {"authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth"}


def api() -> httpx.Client:
    key = os.environ.get("N8N_REVIEW_API_KEY")
    if not key:
        raise SystemExit("N8N_REVIEW_API_KEY missing")
    return httpx.Client(base_url="http://127.0.0.1:5678/api/v1", headers={"X-N8N-API-KEY": key}, timeout=60)


def core(w: dict) -> dict:
    return {"id": w["id"], "name": w["name"], "nodes": w["nodes"], "connections": w["connections"], "settings": w.get("settings"),
            "active": w.get("active")}


def patched(w: dict) -> dict:
    out = deepcopy(w)
    for n in out["nodes"]:
        if n["name"] in TARGETS:
            n["parameters"].update(AUTH)
            n["credentials"] = deepcopy(CREDENTIAL)
    return out


def diff_nodes(a: dict, b: dict) -> list:
    na, nb = {n["id"]: n for n in a["nodes"]}, {n["id"]: n for n in b["nodes"]}
    if set(na) != set(nb):
        return [("node set changed", sorted(set(na) ^ set(nb)))]
    out = []
    for i in na:
        if na[i] != nb[i]:
            keys = sorted(k for k in set(na[i]) | set(nb[i]) if na[i].get(k) != nb[i].get(k))
            params = sorted(k for k in set(na[i].get("parameters", {})) | set(nb[i].get("parameters", {}))
                            if na[i].get("parameters", {}).get(k) != nb[i].get("parameters", {}).get(k))
            out.append((na[i]["name"], keys, params))
    return out


def verify_saved(before: dict, after: dict) -> list:
    problems = []
    if after.get("active") is not False or after.get("activeVersionId"):
        problems.append("workflow is not inactive/unpublished after save")
    for k in ("id", "name", "connections", "settings"):
        if before.get(k) != after.get(k):
            problems.append(f"{k} changed")
    expected = patched(before)
    for name, keys, params in diff_nodes(before, after):
        if name not in TARGETS or set(keys) - {"parameters", "credentials"} or set(params) - set(AUTH):
            problems.append(f"unexpected change in {name}: keys={keys} params={params}")
    for n_exp, n_act in zip(sorted(expected["nodes"], key=lambda n: n["id"]), sorted(after["nodes"], key=lambda n: n["id"])):
        if n_exp["name"] in TARGETS and (n_act.get("credentials") != CREDENTIAL or any(n_act["parameters"].get(k) != v for k, v in AUTH.items())):
            problems.append(f"credential/auth not saved as intended on {n_exp['name']}: {n_act.get('credentials')}")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["check", "apply"])
    ap.add_argument("--backup", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    backup = json.loads(a.backup.read_text(encoding="utf-8"))
    backup = backup[0] if isinstance(backup, list) else backup
    c = api()
    r = c.get(f"/workflows/{WID}")
    r.raise_for_status()
    live = r.json()
    (a.out / f"api-{a.action}-before.json").write_text(json.dumps(live, ensure_ascii=False, indent=1), encoding="utf-8")
    pre = {"versionId": live.get("versionId"), "active": live.get("active"), "activeVersionId": live.get("activeVersionId"),
           "equals_backup": core(live) == core(backup), "credential_refs": [n["name"] for n in live["nodes"] if n.get("credentials")]}
    print("precondition:", json.dumps(pre))
    already = all(n.get("credentials") == CREDENTIAL for n in live["nodes"] if n["name"] in TARGETS)
    if a.action == "check":
        print("planned node changes:", diff_nodes(live, patched(live)), "| already patched:", already)
        return
    if already:
        print("already patched; nothing to do")
        return
    if pre["versionId"] != EXPECTED_VERSION or live.get("active") or live.get("activeVersionId") or not pre["equals_backup"]:
        raise SystemExit("precondition failed: live workflow differs from the verified backup/inactive state; no write")
    body = writable_payload(patched(live))
    r = c.put(f"/workflows/{WID}", params={"publishIfActive": "false"}, json=body)
    print("PUT status:", r.status_code)
    after = c.get(f"/workflows/{WID}").json()
    (a.out / "api-apply-after.json").write_text(json.dumps(after, ensure_ascii=False, indent=1), encoding="utf-8")
    problems = [] if r.status_code == 200 else [f"PUT returned {r.status_code}"]
    problems += verify_saved(live, after)
    print("saved versionId:", after.get("versionId"), "| active:", after.get("active"), "| activeVersionId:", after.get("activeVersionId"))
    print("node changes:", diff_nodes(live, after))
    if problems:
        print("PROBLEMS:", problems, "-> restoring the original draft")
        rr = c.put(f"/workflows/{WID}", params={"publishIfActive": "false"}, json=writable_payload(live))
        restored = c.get(f"/workflows/{WID}").json()
        print("restore PUT:", rr.status_code, "| restored equals original core:", core(restored) == core(live), "| active:", restored.get("active"))
        raise SystemExit(1)
    print("APPLIED: only the authentication of the two HTTP nodes changed; workflow inactive and unpublished")


if __name__ == "__main__":
    main()
