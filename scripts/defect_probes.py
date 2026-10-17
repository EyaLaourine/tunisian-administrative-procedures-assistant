"""End-to-end probes for residual defects A-D through an n8n webhook (query-only).

usage: python scripts/defect_probes.py <webhook_url> <out.json>
Context chaining mimics the Telegram bridge (fresh chat sends {}, later turns send the returned context).
"""
import json
import re
import sys
import time

import httpx

URL, OUT = sys.argv[1], sys.argv[2]
TWO_TURN = [  # (id, language, setup, follow-up, expected substring of the clarification)
    ("A-cin-fr", "fr", "Quelles pièces pour obtenir la carte d'identité nationale pour la première fois ?",
     "Et si mon cas ne correspond pas à ce texte ?", "guide officiel de la carte d'identité"),
    ("A-passport-en", "en", "What documents are needed to renew a Tunisian passport? I live in Tunisia.",
     "What if my case does not match this text?", "official passport guide"),
    ("A-rne-fr", "fr", "Quelle redevance pour RNE C 001 ?", "Et si mon cas ne correspond pas à ce texte ?",
     "Pour le RNE"),
    ("A-legal-fr", "fr", "Qui peut accéder aux informations sur le bénéficiaire effectif ?",
     "Et si mon cas ne correspond pas à ce texte ?", "point du texte"),
    ("A-passport-derja", "derja", "شنوة الأوراق اللازمة باش نجدد الباسبور؟ ساكن في تونس", "و كان حالتي ما تنطبقش؟",
     "الدليل الرسمي متاع الباسبور"),
]
SINGLE = [  # (id, language, question, context or None, regex expected in the answer)
    ("B-scope-en", "en", "RNE: According to this official document, what is its scope and what remains unverified: Formalités?", None, r"table of 95 procedures"),
    ("B-scope-fr", "fr", "Que couvre le tableau des formalités du RNE ?", {}, r"tableau de 95 procédures"),
    ("B-scope-ar", "ar", "RNE: ما نطاق هذا النص الرسمي: Formalités؟", None, r"95"),
    ("C-dup-ar-web", "ar", "ما هي الشروط من أجل استخراج نظير من جواز السفر بالنسبة إلى التونسيين المقيمين بالتراب التونسي؟", None, r"نظير من جواز سفر"),
    ("C-dup-ar-tg", "ar", "ما هي الشروط من أجل استخراج نظير من جواز السفر بالنسبة إلى التونسيين المقيمين بالتراب التونسي؟", {}, r"نظير من جواز سفر"),
    ("C-dup-derja-tg", "derja", "نحب نطلع نظير من الباسبور وأنا ساكن في تونس، شنوة يلزم؟", {}, r"نظير من جواز سفر"),
    ("D-art55-en", "en", "What is the penalty for a false declaration to the RNE?", {}, r"^Source: .*article 55"),
    ("D-art16-ar", "ar", "ماذا ينص الفصل 16 من قانون السجل الوطني للمؤسسات 52 لسنة 2018؟", None, r"^المصدر: .*الفصل 16"),
    ("D-bo-fr", "fr", "Quelles autorités compétentes peuvent obtenir les informations sur le bénéficiaire effectif ?", {}, r"^Source : .*Banque centrale de Tunisie"),
    ("D-art999", "fr", "Que dit l'article 999 de la loi 2018-52 ?", None, r"je préfère ne pas deviner"),
    ("D-art-noact", "fr", "Que dit l'article 5 ?", None, r"disposition précise"),
]


def post(c, body):
    t0 = time.monotonic()
    r = c.post(URL, json=body)
    r.raise_for_status()
    return r.json(), round(time.monotonic() - t0, 2)


res = []
with httpx.Client(timeout=900) as c:
    for pid, lang, setup, follow, expect in TWO_TURN:
        first, _ = post(c, {"text": setup, "language": lang, "context": {}})
        ctx = first.get("context") or {}
        r, s = post(c, {"text": follow, "language": lang, "context": ctx})
        ok = r.get("agent") == "intent_router" and expect in (r.get("text") or "")
        res.append({"id": pid, "ok": ok, "seconds": s, "context_in": ctx, "context_out": r.get("context"),
                    "text": r.get("text")})
        print(pid, ok, s, flush=True)
    for pid, lang, q, ctx, pattern in SINGLE:
        body = {"text": q, "language": lang}
        if ctx is not None:
            body["context"] = ctx
        r, s = post(c, body)
        text = r.get("text") or ""
        ok = bool(re.search(pattern, text, re.S | re.M))
        res.append({"id": pid, "ok": ok, "seconds": s, "agent": r.get("agent"), "chars": len(text), "text": text})
        print(pid, ok, s, len(text), flush=True)
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("passed", sum(x["ok"] for x in res), "/", len(res))
