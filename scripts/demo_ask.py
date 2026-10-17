"""Send one demo request to the n8n assistant webhook and print the reply (UTF-8 safe on Windows).

Usage:
  .venv/Scripts/python scripts/demo_ask.py "question text"
  .venv/Scripts/python scripts/demo_ask.py --local "question text"   # in-process, current code (see below)
  .venv/Scripts/python scripts/demo_ask.py --file path/to/form.pdf [--language fr]
  .venv/Scripts/python scripts/demo_ask.py --mode dossier --file path/to/form.pdf [--language fr]  # bonus via n8n
  .venv/Scripts/python scripts/demo_ask.py --dossier --file path/to/form.pdf [--language fr]   # bonus, in-process fallback
"""

import argparse
import base64
import mimetypes
import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # for --local

WEBHOOK = "http://localhost:5678/webhook/assistant"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="?")
    ap.add_argument("--file")
    ap.add_argument("--language")
    ap.add_argument("--url", default=WEBHOOK)
    ap.add_argument("--mode", choices=["dossier"], help="with --file: Smart Administrative Dossier Validator via n8n")
    ap.add_argument("--local", action="store_true",
                    help="call the agent endpoints in-process, in the order of n8n workflow 03 (demo fallback when "
                         "the deployed backend is not up to date or n8n is unavailable)")
    ap.add_argument("--dossier", action="store_true",
                    help="Smart Administrative Dossier Validator on --file (in-process, POST /agents/dossier-check)")
    args = ap.parse_args()
    if args.dossier:
        return dossier(args.file, args.language)
    if args.local:
        return local(args.text)
    if not args.text and not args.file:
        ap.error("give a question or --file")
    payload: dict = {}
    if args.text:
        payload["text"] = args.text
    if args.file:
        path = Path(args.file)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        payload["file"] = {"filename": path.name, "mime_type": mime, "data_b64": base64.b64encode(path.read_bytes()).decode()}
    if args.language:
        payload["language"] = args.language
    if args.mode:
        payload["mode"] = args.mode
    started = time.perf_counter()
    key = os.environ.get("ASSISTANT_WEBHOOK_KEY", "").strip()
    resp = httpx.post(args.url, json=payload, timeout=900, headers={"X-Assistant-Key": key} if key else {})
    elapsed = time.perf_counter() - started
    resp.raise_for_status()
    data = resp.json()
    sys.stdout.reconfigure(encoding="utf-8")
    route = data.get("route") or {}
    print(f"[live] HTTP {resp.status_code} in {elapsed:.1f}s | agent={data.get('agent')} "
          f"language={route.get('language')} intent={route.get('intent')} category={route.get('procedure_category')}")
    print("-" * 80)
    print(data.get("text", ""))
    return 0


def local(text: str) -> int:
    """Same agent sequence as workflow 03 (route -> retrieve -> checklist|answer), without n8n."""
    from fastapi.testclient import TestClient

    from backend.main import app

    sys.stdout.reconfigure(encoding="utf-8")
    started = time.perf_counter()
    with TestClient(app) as c:
        route = c.post("/agents/route", json={"text": text}).json()
        if route["next_agent"] == "reply":
            out, agent = {"text": route["reply"]}, "intent_router"
        else:
            passages = c.post("/agents/retrieve", json={"query": text, "route": route}).json()["passages"]
            agent = "checklist_builder" if route["next_agent"] == "checklist" else "grounded_answer"
            out = c.post(f"/agents/{route['next_agent'] if agent == 'checklist_builder' else 'answer'}",
                         json={"query": text, "route": route, "passages": passages}).json()
    print(f"[local, not via n8n] {time.perf_counter() - started:.1f}s | agent={agent} language={route['language']} "
          f"intent={route['intent']} category={route['procedure_category']} route={route['method']}")
    if out.get("verification"):
        print(f"verification: {out['verification']}")
    print("-" * 80)
    print(out.get("text", ""))
    return 0


def dossier(file: str, language: str | None) -> int:
    from fastapi.testclient import TestClient

    from backend.main import app

    sys.stdout.reconfigure(encoding="utf-8")
    path = Path(file)
    payload = {"filename": path.name, "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
               "data_b64": base64.b64encode(path.read_bytes()).decode(), "language": language}
    started = time.perf_counter()
    with TestClient(app) as c:
        report = c.post("/agents/dossier-check", json=payload).json()
    print(f"[local, not via n8n] POST /agents/dossier-check in {time.perf_counter() - started:.1f}s")
    print("-" * 80)
    print(report.get("text", report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
