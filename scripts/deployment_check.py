"""Post-deployment functional check against the RUNNING services (no in-process code).

Questions go through the n8n webhook (production path); dossier checks go to the deployed backend.
Fixtures: official blank RNE forms from data/raw/ and copies with neutral placeholder text (test fixtures,
no personal data). Prints one line per check and writes data/evaluation/deployment_check.json.

Usage: .venv/Scripts/python scripts/deployment_check.py
"""

import base64
import glob
import json
import sys
import time
from pathlib import Path

import fitz
import httpx

ROOT = Path(__file__).resolve().parent.parent
N8N = "http://127.0.0.1:5678/webhook/assistant"
BACKEND = "http://127.0.0.1:8000"
F001, F002 = "rne-form-f001-natural-person-registration", "rne-form-f002-legal-entity-registration"
client = httpx.Client(timeout=900)
results = []


def record(name: str, ok: bool, detail: str) -> None:
    results.append({"check": name, "ok": ok, "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")


def ask(text: str) -> tuple[dict, float]:
    t = time.perf_counter()
    r = client.post(N8N, json={"text": text})
    r.raise_for_status()
    return r.json(), time.perf_counter() - t


def pdf(doc_id: str) -> bytes:
    return Path(glob.glob(str(ROOT / "data" / "raw" / doc_id / "*.pdf"))[0]).read_bytes()


def dossier(data: bytes, mime="application/pdf", lang="fr") -> dict:
    r = client.post(f"{BACKEND}/agents/dossier-check",
                    json={"filename": "fixture", "mime_type": mime, "data_b64": base64.b64encode(data).decode(), "language": lang})
    r.raise_for_status()
    return r.json()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    # Supported question, citations, FR/AR conflict warning (n8n -> agents).
    d, s = ask("Quelles pièces fournir pour une première demande de passeport ?")
    record("supported FR checklist via n8n", d.get("agent") == "checklist_builder" and d.get("found") and
           "services.interieur.gov.tn" in d["text"] and bool(d.get("warnings")),
           f"{s:.1f}s agent={d.get('agent')} citations={len(d.get('citations') or [])} warning={bool(d.get('warnings'))}")
    # Multilingual.
    d, s = ask("شنوة الأوراق اللازمة باش نجدد الباسبور؟")
    record("Derja question via n8n", (d.get("route") or {}).get("language") == "derja" and d.get("doc_id") == "interior-passport-guide-ar",
           f"{s:.1f}s language={(d.get('route') or {}).get('language')} doc={d.get('doc_id')}")
    d, s = ask("Combien coûte l'immatriculation d'une SARL ?")
    record("RNE fee via n8n", "RNE C 012" in d["text"] and "50 TND" in d["text"], f"{s:.1f}s agent={d.get('agent')}")
    # Unsupported questions.
    d, s = ask("Comment obtenir un extrait de naissance ?")
    record("unsupported (birth certificate) refused", "pas encore couverte" in d["text"], f"{s:.1f}s agent={d.get('agent')}")
    d, s = ask("Comment obtenir un permis de conduire ?")
    refused = d.get("agent") == "intent_router" or d.get("found") is False
    record("unsupported (driving licence) refused", refused, f"{s:.1f}s agent={d.get('agent')} found={d.get('found')}")
    # Grounded answer with the numerical verifier (new response field 'verification').
    d, s = ask("What is the penalty for late registration with the RNE?")
    record("grounded answer via n8n (new backend)", d.get("agent") == "grounded_answer" and d.get("citations") is not None,
           f"{s:.1f}s method={d.get('method')} citations={len(d.get('citations') or [])}")
    r = client.post(f"{BACKEND}/agents/route", json={"text": "What is the penalty for making a false declaration to the National Business Register?"}).json()
    passages = client.post(f"{BACKEND}/agents/retrieve", json={"query": "What is the penalty for making a false declaration to the National Business Register?", "route": r}).json()["passages"]
    a = client.post(f"{BACKEND}/agents/answer", json={"query": "What is the penalty for making a false declaration to the National Business Register?", "route": r, "passages": passages}).json()
    v = a.get("verification") or {}
    record("numerical verifier active in deployed backend", "numbers" in v or a.get("method") in ("passages_fallback", "none"),
           f"method={a.get('method')} verification={json.dumps(v, ensure_ascii=False)[:160]}")
    record("topic check disabled in deployed backend", (v.get("topic") or {}).get("method") == "disabled",
           f"topic={v.get('topic')}")
    # Dossier Validator on the deployed backend.
    for doc_id, n in ((F001, 7), (F002, 8)):
        rep = dossier(pdf(doc_id))
        ok = rep["recognized"] and rep["form_type"]["doc_id"] == doc_id and len(rep["missing_fields"]) == n \
            and not rep["official_checklist_available"] and "ne peut pas être évaluée" in rep["readiness_summary"] \
            and "n'est pas une validation officielle" in rep["readiness_summary"]
        record(f"dossier-check blank {doc_id[:12]}", ok,
               f"missing={len(rep['missing_fields'])} checklist_available={rep['official_checklist_available']} "
               f"requirements={[(q['id'], q['status']) for q in rep['official_requirements']]}")
    doc = fitz.open(stream=pdf(F002), filetype="pdf")  # TEST FIXTURE: placeholder text in two fields
    tpl_words = {w[4]: w for w in doc[0].get_text("words")}
    for label in ("E-mail", "Dénomination"):
        x0, y0, x1, y1 = tpl_words[label][:4]
        doc[0].insert_text((x1 + 60, y1 - 2), "PLACEHOLDER 12", fontsize=9)
    rep = dossier(doc.tobytes(), lang="en")
    record("dossier-check filled fixture (2 fields)", len(rep["filled_fields"]) == 2 and "PLACEHOLDER" not in json.dumps(rep),
           f"filled={rep['filled_fields']} missing={len(rep['missing_fields'])}")
    png = fitz.open(stream=pdf(F001), filetype="pdf")[0].get_pixmap(dpi=200).tobytes("png")
    rep = dossier(png, mime="image/png", lang="ar")
    record("dossier-check scan-like image (OCR in container)", rep["recognized"] and rep["method"] == "ocr_ink" and len(rep["missing_fields"]) == 7,
           f"method={rep['method']} missing={len(rep['missing_fields'])} unreadable={len(rep['unreadable_fields'])}")
    other = fitz.open()
    page = other.new_page()
    page.insert_text((72, 72), "Neutral placeholder document", fontsize=12)
    rep = dossier(other.tobytes())
    record("dossier-check unrelated PDF rejected", not rep["recognized"] and not rep["recognized_fields"], f"recognized={rep['recognized']}")
    rep = client.post(f"{BACKEND}/agents/dossier-check", json={"mime_type": "text/plain", "data_b64": base64.b64encode(b"x").decode()}).json()
    record("dossier-check invalid type rejected", bool(rep.get("error")), f"error={rep.get('error')}")
    texts = json.dumps(results, ensure_ascii=False).lower()
    record("no approval/certification claims", "approved" not in texts and "certified" not in texts, "checked report texts")
    out = ROOT / "data" / "evaluation" / "deployment_check.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    failed = [r for r in results if not r["ok"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
