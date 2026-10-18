"""Trace one question through the agent endpoints in the order of n8n workflow 03 (in-process, read-only).

usage: QDRANT_URL=http://127.0.0.1:6343 OLLAMA_URL=http://127.0.0.1:11434 python scripts/trace_case.py "question" [--context] [--no-llm]
Prints the route decision, the retrieved passages (document, heading, score) and the final agent output.
Admin endpoints are never called.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("--context", action="store_true", help="send {} like the Telegram bridge")
    ap.add_argument("--full", action="store_true", help="print the whole answer")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as c:
        body = {"text": args.text}
        if args.context:
            body["context"] = {}
        t = time.perf_counter()
        route = c.post("/agents/route", json=body).json()
        keys = ("language", "intent", "procedure_category", "next_agent", "method", "hints", "retrieval_query")
        print("ROUTE", json.dumps({k: route.get(k) for k in keys}, ensure_ascii=False), f"{time.perf_counter() - t:.2f}s")
        if route.get("next_agent") == "reply" or route.get("reply"):
            print("REPLY", route.get("reply"))
            return
        t = time.perf_counter()
        ret = c.post("/agents/retrieve", json={"query": args.text, "route": route, "top_k": 8}).json()
        for i, p in enumerate(ret.get("passages", []), 1):
            cit = p["citation"]
            print(f"  P{i} {p['score']:.3f} {cit.get('doc_id')} | {' > '.join(cit.get('heading_path') or [])[:90]} | {p['text'][:110]!r}")
        print(f"RETRIEVE {time.perf_counter() - t:.2f}s")
        path = "/agents/checklist" if route.get("next_agent") == "checklist" else "/agents/answer"
        t = time.perf_counter()
        res = c.post(path, json={"query": args.text, "route": route, "passages": ret.get("passages", [])}).json()
        print(f"{path} method={res.get('method')} citations={len(res.get('citations') or [])} {time.perf_counter() - t:.2f}s")
        text = res.get("text") or ""
        print(text if args.full else text[:900])


if __name__ == "__main__":
    main()
