"""Generate LaTeX tables for report/ from the recorded evaluation results (no manual transcription).

Usage: .venv/Scripts/python scripts/make_report_tables.py
Writes report/tables/*.tex.
"""

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "data" / "evaluation"
OUT = ROOT / "report" / "tables"

# (results file, config key, label, chunks, latency comparable)
ROWS = [
    ("final", "dense_structure", "Dense, raw query (Phase 1)", "structure", True),
    ("final", "dense_recursive", "Dense, raw query (Phase 1)", "recursive", True),
    ("before", "agent_structure", "Agent retriever (Phase 2, before)", "structure", False),
    ("final", "agent_structure", "Agent + term normalisation", "structure", True),
    ("final", "agent_recursive", "Agent + term normalisation", "recursive", True),
    ("final", "hybrid_structure", "Hybrid RRF (raw+expanded+BM25)", "structure", True),
    ("final", "hybridcap2_structure", "Hybrid RRF + max 2 chunks/doc", "structure", True),
    ("final", "hybridcap2_recursive", "Hybrid RRF + max 2 chunks/doc", "recursive", True),
    ("final", "hybridcap3_structure", "Hybrid RRF + max 3 chunks/doc", "structure", True),
]
SELECTED = "hybridcap2_structure"


def load(name: str) -> dict:
    return json.loads((EVAL / name).read_text(encoding="utf-8"))


def f3(x) -> str:
    return "--" if x is None else f"{x:.3f}"


def retrieval_table(files: dict) -> str:
    lines = [r"\begin{tabular}{@{}llrrrrrr@{}}", r"\toprule",
             r"Configuration & Chunks & R@1 & R@3 & R@5 & MRR@5 & Hit@5 & ms \\", r"\midrule"]
    for src, key, label, chunks, timed in ROWS:
        o = files[src][key]["overall"]
        ms = f"{o['latency_ms_median']:.0f}" if timed else "--"
        cells = [f3(o[m]) for m in ("recall@1", "recall@3", "recall@5", "mrr@5", "hit@5")]
        if src == "final" and key == SELECTED:
            cells = [r"\textbf{" + c + "}" for c in cells]
        lines.append(f"{label} & {chunks} & {' & '.join(cells)} & {ms} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def breakdown_table(results: dict, keys: list[str], field: str, names: dict[str, str]) -> str:
    groups = sorted({g for k in keys for g in results[k][field]})
    head = " & ".join(names.get(k, k) for k in keys)
    lines = [r"\begin{tabular}{@{}lr" + "r" * len(keys) + r"@{}}", r"\toprule",
             f"Subset & $n$ & {head} \\\\", r"\midrule"]
    for g in groups:
        n = results[keys[0]][field][g]["n"]
        vals = " & ".join(f3(results[k][field].get(g, {}).get("hit@5")) for k in keys)
        lines.append(f"{g.replace('_', ' ')} & {n} & {vals} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def script_chart(results: dict, keys: list[tuple[str, str]], field: str) -> str:
    """pgfplots coordinates of Hit@5 by query language/script."""
    order = ["fr", "en", "ar", "derja", "derja-latin"]
    out = []
    for key, legend in keys:
        coords = " ".join(f"({g},{results[key][field][g]['hit@5']:.3f})" for g in order if g in results[key][field])
        out.append(r"\addplot coordinates {" + coords + r"}; \addlegendentry{" + legend + "}")
    return "\n".join(out)


def chunk_stats_table() -> str:
    lines = [r"\begin{tabular}{@{}lrrr@{}}", r"\toprule", r"Strategy & Chunks & Mean chars & Median chars \\", r"\midrule"]
    for s in ("structure", "recursive"):
        rows = [json.loads(line) for line in (ROOT / "data" / "processed" / f"chunks_{s}.jsonl").read_text(encoding="utf-8").splitlines() if line]
        lens = [len(r["text"]) for r in rows]
        lines.append(f"{s} & {len(rows)} & {statistics.mean(lens):.0f} & {statistics.median(lens):.0f} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def agent_table(summary: dict) -> str:
    def rate(key):
        v = summary[key]
        return f"{v['rate']:.3f} & {v['n']}" if v.get("rate") is not None else "-- & 0"
    cv = summary["citation_validity"]
    rows = [
        ("Category routing accuracy", rate("category_accuracy")),
        ("Intent routing accuracy", rate("intent_accuracy")),
        ("Language detection accuracy", rate("language_detection_accuracy")),
        ("Citation validity (URL and SHA-256 match manifest)", f"{cv['valid'] / cv['total']:.3f} & {cv['total']}"),
        ("Citation support (an expected document is cited)", rate("citation_support")),
        ("Verified evidence span present in response", rate("evidence_found")),
        ("Faithfulness (verbatim items / numbers in sources)", rate("faithfulness")),
        ("Unsupported / out-of-scope rejection", rate("unsupported_rejection")),
        ("Source conflict flagged", rate("conflict_flagged")),
        ("Response language consistency (strict, whole text)", rate("language_consistency")),
    ]
    lines = [r"\begin{tabular}{@{}lrr@{}}", r"\toprule", r"Check (deterministic) & Rate & $n$ \\", r"\midrule"]
    lines += [f"{a} & {b} \\\\" for a, b in rows]
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def latency_table(summary: dict) -> str:
    lines = [r"\begin{tabular}{@{}lrr@{}}", r"\toprule", r"Final agent & $n$ & Median ms \\", r"\midrule"]
    for agent, v in sorted(summary["by_agent"].items()):
        lines.append(f"{agent.replace('_', ' ')} & {v['n']} & {v['median_ms']} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def prompt_table(runs: list[tuple[str, dict]]) -> str:
    """One row per (run, prompt version); versions compared within a run share the same passages."""
    lines = [r"\begin{tabular}{@{}llrrrrr@{}}", r"\toprule",
             r"Run & Prompt & Accepted & Numbers in sources & Evidence span & Language OK & Median s \\", r"\midrule"]
    for run, comparison in runs:
        for v, c in comparison.items():
            lines.append(f"{run} & grounded\\_answer@{v} & {f3(c['accepted']['rate'])} & {f3(c['numbers_faithful']['rate'])} & "
                         f"{f3(c['evidence_found']['rate'])} & {f3(c['language_ok']['rate'])} & {c['median_seconds']:.1f} \\\\")
        lines.append(r"\addlinespace[1pt]")
    lines = lines[:-1] + [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def heldout_table() -> str:
    """Development vs held-out metrics, before and after the final reliability changes."""
    need = ["retrieval_results_improved.json", "retrieval_results_heldout.json", "agent_results_final.json",
            "agent_results_dev_after.json", "agent_results_heldout_before.json", "agent_results_heldout_after.json"]
    if not all((EVAL / n).exists() for n in need):
        return ""
    rd, rh = load(need[0]), load(need[1])
    db, da, hb, ha = (load(n)["summary"] for n in need[2:])

    def rate(summary, key):
        v = summary.get(key) or {}
        return f3(v.get("rate")) if isinstance(v, dict) and "rate" in v else "--"

    def cit(summary):
        c = summary["citation_validity"]
        return f"{c['valid']}/{c['total']}"

    rows = [
        ("Hit@5, dense raw query", f3(rd["dense_structure"]["overall"]["hit@5"]), "", f3(rh["dense_structure"]["overall"]["hit@5"]), ""),
        ("Hit@5, Phase-2 agent retriever", f3(rd["agent_structure"]["overall"]["hit@5"]), "", f3(rh["agent_structure"]["overall"]["hit@5"]), ""),
        ("Hit@5, hybrid + cap (production)", f3(rd["hybridcap2_structure"]["overall"]["hit@5"]), "", f3(rh["hybridcap2_structure"]["overall"]["hit@5"]), ""),
        ("MRR@5, hybrid + cap (production)", f3(rd["hybridcap2_structure"]["overall"]["mrr@5"]), "", f3(rh["hybridcap2_structure"]["overall"]["mrr@5"]), ""),
        ("Citation validity", cit(db), cit(da), cit(hb), cit(ha)),
        ("Unsupported-answer rejection", rate(db, "unsupported_rejection"), rate(da, "unsupported_rejection"),
         rate(hb, "unsupported_rejection"), rate(ha, "unsupported_rejection")),
        ("Faithfulness", rate(db, "faithfulness"), rate(da, "faithfulness"), rate(hb, "faithfulness"), rate(ha, "faithfulness")),
        ("Language consistency, strict", rate(db, "language_consistency"), rate(da, "language_consistency"),
         rate(hb, "language_consistency"), rate(ha, "language_consistency")),
        ("Language consistency, assistant text", rate(db, "assistant_language_consistency"), rate(da, "assistant_language_consistency"),
         rate(hb, "assistant_language_consistency"), rate(ha, "assistant_language_consistency")),
        ("Verified evidence span present", rate(db, "evidence_found"), rate(da, "evidence_found"),
         rate(hb, "evidence_found"), rate(ha, "evidence_found")),
    ]
    lines = [r"\begin{tabular}{@{}lrrrr@{}}", r"\toprule",
             r"& \multicolumn{2}{c}{Development (84)} & \multicolumn{2}{c}{Held-out (20)} \\",
             r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}",
             r"Metric & before & after & before & after \\", r"\midrule"]
    lines += [" & ".join(r) + r" \\" for r in rows]
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def verification_table() -> str:
    """False acceptance / false refusal / numeric support, without vs with the evidence verifier."""
    sets = [  # (label, without verifier, with verifier)
        ("Development (84)", "agent_results_dev_after.json", "agent_results_dev_final.json"),
        ("Regression (15)", "agent_results_regression_noverif.json", "agent_results_regression_final.json"),
        ("Held-out (20)$^a$", "agent_results_heldout_after.json", "agent_results_heldout_final.json"),
        ("Test 1 (14)$^b$", "agent_results_test_noverif.json", "agent_results_test_second.json"),
        ("Test 2 (12)$^c$", "agent_results_test2_noverif.json", "agent_results_test2_once.json"),
    ]
    if not all((EVAL / f).exists() for _, a, b in sets for f in (a, b)):
        return ""

    def cells(name):
        sm = load(name)["summary"]
        fa, fr = sm.get("false_acceptance_rate", {}), sm.get("false_refusal_rate", {})
        num = sm.get("numeric_claim_support", {})
        cv = sm["citation_validity"]
        return [f"{f3(fa.get('rate'))}", f"{f3(fr.get('rate'))}",
                f"{num.get('unsupported', '--')}/{num.get('claims', '--')}", f"{cv['valid']}/{cv['total']}"]

    lines = [r"\begin{tabular}{@{}lrrrrrrrr@{}}", r"\toprule",
             r"& \multicolumn{2}{c}{False acceptance} & \multicolumn{2}{c}{False refusal} & "
             r"\multicolumn{2}{c}{Unsupp.\ numbers} & \multicolumn{2}{c}{Valid citations} \\",
             r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}\cmidrule(lr){8-9}",
             r"Set & off & on & off & on & off & on & off & on \\", r"\midrule"]
    for label, off, on in sets:
        a, b = cells(off), cells(on)
        lines.append(" & ".join([label] + [x for pair in zip(a, b) for x in pair]) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    final = load("retrieval_results_improved.json")
    files = {"final": final, "before": load("retrieval_results_final.json")}
    (OUT / "retrieval.tex").write_text(retrieval_table(files), encoding="utf-8")
    (OUT / "chunks.tex").write_text(chunk_stats_table(), encoding="utf-8")
    keys = ["dense_structure", "agent_structure", SELECTED]
    names = {"dense_structure": "Dense", "agent_structure": "Agent", SELECTED: "Hybrid+cap"}
    (OUT / "by_script.tex").write_text(breakdown_table(final, keys, "by_query_script", names), encoding="utf-8")
    (OUT / "parallel.tex").write_text(breakdown_table(final, keys, "parallel_by_language", names), encoding="utf-8")
    (OUT / "by_category.tex").write_text(breakdown_table(final, keys, "by_category", names), encoding="utf-8")
    chart = [("dense_structure", "Dense (raw query)"), ("agent_structure", "Agent"), (SELECTED, "Hybrid + cap")]
    (OUT / "script_chart.tex").write_text(script_chart(final, chart, "parallel_by_language"), encoding="utf-8")
    agent_file = next((n for n in ("agent_results_dev_after.json", "agent_results_final.json", "agent_results_hybrid.json") if (EVAL / n).exists()), None)
    if agent_file:
        agents = load(agent_file)
        (OUT / "agents.tex").write_text(agent_table(agents["summary"]), encoding="utf-8")
        (OUT / "latency.tex").write_text(latency_table(agents["summary"]), encoding="utf-8")
    runs = [(label, load(n)["prompt_comparison"]) for label, n in (("A", "agent_results_hybrid.json"), ("B", "agent_results_prompt_v3.json"))
            if (EVAL / n).exists() and "prompt_comparison" in load(n)]
    if runs:
        (OUT / "prompts.tex").write_text(prompt_table(runs), encoding="utf-8")
    held = heldout_table()
    if held:
        (OUT / "heldout.tex").write_text(held, encoding="utf-8")
    ver = verification_table()
    if ver:
        (OUT / "verification.tex").write_text(ver, encoding="utf-8")
    print("tables written:", sorted(p.name for p in OUT.glob("*.tex")))


if __name__ == "__main__":
    main()
