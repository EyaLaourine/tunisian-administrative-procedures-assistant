"""Scores replay files of the 728 n8n audit cases with the metrics of report/tables/final_regression.tex.

usage: python scripts/score_replay.py <replay.jsonl> [<replay2.jsonl> ...]

The RNE, guide, targeted-fact, form-instruction, intent and citation rows use the per-case `checks` written by
scripts/final_replay.py. Legal and fee-passage containment uses character 20-gram shingles of the normalised
official supporting passage (threshold 0.8): this reconstruction reproduces the published values on the stored
replays (final candidate 26/30, audited candidate 25/30) and is calibrated on them, not independently derived.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rag.evaluation import norm  # noqa: E402

LEGAL = {"rne-law-2018-52-ar", "rne-decree-2022-298-fees-fr", "rne-decree-law-2022-18-fr", "rne-decree-beneficial-owners",
         "rne-decree-name-reservation", "rne-arrete-2026-35"}
FORMS = {"rne-form-f001-natural-person-registration": 7, "rne-form-f002-legal-entity-registration": 8}
TESTS = {t["id"]: t for t in json.loads((ROOT / "data/evaluation/full_document_coverage.json").read_text(encoding="utf-8"))["tests"]}


def shingle_containment(passage: str, body: str, k: int = 20) -> float:
    p, b = norm(passage), norm(body)
    if len(p) < k:
        return 1.0 if p and p in b else 0.0
    ps = {p[i:i + k] for i in range(len(p) - k + 1)}
    bs = {b[i:i + k] for i in range(len(b) - k + 1)}
    return len(ps & bs) / len(ps)


def score(path: Path) -> dict:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ok_rows = [r for r in rows if r.get("status") == "ok"]

    def kind(k):
        return [r for r in ok_rows if r["kind"] == k]

    def frac(n, d):
        return f"{n}/{d}"

    ch = lambda r: r["checks"]  # noqa: E731
    out = {"cases": len(rows), "status_ok": len(ok_rows)}
    fd, fr = kind("formalities_row_dialogue"), kind("formalities_row")
    out["rne_with_context_exact_row_and_value"] = frac(sum(ch(r)["first_code_in_body"] == ch(r)["asked_code"] and ch(r)["spans_in_body"] == ch(r)["spans_total"] for r in fd), len(fd))
    out["rne_without_context_exact_row_first"] = frac(sum(ch(r)["first_code_in_body"] == ch(r)["asked_code"] for r in fr), len(fr))
    g = kind("guide_scenario")
    out["guide_scenarios_all_spans"] = frac(sum(ch(r)["spans_in_body"] == ch(r)["spans_total"] for r in g), len(g))
    sp = [r for r in ok_rows if ch(r)["spans_total"] > 0]
    out["targeted_official_facts"] = frac(sum(ch(r)["spans_in_body"] == ch(r)["spans_total"] for r in sp), len(sp))

    def containment(kinds, docs):
        sel = [r for r in ok_rows if r["kind"] in kinds and TESTS[r["id"]].get("document_id") in docs]
        hit = sum(shingle_containment(TESTS[r["id"]].get("official_supporting_passage") or "", (r["response"] or {}).get("text") or "") >= 0.8 for r in sel)
        return frac(hit, len(sel))
    out["legal_direct_passage_contained"] = containment({"direct_factual"}, LEGAL)
    out["legal_multilingual_passage_contained"] = containment({"multilingual"}, LEGAL)
    out["fee_service_passage_contained"] = containment({"fee_service"}, LEGAL)
    out["fee_condition_passage_contained"] = containment({"fee_condition"}, LEGAL)
    out["form_instruction_passage_contained"] = containment({"direct_factual"}, set(FORMS))
    out["intent_agrees_with_expectation"] = frac(sum(ch(r)["intent"] == ch(r)["expected_intent"] for r in ok_rows), len(ok_rows))
    cits = sum(len(ch(r)["citations"]) for r in ok_rows)
    out["citation_urls_official"] = frac(sum(len(ch(r)["citations"]) for r in ok_rows if ch(r)["citations_official"]), cits)
    up = kind("upload")
    out["official_uploads_recognised_correct_missing"] = frac(sum(bool(r["response"].get("recognised")) and len(r["response"].get("missing") or []) == FORMS.get(r["response"].get("form_doc_id"), -1) for r in up), len(up))
    bad = kind("upload_error") + kind("unsupported_upload")
    out["corrupt_or_unsupported_uploads_safe"] = frac(sum(not r["response"].get("recognised") for r in bad), len(bad))
    bc = kind("unsupported_birth_certificate")
    out["birth_certificate_refused"] = frac(sum(r["response"].get("agent") == "intent_router" for r in bc), len(bc))
    art16 = [r for r in ok_rows if "16" in r["question"] and TESTS[r["id"]].get("document_id") == "rne-law-2018-52-ar"]
    out["art16_answers_quote_art16"] = frac(sum("الفصل 16" in ((r["response"] or {}).get("text") or "") or "الفصل16" in ((r["response"] or {}).get("text") or "") for r in art16), len(art16))
    sec = sorted(r.get("seconds") or 0 for r in ok_rows)
    out["median_seconds"] = sec[len(sec) // 2] if sec else None
    return out


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(p)
        print(json.dumps(score(Path(p)), indent=1))
