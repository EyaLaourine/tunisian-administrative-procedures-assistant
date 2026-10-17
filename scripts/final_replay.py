"""Independent replay of original audit cases (read-only, query-only).

Uses the original suite questions/contexts/setup turns/upload specs unchanged, but its OWN checks
(not scripts/audit_full_coverage.assess). Output goes to the audit scratchpad only.

usage: python indep_run.py <webhook_url> <out.jsonl> <kinds comma-separated|all>
"""
import asyncio
import base64
import json
import re
import sys
import time
from pathlib import Path

import httpx

ROOT = Path.cwd()
URL, OUT, KINDS = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
suite = json.loads((ROOT / "data/evaluation/full_document_coverage.json").read_text(encoding="utf-8"))
cases = [c for c in suite["tests"] if c["execution_stage"] == "n8n_full_assistant"
         and (KINDS == "all" or c["kind"] in KINDS.split(","))]
manifest = json.loads((ROOT / "data/raw/manifest.json").read_text(encoding="utf-8"))["records"]
OFFICIAL_URLS = {r["url"] for r in manifest} | {r["final_url"] for r in manifest if r.get("final_url")}
FOOTER = re.compile(r"\n(?:📚|📎)")
CODE = re.compile(r"Code procédure:\s*(RNE\s*[CIM]\s*\d{3}(?:\.\d+)*)")
ASKED = re.compile(r"\bRNE\s*([CIM])\s*(\d{3}(?:\.\d+)*)", re.I)


def norm_code(c):
    return re.sub(r"\s+", "", c).upper()


def check(case, resp):
    text = resp.get("text", "") or ""
    m = FOOTER.search(text)
    body = text[:m.start()] if m else text
    spans = case.get("required_verbatim_spans") or []
    route = resp.get("route") or {}
    out = {
        "agent": resp.get("agent"), "intent": route.get("intent"), "category": route.get("procedure_category"),
        "next": route.get("next_agent"), "expected_intent": case.get("expected_intent"),
        "body_chars": len(re.sub(r"\W", "", body)),
        "spans_total": len(spans), "spans_in_body": sum(s in body for s in spans),
        "citations": [c.get("url") for c in resp.get("citations") or []],
    }
    out["citations_official"] = all(u in OFFICIAL_URLS for u in out["citations"])
    out["expected_doc_cited"] = None
    exp_docs = case.get("expected_document_ids") or []
    if exp_docs:
        doc_urls = {r["url"] for r in manifest if r["doc_id"] in exp_docs} | {r.get("final_url") for r in manifest if r["doc_id"] in exp_docs}
        out["expected_doc_cited"] = any(u in doc_urls for u in out["citations"])
    asked = ASKED.search(case["question"])
    if asked:
        want = norm_code(f"RNE{asked[1]}{asked[2]}")
        codes = [norm_code(c) for c in CODE.findall(body)]
        out["asked_code"] = want
        out["first_code_in_body"] = codes[0] if codes else None
        out["asked_code_present"] = want in codes
        out["other_codes_in_body"] = len([c for c in codes if c != want])
    return out


async def main():
    done = set()
    if OUT.exists():
        done = {json.loads(l)["id"] for l in OUT.read_text(encoding="utf-8").splitlines()}
    sem = asyncio.Semaphore(2)
    async with httpx.AsyncClient(timeout=httpx.Timeout(900, connect=15)) as client:
        async def post(body):
            r = await client.post(URL, json=body)
            r.raise_for_status()
            return r.json()

        async def one(case):
            async with sem:
                t0 = time.monotonic()
                row = {"id": case["id"], "kind": case["kind"], "language": case["language"], "url": URL,
                       "setup": [], "question": case["question"]}
                try:
                    context = case["conversation_context"]
                    for setup in case["conversation_setup"]:
                        r = await post(setup)
                        row["setup"].append({"agent": r.get("agent"), "intent": (r.get("route") or {}).get("intent"),
                                             "text_head": (r.get("text") or "")[:300]})
                        context = r.get("context")
                    body = {"text": case["question"], "language": case["language"]}
                    if context is not None:
                        body["context"] = context
                    spec = case.get("upload")
                    if spec:
                        if spec.get("fixture"):
                            pdf = spec["fixture"] == "corrupt_pdf"
                            data = b"%PDF-1.0\nneutral invalid file" if pdf else b"neutral placeholder"
                            name, mime = ("neutral.pdf", "application/pdf") if pdf else ("neutral.txt", "text/plain")
                        else:
                            path = ROOT / spec["raw_file"]
                            data, name, mime = path.read_bytes(), path.name, "application/pdf"
                            if spec["media"] == "image":
                                import fitz
                                with fitz.open(path) as d:
                                    data = d[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).tobytes("png")
                                name, mime = path.stem + ".png", "image/png"
                        body = {"file": {"filename": name, "mime_type": mime,
                                         "data_b64": base64.b64encode(data).decode()}, "language": case["language"]}
                        if spec["mode"] == "dossier":
                            body["mode"] = "dossier"
                    row["context_sent"] = body.get("context")
                    resp = await post(body)
                    row.update(status="ok", response=resp, checks=check(case, resp))
                except Exception as exc:  # noqa: BLE001
                    row.update(status="error", error=type(exc).__name__ + ": " + str(exc)[:200])
                row["seconds"] = round(time.monotonic() - t0, 3)
                with OUT.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
        todo = [c for c in cases if c["id"] not in done]
        print(f"running {len(todo)} cases against {URL}", flush=True)
        await asyncio.gather(*(one(c) for c in todo))
        print("done", flush=True)


asyncio.run(main())
