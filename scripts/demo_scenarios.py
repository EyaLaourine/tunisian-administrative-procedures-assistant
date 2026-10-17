"""Run the demonstration scenarios through the demo interface proxy -> REAL n8n workflow 03 -> backend.

Inputs are questions from the verified evaluation set and the official blank RNE forms. Each run records
the exact input, expected behaviour, observed behaviour, sources and time into docs/demo_fallback/:
  scenarios.json        structured results
  outputs/<id>.txt      the assistant text exactly as returned (official content only; no personal data)

Usage (demo interface running on 127.0.0.1:8090):
  .venv\\Scripts\\python.exe scripts\\demo_scenarios.py
"""

import base64
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
UI = "http://127.0.0.1:8090"
OUT = ROOT / "docs" / "demo_fallback"
F001 = ROOT / "data/raw/rne-form-f001-natural-person-registration/dbfa1f815312_RNE-F-001_declation_immatriculation_personne_physique.pdf"

SCENARIOS = [
    {"id": "S1", "title": "Supported question in French (official citations)", "eval_id": "P01",
     "ask": {"text": "Quelles pièces fournir pour une première demande de passeport ?"},
     "expected": "Checklist Builder quotes the official 'Pièces à fournir' section verbatim, cites the Ministry of the Interior pages and warns about the FR/AR stamp-duty discrepancy.",
     "check": lambda d: d.get("agent") == "checklist_builder" and d.get("citations") and d.get("warnings")},
    {"id": "S2", "title": "Supported question in English", "eval_id": "P02",
     "ask": {"text": "What documents are needed to renew a Tunisian passport?"},
     "expected": "Checklist in English (validated FR->EN translation of the official items, or the French original with a note if validation fails), with citations.",
     "check": lambda d: d.get("agent") == "checklist_builder" and d.get("citations")},
    {"id": "S3a", "title": "Tunisian Derja question (Arabic script)", "eval_id": "P04",
     "ask": {"text": "شنوة الأوراق اللازمة باش نجدد الباسبور؟"},
     "expected": "Detected as Derja; the official Arabic passport page is quoted with Derja labels.",
     "check": lambda d: (d.get("route") or {}).get("language") == "derja" and d.get("doc_id") == "interior-passport-guide-ar"},
    {"id": "S3b", "title": "Tunisian Derja question (Latin script)", "eval_id": "P05",
     "ask": {"text": "chnowa el wra9 eli lezmin bech nejjedd el passbor?"},
     "expected": "Latin-script Derja detected; passport checklist from the official sources.",
     "check": lambda d: (d.get("route") or {}).get("language") == "derja" and d.get("agent") == "checklist_builder"},
    {"id": "S4", "title": "Unsupported administrative question safely refused", "eval_id": "B01",
     "ask": {"text": "Comment obtenir un extrait de naissance ?"},
     "expected": "Reported as not covered (the only source opts out of AI use); no procedure invented.",
     "check": lambda d: d.get("agent") == "intent_router" and "pas encore couverte" in d.get("text", "")},
    {"id": "S5", "title": "Official RNE F-001 upload in Form Check mode", "eval_id": None,
     "upload": {"mode": "form_check", "language": "fr"},
     "expected": "Form recognised (RNE-F-001); 7 fields listed as empty.",
     "check": lambda d: d.get("agent") == "form_helper" and d.get("recognised") and len(d.get("missing") or []) == 7},
    {"id": "S6", "title": "Same form in Dossier Validation mode", "eval_id": None,
     "upload": {"mode": "dossier", "language": "fr"},
     "expected": "Readiness report: 7 missing fields; e-mail and mobile mandatory per the form (quoted); supporting-document list unavailable, so completeness cannot be assessed; never certified.",
     "check": lambda d: d.get("agent") == "dossier_validator" and d["report"]["dossier"]["completeness_certified"] is False
     and d["report"]["dossier"]["official_checklist_available"] is False},
    {"id": "S7", "title": "Optional: numerical evidence verifier", "eval_id": "RN1 (= held-out H14)",
     "ask": {"text": "What is the penalty for making a false declaration to the National Business Register?"},
     "expected": "If the model states a figure that is not in the cited article (observed: 510,000 TND for 'خمسون ألف دينار'), the answer is refused; a supported answer would be shown with its citation. LLM output can vary.",
     "check": lambda d: d.get("agent") == "grounded_answer"},
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    (OUT / "outputs").mkdir(parents=True, exist_ok=True)
    client = httpx.Client(timeout=900)
    status = client.get(f"{UI}/api/status").json()
    results = {"status_before": status, "scenarios": []}
    for s in SCENARIOS:
        t = time.perf_counter()
        if "ask" in s:
            r = client.post(f"{UI}/api/ask", json=s["ask"])
            shown_input = s["ask"]["text"]
        else:
            payload = {"filename": F001.name, "mime_type": "application/pdf",
                       "data_b64": base64.b64encode(F001.read_bytes()).decode(), **s["upload"]}
            r = client.post(f"{UI}/api/upload", json=payload)
            shown_input = f"{F001.name} (official blank form), mode={s['upload']['mode']}"
        seconds = round(time.perf_counter() - t, 1)
        d = r.json()
        ok = r.status_code == 200 and bool(s["check"](d))
        sources = sorted({c["url"] for c in (d.get("citations") or []) if c.get("url")}) or ([d["form_url"]] if d.get("form_url") else [])
        observed = {"agent": d.get("agent"), "language": (d.get("route") or {}).get("language"), "method": d.get("method"),
                    "missing_fields": len(d.get("missing") or []) if "missing" in d else None,
                    "warnings": d.get("warnings"), "first_line": (d.get("text") or "").splitlines()[0][:160] if d.get("text") else None}
        (OUT / "outputs" / f"{s['id']}.txt").write_text(d.get("text") or json.dumps(d, ensure_ascii=False), encoding="utf-8")
        results["scenarios"].append({"id": s["id"], "title": s["title"], "eval_id": s["eval_id"], "input": shown_input,
                                     "expected": s["expected"], "observed": observed, "sources": sources,
                                     "seconds": seconds, "pass": ok, "output_file": f"docs/demo_fallback/outputs/{s['id']}.txt"})
        print(f"{'PASS' if ok else 'FAIL'} {s['id']:4} {seconds:5.1f}s agent={observed['agent']} | {observed['first_line']}")
    (OUT / "scenarios.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    failed = [x for x in results["scenarios"] if not x["pass"]]
    print(f"{len(results['scenarios']) - len(failed)}/{len(results['scenarios'])} scenarios passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
