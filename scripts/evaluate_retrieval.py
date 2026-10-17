"""Retrieval evaluation on data/evaluation/eval_set.jsonl (same questions for every configuration).

Configurations (retrieval depth k = 5 everywhere):
  dense_<strategy>   raw user query -> BGE-M3 -> Qdrant, no filter (Phase 1 /retrieve)
  agent_<strategy>   production RAG Retriever agent: routed query expansion, procedure filter,
                     language-preference re-ranking, min_score
  multi_<strategy>   RRF of dense(raw query) + agent(expanded query), same procedure filter
  lexexp_<strategy>  RRF of agent(expanded query) + BM25(raw query)
  hybrid_<strategy>  RRF of dense(raw) + agent(expanded) + BM25(raw)   (see rag/hybrid.py)

Routes come from the production Intent Router (keyword rules + LLM fallback) and are cached in
data/evaluation/routes.json so every configuration sees identical routing.

Usage: .venv/Scripts/python scripts/evaluate_retrieval.py [--configs dense_structure,agent_structure,...]
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.intent_router import IntentRouter  # noqa: E402
from agents.llm import OllamaChatClient  # noqa: E402
from agents.prompts import PromptLibrary  # noqa: E402
from agents.retriever import agent_retrieve  # noqa: E402
from agents.schemas import RouteDecision, RouteRequest  # noqa: E402
from backend.settings import get_settings  # noqa: E402
from rag.embeddings import OllamaEmbeddingClient  # noqa: E402
from rag.evaluation import Alternative, aggregate, breakdown, group_hit_ranks, question_metrics  # noqa: E402
from rag.retrieval import RetrievalRequest, retrieve  # noqa: E402
from rag.vector_store import QdrantStore  # noqa: E402

EVAL = ROOT / "data" / "evaluation"


class CachedEmbedder:
    """Deterministic embeddings are reused across configurations to save GPU time."""

    def __init__(self, inner):
        self.inner, self.dim, self.cache = inner, inner.dim, {}

    def embed(self, texts):
        missing = [t for t in texts if t not in self.cache]
        if missing:
            for t, v in zip(missing, self.inner.embed(missing)):
                self.cache[t] = v
        return [self.cache[t] for t in texts]
K = 5


def load_items(set_file: str = "eval_set.jsonl") -> list[dict]:
    rows = [json.loads(line) for line in (EVAL / set_file).read_text(encoding="utf-8").splitlines() if line]
    # Only items whose relevance labels are verified (or document-level for ambiguous items) are scored.
    return [r for r in rows if r["evidence_groups"] and r["verification_status"] != "UNVERIFIED"]


def load_routes(items: list[dict], settings, refresh: bool, set_file: str = "eval_set.jsonl") -> dict[str, RouteDecision]:
    path = EVAL / "routes.json"
    cached = {} if refresh or not path.exists() else json.loads(path.read_text(encoding="utf-8"))
    prompts = PromptLibrary(settings.prompts_path)
    llm = OllamaChatClient(settings.ollama_url, settings.llm_model, settings.translation_model, settings.llm_timeout_seconds)
    router = IntentRouter(llm, prompts, settings.intent_llm_fallback)
    all_items = [json.loads(line) for line in (EVAL / set_file).read_text(encoding="utf-8").splitlines() if line]
    for r in all_items:
        if r["id"] not in cached:
            t = time.perf_counter()
            decision = router.route(RouteRequest(text=r["question"]))
            cached[r["id"]] = {**decision.model_dump(), "router_ms": round((time.perf_counter() - t) * 1000, 1)}
    path.write_text(json.dumps(cached, ensure_ascii=False, indent=1), encoding="utf-8")
    return {k: RouteDecision.model_validate({f: v for f, v in d.items() if f != "router_ms"}) for k, d in cached.items()}


def make_retrievers(settings, embedder, store):
    def dense(strategy):
        def run(item, route):
            req = RetrievalRequest(query=item["question"], top_k=K, strategy=strategy)
            return [(p.citation.doc_id, p.text) for p in retrieve(req, settings, embedder, store)]
        return run

    def agent(strategy):
        def run(item, route):
            res = agent_retrieve(item["question"], route, K, settings, embedder, store, strategy=strategy)
            return [(p.citation.doc_id, p.text) for p in res.passages]
        return run

    def hybrid(strategy, components, cap=None):
        from rag.hybrid import HybridRetriever
        h = HybridRetriever(settings, embedder, store, strategy, components, max_per_doc=cap)

        def run(item, route):
            return [(p.citation.doc_id, p.text) for p in h.retrieve(item["question"], route, K)]
        return run

    variants = {"multi": ("raw", "expanded"), "hybrid": ("raw", "expanded", "bm25"), "lexexp": ("expanded", "bm25")}
    out = {}
    for s in ("structure", "recursive"):
        out[f"dense_{s}"] = dense(s)
        out[f"agent_{s}"] = agent(s)
        for v, comps in variants.items():
            out[f"{v}_{s}"] = hybrid(s, comps)
        for cap in (2, 3):
            out[f"hybridcap{cap}_{s}"] = hybrid(s, variants["hybrid"], cap)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", default="dense_structure,dense_recursive,agent_structure,agent_recursive")
    ap.add_argument("--refresh-routes", action="store_true")
    ap.add_argument("--tag", default="", help="suffix for the results file")
    ap.add_argument("--set", default="eval_set.jsonl", help="eval_set.jsonl (development) or heldout_set.jsonl")
    ap.add_argument("--cache-embeddings", action="store_true",
                    help="reuse query embeddings across configurations (quality only; latency is then not comparable)")
    args = ap.parse_args()

    settings = get_settings()
    embedder = OllamaEmbeddingClient(settings.ollama_url, settings.embedding_model, settings.embedding_dim)
    if args.cache_embeddings:
        embedder = CachedEmbedder(embedder)
    store = QdrantStore(settings.qdrant_url, settings.qdrant_api_key)
    items = load_items(args.set)
    routes = load_routes(items, settings, args.refresh_routes, args.set)
    retrievers = make_retrievers(settings, embedder, store)
    embedder.embed(["warm-up"])  # load the embedding model before timing

    results = {}
    for name in args.configs.split(","):
        run = retrievers[name]
        run(items[0], routes[items[0]["id"]])  # warm-up (lazy indexes, caches)
        rows = []
        for item in items:
            groups = [[Alternative(a["doc_id"], a["evidence"]) for a in g] for g in item["evidence_groups"]]
            t = time.perf_counter()
            retrieved = run(item, routes[item["id"]])
            latency = (time.perf_counter() - t) * 1000
            ranks = group_hit_ranks(groups, retrieved)
            rows.append({"id": item["id"], "language": item["language"], "category": item["expected_category"],
                         "query_script": item["language"] + ("-latin" if item.get("script") == "latin" else ""),
                         "parallel_group": item.get("parallel_group") or "-",
                         "answerability": item["answerability"], "ranks": ranks,
                         "retrieved_docs": [d for d, _ in retrieved], "latency_ms": round(latency, 1),
                         **question_metrics(ranks)})
        results[name] = {"overall": aggregate(rows), "by_language": breakdown(rows, "language"),
                         "by_category": breakdown(rows, "category"),
                         "by_query_script": breakdown(rows, "query_script"),
                         "parallel_by_language": breakdown([r for r in rows if r["parallel_group"] != "-"], "query_script"),
                         "by_parallel_group": breakdown([r for r in rows if r["parallel_group"] != "-"], "parallel_group"),
                         "rows": rows}
        o = results[name]["overall"]
        print(f"{name:18} n={o['n']} R@1={o['recall@1']:.3f} R@3={o['recall@3']:.3f} R@5={o['recall@5']:.3f} "
              f"MRR@5={o['mrr@5']:.3f} Hit@5={o['hit@5']:.3f} median={o['latency_ms_median']}ms")
        misses = [r["id"] for r in rows if r["hit@5"] == 0]
        print(f"{'':18} misses@5: {misses}")
    for r in results.values():
        r["latency_comparable"] = not args.cache_embeddings
    out = EVAL / f"retrieval_results{('_' + args.tag) if args.tag else ''}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
