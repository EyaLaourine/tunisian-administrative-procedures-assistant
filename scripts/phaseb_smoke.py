"""Bounded, read-only production smoke test of the published n8n workflows 02 and 03 (Phase B).

usage: python scripts/phaseb_smoke.py <out.json>
Nine requests in total; the expected patterns come from the validated sets in scripts/defect_probes.py and the
integration tests. Nothing is ingested or indexed; workflow 01 is never called.
"""
import json
import re
import sys
import time

import httpx

N8N = "http://127.0.0.1:5678/webhook"
OUT = sys.argv[1]
res = []


def record(cid, ok, seconds, **extra):
    res.append({"id": cid, "ok": ok, "seconds": seconds, **extra})
    print(cid, "PASS" if ok else "FAIL", seconds, flush=True)


def ask(c, body):
    t0 = time.monotonic()
    r = c.post(f"{N8N}/assistant", json=body)
    return r, round(time.monotonic() - t0, 2)


with httpx.Client(timeout=900) as c:
    # 1. Workflow 02: retrieval passages with full citations
    t0 = time.monotonic()
    r = c.post(f"{N8N}/retrieve", json={"query": "pièces à fournir passeport", "top_k": 3})
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else None
    items = body if isinstance(body, list) else (body or {}).get("results", [])
    ok = r.status_code == 200 and len(items) == 3 and all(
        str(i["citation"]["url"]).startswith("http") and len(i["citation"]["sha256"]) == 64 and i.get("text") for i in items)
    record("wf02-retrieve-citations", ok, round(time.monotonic() - t0, 2), status=r.status_code,
           doc_ids=[i["citation"].get("doc_id") for i in items])

    # 2. Workflow 02: expected error handling (body without "query": documented generic n8n 500, pre-existing)
    t0 = time.monotonic()
    r = c.post(f"{N8N}/retrieve", json={"top_k": 3})
    record("wf02-missing-query-error", r.status_code == 500, round(time.monotonic() - t0, 2), status=r.status_code,
           body=r.text[:200])

    single = [  # (id, language, question, context, regex)
        ("wf03-ar-duplicate", "ar", "ما هي الشروط من أجل استخراج نظير من جواز السفر بالنسبة إلى التونسيين المقيمين بالتراب التونسي؟", None, r"نظير"),
        ("wf03-derja-duplicate", "derja", "نحب نطلع نظير من الباسبور وأنا ساكن في تونس، شنوة يلزم؟", {}, r"نظير من جواز سفر"),
        ("wf03-legal-citation-fr", "fr", "Quelles autorités compétentes peuvent obtenir les informations sur le bénéficiaire effectif ?", {}, r"^Source : .*Banque centrale de Tunisie"),
        ("wf03-legal-citation-ar", "ar", "ماذا ينص الفصل 16 من قانون السجل الوطني للمؤسسات 52 لسنة 2018؟", None, r"^المصدر: .*الفصل 16"),
        ("wf03-unknown-article-handling", "fr", "Que dit l'article 999 de la loi 2018-52 ?", None, r"je préfère ne pas deviner"),
    ]
    for cid, lang, q, ctx, pattern in single:
        b = {"text": q, "language": lang}
        if ctx is not None:
            b["context"] = ctx
        r, s = ask(c, b)
        d = r.json() if r.status_code == 200 else {}
        text = d.get("text") or ""
        record(cid, r.status_code == 200 and bool(re.search(pattern, text, re.S | re.M)), s, status=r.status_code,
               agent=d.get("agent"), chars=len(text), text=text)

    # French checklist: without a residence the assistant first asks "Tu résides en Tunisie ou à l'étranger ?"
    # (same behaviour as the previous release); the answer must then produce the sourced checklist.
    r1, s1 = ask(c, {"text": "Quelles pièces fournir pour renouveler un passeport ?", "language": "fr", "context": {}})
    d1 = r1.json() if r1.status_code == 200 else {}
    r2, s2 = ask(c, {"text": "En Tunisie", "language": "fr", "context": d1.get("context") or {}})
    d2 = r2.json() if r2.status_code == 200 else {}
    t2 = d2.get("text") or ""
    record("wf03-fr-checklist-2turn", "Tunisie" in (d1.get("text") or "") and d2.get("agent") == "checklist_builder"
           and "Pièces à fournir" in t2 and "Source" in t2, round(s1 + s2, 2), status=[r1.status_code, r2.status_code],
           clarification=d1.get("text"), agent=d2.get("agent"), chars=len(t2), text=t2)

    # Conversation context (two turns; the follow-up must be answered from the returned context)
    r1, s1 = ask(c, {"text": "Quelles pièces pour obtenir la carte d'identité nationale pour la première fois ?",
                     "language": "fr", "context": {}})
    ctx = (r1.json() if r1.status_code == 200 else {}).get("context") or {}
    r2, s2 = ask(c, {"text": "Et si mon cas ne correspond pas à ce texte ?", "language": "fr", "context": ctx})
    d2 = r2.json() if r2.status_code == 200 else {}
    record("wf03-context-followup", bool(ctx) and d2.get("agent") == "intent_router"
           and "guide officiel de la carte d'identité" in (d2.get("text") or ""), round(s1 + s2, 2),
           status=[r1.status_code, r2.status_code], context_keys=sorted(ctx), text=d2.get("text"))

json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("passed", sum(x["ok"] for x in res), "/", len(res))
