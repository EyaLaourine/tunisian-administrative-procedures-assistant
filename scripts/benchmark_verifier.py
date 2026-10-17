"""Latency of the evidence verifier on this machine.

* numerical check: deterministic, timed over the recorded LLM answers of the development run;
* topic check: one extra local LLM call, made only when the procedure was not identified by the keyword
  rules; timed (warm model) on the questions of the regression and test sets that take this path.

Usage: .venv/Scripts/python scripts/benchmark_verifier.py
"""

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.retriever import CATEGORY_TERMS, routed_retrieve  # noqa: E402
from agents.schemas import RouteRequest  # noqa: E402
from agents.verification import EvidenceVerifier, verify_numbers  # noqa: E402
from backend.agents_api import Agents  # noqa: E402
from backend.settings import get_settings  # noqa: E402
from rag.embeddings import OllamaEmbeddingClient  # noqa: E402
from rag.vector_store import QdrantStore  # noqa: E402

EVAL = ROOT / "data" / "evaluation"


def main() -> None:
    s = get_settings()
    agents = Agents(s)
    embedder = OllamaEmbeddingClient(s.ollama_url, s.embedding_model, s.embedding_dim)
    store = QdrantStore(s.qdrant_url, s.qdrant_api_key)
    verifier = EvidenceVerifier(agents.llm, agents.prompts)

    # Numerical check over recorded answers (passages recovered by retrieval).
    rows = [r for r in json.loads((EVAL / "agent_results_dev_final.json").read_text(encoding="utf-8"))["rows"]
            if r["agent"] == "grounded_answer" and r.get("method") == "llm_grounded"]
    items = {json.loads(l)["id"]: json.loads(l) for l in (EVAL / "eval_set.jsonl").read_text(encoding="utf-8").splitlines() if l}
    num_ms = []
    for r in rows:
        q = items[r["id"]]["question"]
        passages = routed_retrieve(q, agents.router.route(RouteRequest(text=q)), 8, s, embedder, store).passages
        t = time.perf_counter()
        verify_numbers(r["response"].split("📚")[0], passages, q)
        num_ms.append((time.perf_counter() - t) * 1000)

    # Topic check on the LLM-routed questions.
    topic_s = []
    for f in ("regression_set.jsonl", "test_set.jsonl"):
        for line in (EVAL / f).read_text(encoding="utf-8").splitlines():
            q = json.loads(line)["question"]
            route = agents.router.route(RouteRequest(text=q))
            if route.next_agent == "reply" or (route.method == "rules" and route.procedure_category in CATEGORY_TERMS):
                continue
            passages = routed_retrieve(q, route, 8, s, embedder, store).passages
            verifier.check_topic(q, route, passages)  # warm-up / model load
            t = time.perf_counter()
            check = verifier.check_topic(q, route, passages)
            topic_s.append(time.perf_counter() - t)
            print(f"topic {time.perf_counter() - t:5.1f}s consistent={check.consistent} {q[:60]}")
    report = {
        "numeric_check_ms": {"n": len(num_ms), "median": round(statistics.median(num_ms), 2), "max": round(max(num_ms), 2)},
        "topic_check_s": {"n": len(topic_s), "median": round(statistics.median(topic_s), 2), "max": round(max(topic_s), 2)},
    }
    (EVAL / "verifier_latency.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
