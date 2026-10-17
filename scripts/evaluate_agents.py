"""Answer-quality evaluation of the production agent chain (in-process, real Qdrant + Ollama).

For every item of data/evaluation/eval_set.jsonl the chain route -> retrieve -> checklist|answer
is executed exactly as n8n workflow 03 does (without the HTTP hops). All checks are deterministic:

  routing          category / intent / language vs. the labels of the item
  citation_valid   every cited doc_id exists in the manifest with the same URL and SHA-256
  citation_support at least one cited document is an expected evidence document (answerable items)
  evidence_found   the response contains a verified evidence span verbatim (normalised)
  faithful         checklist: every quoted item occurs verbatim in the extracted official text;
                   LLM answer: every number in the answer body occurs in the passages given to it
  rejected         unsupported / out-of-scope items: no substantive answer is given
  conflict_flagged conflicting items: the FR/AR discrepancy warning is shown
  language_ok      response body is written in the language (script) of the question

The "rejected" check for LLM answers matches refusal phrases (FR/EN/AR); this is a heuristic and is
reported as such. No LLM is used as a judge.

Usage: .venv/Scripts/python scripts/evaluate_agents.py [--prompt-versions v1,v2] [--tag name]
"""

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.language import detect_language  # noqa: E402
from agents.verification import _DIGITS as DIGIT_CLAIM, evidence_numbers, parse_digits  # noqa: E402
from agents.retriever import routed_retrieve  # noqa: E402
from agents.schemas import ComposeRequest, RouteRequest  # noqa: E402
from backend.agents_api import Agents  # noqa: E402
from backend.settings import get_settings  # noqa: E402
from rag.embeddings import OllamaEmbeddingClient  # noqa: E402
from rag.evaluation import norm  # noqa: E402
from rag.vector_store import QdrantStore  # noqa: E402

EVAL = ROOT / "data" / "evaluation"
ARABIC = re.compile(r"[؀-ۿ]")
LATIN = re.compile(r"[A-Za-zÀ-ÿ]")
NUMBER = re.compile(r"\d+(?:[.,/]\d+)*")
REFUSAL = re.compile(
    r"ne contiennent pas|ne contient pas|pas trouvé|aucune information|not contain|does not contain|do not contain|"
    r"no (?:specific )?(?:mention|information)|could not find|not covered|pas encore couverte|"
    r"لا تتضمن|لم أجد|غير مشمول|لا يوجد|ما لقيتش|موش موجود|can only help|ne peux aider|يمكنني المساعدة فقط|نجم نعاونك كان",
    re.I)


def body(text: str) -> str:
    """Response text without the sources footer and disclaimer."""
    return text.split("📚")[0]


def language_ok(text: str, lang: str) -> bool:
    b = body(text)
    ar, la = len(ARABIC.findall(b)), len(LATIN.findall(b))
    if lang in ("ar", "derja"):
        return ar > la
    return la > ar and detect_language(b) == lang if lang == "en" else la > ar


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-versions", default="", help="grounded_answer versions to compare on answer-routed items")
    ap.add_argument("--tag", default="")
    ap.add_argument("--set", default="eval_set.jsonl", help="eval_set.jsonl (development) or heldout_set.jsonl")
    ap.add_argument("--only", default="", help="comma-separated item ids")
    args = ap.parse_args()

    settings = get_settings()
    agents = Agents(settings)
    embedder = OllamaEmbeddingClient(settings.ollama_url, settings.embedding_model, settings.embedding_dim)
    store = QdrantStore(settings.qdrant_url, settings.qdrant_api_key)
    records = agents.corpus.records()
    doc_text = {d: norm("".join(b["text"] for b in agents.corpus.blocks(d))) for d in records}

    def assistant_text(text: str) -> str:
        """The response without verbatim official quotations (segments found in an official document)."""
        kept = []
        for line in body(text).splitlines():
            line = re.sub(r"^[^\w\[(]+", "", line.strip())  # bullets and emoji markers
            for seg in re.split(r" \| |: ", line):
                n = norm(seg)
                if len(n) > 3 and any(n in t for t in doc_text.values()):
                    continue
                kept.append(seg)
        return "\n".join(s for s in kept if s.strip())

    def verbatim(item: str) -> bool:
        """Every line of a quoted item (bullet markers removed) occurs in one official document."""
        lines = [norm(ln.strip().lstrip("-").strip()) for ln in item.splitlines() if ln.strip()]
        return any(all(ln in text for ln in lines) for text in doc_text.values())
    items = [json.loads(line) for line in (EVAL / args.set).read_text(encoding="utf-8").splitlines() if line]
    if args.only:
        keep = set(args.only.split(","))
        items = [i for i in items if i["id"] in keep]

    def citation_checks(citations) -> tuple[int, int]:
        valid = 0
        for c in citations:
            rec = records.get(c["doc_id"])
            valid += bool(rec and rec.url == c["url"] and rec.sha256 == c["sha256"])
        return valid, len(citations)

    rows = []
    answer_inputs = []  # (item, route, passages) for the prompt comparison
    for item in items:
        t0 = time.perf_counter()
        route = agents.router.route(RouteRequest(text=item["question"]))
        t_route = time.perf_counter() - t0
        passages, out, agent = [], None, "intent_router"
        if route.next_agent != "reply":
            passages = routed_retrieve(item["question"], route, 8, settings, embedder, store).passages
            req = ComposeRequest(query=item["question"], route=route, passages=passages)
            if route.next_agent == "checklist":
                out, agent = agents.checklist.build(req).model_dump(), "checklist_builder"
            else:
                out, agent = agents.answerer.answer(req).model_dump(), "grounded_answer"
                answer_inputs.append((item, route, passages))
        total = time.perf_counter() - t0
        text = out["text"] if out else (route.reply or "")
        citations = out.get("citations", []) if out else []
        expected_docs = {a["doc_id"] for g in item["evidence_groups"] for a in g}
        spans = [a["evidence"] for g in item["evidence_groups"] for a in g if a["evidence"]]
        valid, n_cit = citation_checks(citations)

        row = {
            "id": item["id"], "language": item["language"], "answerability": item["answerability"],
            "expected_category": item["expected_category"], "expected_intent": item["expected_intent"],
            "category": route.procedure_category, "intent": route.intent, "detected_language": route.language,
            "route_method": route.method, "agent": agent, "method": (out or {}).get("method"),
            "category_ok": route.procedure_category == item["expected_category"] if item["expected_category"] else None,
            "intent_ok": route.intent == item["expected_intent"] if item["expected_intent"] else None,
            "language_detect_ok": route.language == item["language"],
            "citations": n_cit, "citations_valid": valid,
            "citation_support": bool(expected_docs & {c["doc_id"] for c in citations}) if expected_docs else None,
            "evidence_found": any(norm(s) in norm(text) for s in spans) if spans else None,
            "language_ok": language_ok(text, item["language"]),
            "assistant_language_ok": (language_ok(own, item["language"]) if (own := assistant_text(text)).strip() else None),
            "router_ms": round(t_route * 1000, 1), "total_ms": round(total * 1000, 1),
            "response": text,
        }
        if agent == "checklist_builder" and out and out.get("sections"):
            items_quoted = [i for s in out["sections"] for i in s["items"]]
            ok = sum(1 for i in items_quoted if verbatim(i))
            row["faithful"] = ok / len(items_quoted)
        elif agent == "grounded_answer" and out and out["method"] == "llm_grounded":
            given = " ".join(p.text for p in passages) + " " + item["question"]
            nums = NUMBER.findall(body(re.sub(r"\[\d+\]", "", text)))
            row["faithful"] = (sum(1 for n in nums if n in given) / len(nums)) if nums else 1.0
            row["unsupported_numbers"] = [n for n in nums if n not in given]
        if agent == "grounded_answer" and out and out["method"] == "llm_grounded":
            # Numerical claim support with number words read in the sources (agents.verification).
            evidence = evidence_numbers(" ".join(p.text for p in passages)) | parse_digits(item["question"])
            claims = [m.group(0) for m in DIGIT_CLAIM.finditer(re.sub(r"\[\d+\]", " ", body(text)))]
            row["numeric_claims"] = len(claims)
            row["numeric_unsupported"] = [c for c in claims if not (parse_digits(c) & evidence)]
        answerable_item = item["answerability"] in ("answerable", "conflicting")
        refused = agent == "intent_router" or bool(out and not out.get("found"))
        if answerable_item:
            row["false_refusal"] = refused
        if item["answerability"] in ("unsupported", "out_of_scope"):
            refused = (agent == "intent_router" or (out and not out.get("found"))
                       or bool(REFUSAL.search(body(text))))
            row["rejected"] = bool(refused)
        if item["answerability"] == "conflicting":
            row["conflict_flagged"] = bool(out and out.get("warnings"))
        rows.append(row)
        print(f"{item['id']:4} {agent:17} {route.procedure_category[:12]:12} {route.intent[:12]:12} "
              f"{row['total_ms']:8.0f}ms ev={row['evidence_found']} faithful={row.get('faithful')} "
              f"rej={row.get('rejected')} lang={row['language_ok']}", flush=True)

    def rate(key, subset=None):
        vals = [r[key] for r in (subset or rows) if r.get(key) is not None]
        return {"n": len(vals), "rate": round(sum(map(float, vals)) / len(vals), 3) if vals else None}

    answerable = [r for r in rows if r["answerability"] in ("answerable", "conflicting")]
    summary = {
        "n_items": len(rows),
        "category_accuracy": rate("category_ok"), "intent_accuracy": rate("intent_ok"),
        "language_detection_accuracy": rate("language_detect_ok"),
        "citation_validity": {"valid": sum(r["citations_valid"] for r in rows), "total": sum(r["citations"] for r in rows)},
        "citation_support": rate("citation_support", answerable),
        "evidence_found": rate("evidence_found", answerable),
        "faithfulness": rate("faithful"),
        "unsupported_rejection": rate("rejected"),
        "false_acceptance_rate": {"n": len([r for r in rows if r.get("rejected") is not None]),
                                  "rate": round(1 - rate("rejected")["rate"], 3) if rate("rejected")["rate"] is not None else None},
        "false_refusal_rate": rate("false_refusal"),
        "numeric_claim_support": {"claims": sum(r.get("numeric_claims", 0) for r in rows),
                                  "unsupported": sum(len(r.get("numeric_unsupported", [])) for r in rows)},
        "conflict_flagged": rate("conflict_flagged"),
        "language_consistency": rate("language_ok"),
        "assistant_language_consistency": rate("assistant_language_ok"),
        "by_agent": {a: {"n": len(v), "median_ms": round(statistics.median(r["total_ms"] for r in v))}
                     for a in {r["agent"] for r in rows} for v in [[r for r in rows if r["agent"] == a]]},
    }
    result = {"summary": summary, "rows": rows}

    if args.prompt_versions and answer_inputs:
        comparison = {}
        for version in args.prompt_versions.split(","):
            agents.prompts.active["grounded_answer"] = version
            vrows = []
            for item, route, passages in answer_inputs:
                t = time.perf_counter()
                res = agents.answerer.answer(ComposeRequest(query=item["question"], route=route, passages=passages))
                given = " ".join(p.text for p in passages) + " " + item["question"]
                nums = NUMBER.findall(body(re.sub(r"\[\d+\]", "", res.text))) if res.method == "llm_grounded" else []
                spans = [a["evidence"] for g in item["evidence_groups"] for a in g if a["evidence"]]
                vrows.append({
                    "id": item["id"], "method": res.method, "seconds": round(time.perf_counter() - t, 1),
                    "accepted": res.method == "llm_grounded",
                    "numbers_faithful": (sum(1 for n in nums if n in given) / len(nums)) if nums else 1.0,
                    "evidence_found": any(norm(s) in norm(res.text) for s in spans) if spans else None,
                    "refusal": bool(REFUSAL.search(body(res.text))),
                    "language_ok": language_ok(res.text, item["language"]),
                    "answerability": item["answerability"], "response": res.text,
                })
                print(f"  {version} {item['id']:4} {res.method:17} {vrows[-1]['seconds']:5.1f}s lang={vrows[-1]['language_ok']}", flush=True)
            comparison[version] = {
                "accepted": rate("accepted", vrows), "numbers_faithful": rate("numbers_faithful", vrows),
                "evidence_found": rate("evidence_found", [r for r in vrows if r["answerability"] == "answerable"]),
                "language_ok": rate("language_ok", vrows),
                "refusal_on_unsupported": rate("refusal", [r for r in vrows if r["answerability"] != "answerable"]),
                "median_seconds": statistics.median(r["seconds"] for r in vrows), "rows": vrows,
            }
        result["prompt_comparison"] = comparison

    out_path = EVAL / f"agent_results{('_' + args.tag) if args.tag else ''}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    if "prompt_comparison" in result:
        for v, c in result["prompt_comparison"].items():
            print(v, {k: c[k] for k in c if k != "rows"})
    print("saved", out_path.relative_to(ROOT))


if __name__ == "__main__":
    main()
