"""Interactive demo client that keeps the dialogue context like the Telegram bridge (fallback for slide 16).

usage: python presentation/demo_client.py [--url http://127.0.0.1:5680/webhook/assistant] [--language fr]
Commands at the prompt:  <text>  |  /file <path> [dossier]  |  /new  (clear the context)  |  /quit
Sends X-Assistant-Key only when ASSISTANT_WEBHOOK_KEY is set. Never use real personal documents.
"""

import argparse
import base64
import mimetypes
import os
import sys
import time
from pathlib import Path

import httpx


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:5680/webhook/assistant", help="candidate stack by default")
    ap.add_argument("--language")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    key = os.environ.get("ASSISTANT_WEBHOOK_KEY", "").strip()
    headers = {"X-Assistant-Key": key} if key else {}
    context: dict = {}
    print(f"webhook: {args.url}  (/file <path> [dossier], /new, /quit)")
    while True:
        try:
            line = input("\nyou> ").strip()
        except EOFError:
            break
        if not line:
            continue
        if line == "/quit":
            break
        if line == "/new":
            context = {}
            print("[context cleared]")
            continue
        payload: dict = {}
        if line.startswith("/file "):
            parts = line.split()
            path = Path(parts[1])
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            payload["file"] = {"filename": path.name, "mime_type": mime, "data_b64": base64.b64encode(path.read_bytes()).decode()}
            if len(parts) > 2 and parts[2] == "dossier":
                payload["mode"] = "dossier"
        else:
            payload = {"text": line, "context": context}
        if args.language:
            payload["language"] = args.language
        t = time.perf_counter()
        r = httpx.post(args.url, json=payload, headers=headers, timeout=900)
        r.raise_for_status()
        data = r.json()
        if "text" in payload:
            context = data.get("context") or context
        print(f"[{data.get('agent')} · {time.perf_counter() - t:.2f}s]\n{data.get('text', '')}")


if __name__ == "__main__":
    main()
