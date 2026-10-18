"""Before/after prompt experiments with identical inputs (see data/evaluation/prompt_experiments/README.md).

usage: python scripts/prompt_experiments.py intent_router|dialogue_understanding|translate_items [--limit N]

Calls are sequential and go through agents.llm.OllamaChatClient with the committed prompt files.
B0 prompts are controlled baselines written for this experiment, not historical versions.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.checklist_builder import _parse_numbered, _same_numbers  # noqa: E402
from agents.corpus import Corpus  # noqa: E402
from agents.llm import LLMError, OllamaChatClient  # noqa: E402
from agents.prompts import PromptLibrary, PromptSpec  # noqa: E402

OUT = ROOT / "data" / "evaluation" / "prompt_experiments"
OLLAMA = "http://127.0.0.1:11434"
LLM_MODEL, TRANSLATION_MODEL = "mistral:latest", "translategemma:4b"

CATEGORIES = {"passport", "national_id", "business_registration", "birth_certificate", "general", "none"}
INTENTS = {"required_documents", "fees", "processing_time", "submission_place", "eligibility", "procedure_info",
           "greeting", "out_of_scope"}
ITEM_KEYS = {"photos", "identity_card_copy", "application_form", "old_passport", "residence_proof", "school_proof",
             "payment_receipt", "birth_certificate", "guardian_authorization"}

# Controlled baselines (B0): same output format, model and options as the real prompt; techniques removed.
B0_INTENT = {
    "name": "intent_router", "version": "B0-controlled-baseline", "model_role": "llm",
    "options": {"temperature": 0, "num_predict": 120}, "json_output": True, "system": "",
    "user_template": "Classify this message about Tunisian administrative procedures. Return JSON with keys "
                     "procedure_category (passport, national_id, business_registration, birth_certificate, general, "
                     "none) and intent (required_documents, fees, processing_time, submission_place, eligibility, "
                     "procedure_info, greeting, out_of_scope).\nMessage: {message}",
}
B0_TRANSLATE = {
    "name": "translate_items", "version": "B0-controlled-baseline", "model_role": "translation",
    "options": {"temperature": 0, "num_predict": 1200}, "json_output": False, "system": "",
    "user_template": "Translate this text from {source_language_name} into {target_language_name}.\n\n{items}",
}


def client() -> OllamaChatClient:
    return OllamaChatClient(OLLAMA, LLM_MODEL, TRANSLATION_MODEL, timeout=600)


def environment() -> dict:
    tags = httpx.get(OLLAMA + "/api/tags", timeout=10).json()["models"]
    return {"ollama_version": httpx.get(OLLAMA + "/api/version", timeout=10).json()["version"],
            "models": {m["name"]: m["digest"][:12] for m in tags if m["name"] in (LLM_MODEL, TRANSLATION_MODEL)},
            "started_at": datetime.now(timezone.utc).isoformat()}


def run(llm: OllamaChatClient, spec: PromptSpec, **values: str) -> dict:
    try:
        r = llm.run(spec, **values)
        return {"text": r.text, "seconds": r.seconds, "truncated": r.truncated, "error": None}
    except LLMError as exc:
        return {"text": "", "seconds": None, "truncated": False, "error": type(exc).__name__}


def parse_json(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def median(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 2) if xs else None


# --------------------------------------------------------------------------------------------- intent router
def intent_router(limit: int | None) -> dict:
    lib, llm = PromptLibrary(ROOT / "prompts"), client()
    specs = {"B0": PromptSpec.model_validate(B0_INTENT), "v1": lib.get("intent_router", "v1")}
    rows = [json.loads(line) for line in (ROOT / "data/evaluation/eval_set.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = rows[:limit] if limit else rows
    records = []
    for row in rows:
        rec = {"id": row["id"], "language": row["language"], "question": row["question"],
               "expected": {"procedure_category": row["expected_category"], "intent": row["expected_intent"]}}
        for label, spec in specs.items():
            out = run(llm, spec, message=row["question"])
            data = parse_json(out["text"])
            cat = data.get("procedure_category") if isinstance(data, dict) else None
            intent = data.get("intent") if isinstance(data, dict) else None
            out.update(json_valid=isinstance(data, dict), enum_valid=cat in CATEGORIES and intent in INTENTS,
                       category_ok=cat == row["expected_category"], intent_ok=intent == row["expected_intent"])
            rec[label] = out
        records.append(rec)
        print(rec["id"], {k: (rec[k]["category_ok"], rec[k]["intent_ok"]) for k in specs}, flush=True)

    def summary(label, subset):
        n = len(subset)
        return {"n": n,
                "json_valid": round(sum(r[label]["json_valid"] for r in subset) / n, 3),
                "enum_valid": round(sum(r[label]["enum_valid"] for r in subset) / n, 3),
                "category_accuracy": round(sum(r[label]["category_ok"] for r in subset) / n, 3),
                "intent_accuracy": round(sum(r[label]["intent_ok"] for r in subset) / n, 3),
                "both_correct": round(sum(r[label]["category_ok"] and r[label]["intent_ok"] for r in subset) / n, 3),
                "median_seconds": median([r[label]["seconds"] for r in subset])}

    langs = sorted({r["language"] for r in records})
    return {"records": records, "summary": {label: {"all": summary(label, records),
                                                    **{lang: summary(label, [r for r in records if r["language"] == lang]) for lang in langs}}
                                            for label in specs}}


# ------------------------------------------------------------------------------------ dialogue understanding
def _item_set(items):
    return {(i.get("key"), bool(i.get("available"))) for i in items if isinstance(i, dict)}


def dialogue_understanding(limit: int | None) -> dict:
    lib, llm = PromptLibrary(ROOT / "prompts"), client()
    specs = {v: lib.get("dialogue_understanding", v) for v in ("v1", "v2", "v3")}
    schema = specs["v3"].response_schema
    rows = [json.loads(line) for line in (OUT / "dialogue_messages.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = rows[:limit] if limit else rows
    records = []
    for row in rows:
        rec = {"id": row["id"], "language": row["language"], "message": row["message"], "expected": row["expected"]}
        exp_items = _item_set(row["expected"]["items"])
        for label, spec in specs.items():
            out = run(llm, spec, message=row["message"])
            data = parse_json(out["text"])
            items = data.get("items", []) if isinstance(data, dict) else []
            items = items if isinstance(items, list) else []
            got = _item_set(items)
            evid = [i.get("evidence") for i in items if isinstance(i, dict)]
            for name in ("application", "residence"):
                fact = data.get(name) if isinstance(data, dict) else None
                if isinstance(fact, dict):
                    evid.append(fact.get("evidence"))
            schema_ok = isinstance(data, dict) and _schema_ok(data, schema)
            out.update(json_valid=isinstance(data, dict), schema_valid=schema_ok,
                       evidence_total=len(evid), evidence_exact=sum(isinstance(e, str) and e != "" and e in row["message"] for e in evid),
                       tp=len(got & exp_items), fp=len(got - exp_items), fn=len(exp_items - got),
                       application=(data.get("application") or {}).get("value") if isinstance(data, dict) and isinstance(data.get("application"), dict) else None,
                       residence=(data.get("residence") or {}).get("value") if isinstance(data, dict) and isinstance(data.get("residence"), dict) else None,
                       quantity_errors=sum(1 for i in items if isinstance(i, dict) and i.get("quantity") not in (None,)
                                           and not any(e.get("key") == i.get("key") and e.get("quantity") == i.get("quantity") for e in row["expected"]["items"])))
            rec[label] = out
        records.append(rec)
        print(rec["id"], {k: (rec[k]["tp"], rec[k]["fp"], rec[k]["fn"], rec[k]["schema_valid"]) for k in specs}, flush=True)

    def summary(label):
        tp = sum(r[label]["tp"] for r in records); fp = sum(r[label]["fp"] for r in records); fn = sum(r[label]["fn"] for r in records)
        ev_total = sum(r[label]["evidence_total"] for r in records); ev_ok = sum(r[label]["evidence_exact"] for r in records)
        no_fact = [r for r in records if not r["expected"]["items"]]
        facts = [(r, n) for r in records for n in ("application", "residence") if n in r["expected"]]
        return {"n": len(records), "json_valid": sum(r[label]["json_valid"] for r in records),
                "schema_valid": sum(r[label]["schema_valid"] for r in records),
                "item_precision": round(tp / (tp + fp), 3) if tp + fp else None,
                "item_recall": round(tp / (tp + fn), 3) if tp + fn else None,
                "evidence_exact_substring": f"{ev_ok}/{ev_total}",
                "spurious_items_on_messages_without_items": sum(r[label]["fp"] for r in no_fact),
                "quantity_errors": sum(r[label]["quantity_errors"] for r in records),
                "application_residence_correct": f"{sum(r[label][n] == r['expected'][n] for r, n in facts)}/{len(facts)}",
                "median_seconds": median([r[label]["seconds"] for r in records])}

    return {"records": records, "summary": {label: summary(label) for label in specs}}


def _schema_ok(data: dict, schema: dict) -> bool:
    """Minimal structural check of the v3 response schema (keys, enums, types); no external dependency."""
    allowed_top = set(schema["properties"])
    if set(data) - allowed_top or "items" not in data or not isinstance(data["items"], list):
        return False
    for i in data["items"]:
        if not isinstance(i, dict) or set(i) != {"key", "available", "quantity", "evidence"}:
            return False
        if i["key"] not in ITEM_KEYS or not isinstance(i["available"], bool) or not (i["quantity"] is None or isinstance(i["quantity"], int)):
            return False
    for name, values in (("application", {"first_time", "renewal", "loss", "modification", "pilgrimage"}), ("residence", {"tunisia", "abroad"})):
        if name in data:
            f = data[name]
            if not isinstance(f, dict) or set(f) != {"value", "evidence"} or f["value"] not in values:
                return False
    return True


# ---------------------------------------------------------------------------------------- translate items
def translate_items(limit: int | None) -> dict:
    lib, llm = PromptLibrary(ROOT / "prompts"), client()
    specs = {"B0": PromptSpec.model_validate(B0_TRANSLATE), "v1": lib.get("translate_items", "v1")}
    corpus = Corpus(ROOT / "data" / "raw", ROOT / "data" / "processed")
    cases = [(doc, sc) for doc in ("interior-passport-guide-fr", "interior-national-id-guide-fr") for sc in corpus.scenarios(doc)]
    cases = cases[:limit] if limit else cases
    records = []
    for doc, sc in cases:
        lines = [sc.title] + [i for s in sc.sections for i in s.items]
        numbered = "\n".join(f"{n}. {line.replace(chr(10), ' ')}" for n, line in enumerate(lines, 1))
        rec = {"doc_id": doc, "scenario_index": sc.index, "title": sc.title, "lines": len(lines), "source": numbered}
        for label, spec in specs.items():
            out = run(llm, spec, items=numbered, source_language_name="French", target_language_name="English")
            parsed = _parse_numbered(out["text"], len(lines))
            numbers_ok = parsed is not None and all(_same_numbers(a, b) for a, b in zip(lines, parsed))
            out.update(structure_valid=parsed is not None, numbers_preserved=numbers_ok, accepted=numbers_ok)
            rec[label] = out
        records.append(rec)
        print(doc, sc.index, {k: rec[k]["accepted"] for k in specs}, flush=True)
    return {"records": records, "summary": {label: {
        "n": len(records), "structure_valid": sum(r[label]["structure_valid"] for r in records),
        "accepted_by_production_validator": sum(r[label]["accepted"] for r in records),
        "truncated": sum(r[label]["truncated"] for r in records),
        "median_seconds": median([r[label]["seconds"] for r in records])} for label in specs}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("experiment", choices=["intent_router", "dialogue_understanding", "translate_items"])
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    env = environment()
    started = time.perf_counter()
    result = globals()[args.experiment](args.limit)
    result["config"] = {**env, "llm_model": LLM_MODEL, "translation_model": TRANSLATION_MODEL,
                        "limit": args.limit, "wall_seconds": round(time.perf_counter() - started, 1),
                        "note": "B0 = controlled baseline written 2026-10-18 for this experiment; not a historical prompt."}
    OUT.mkdir(parents=True, exist_ok=True)
    suffix = f"_limit{args.limit}" if args.limit else ""
    path = OUT / f"{args.experiment}_results{suffix}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=1))
    print("written", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
