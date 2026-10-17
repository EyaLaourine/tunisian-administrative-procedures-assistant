"""Add false-refusal and numerical-claim-support metrics to result files recorded before these metrics
existed (no generation is repeated).

* false refusal: the recorded response is one of the assistant's refusal messages (any language) or a
  router-only reply, for an answerable item;
* numerical claim support: digits in recorded LLM answers are checked against the passages of the same
  question, recovered by re-running the deterministic routing + retrieval of the current code.

Usage: .venv/Scripts/python scripts/rescore_verification.py agent_results_regression_before.json [...]
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents import i18n  # noqa: E402
from agents.retriever import routed_retrieve  # noqa: E402
from agents.schemas import RouteRequest  # noqa: E402
from agents.verification import _DIGITS, evidence_numbers, parse_digits  # noqa: E402
from backend.agents_api import Agents  # noqa: E402
from backend.settings import get_settings  # noqa: E402
from rag.embeddings import OllamaEmbeddingClient  # noqa: E402
from rag.vector_store import QdrantStore  # noqa: E402

REFUSAL_KEYS = ["not_found", "insufficient_evidence", "uncovered_category", "out_of_scope", "code_not_found",
                "topic_mismatch", "unsupported_claim"]


def main() -> None:
    settings = get_settings()
    agents = Agents(settings)
    embedder = OllamaEmbeddingClient(settings.ollama_url, settings.embedding_model, settings.embedding_dim)
    store = QdrantStore(settings.qdrant_url, settings.qdrant_api_key)
    refusals = [i18n.STRINGS[k][lang].split("{")[0][:40] for k in REFUSAL_KEYS for lang in ("en", "fr", "ar", "derja")]
    for name in sys.argv[1:]:
        path = ROOT / "data" / "evaluation" / name
        data = json.loads(path.read_text(encoding="utf-8"))
        items = {}
        for f in ("eval_set.jsonl", "heldout_set.jsonl", "regression_set.jsonl", "test_set.jsonl"):
            for line in (ROOT / "data" / "evaluation" / f).read_text(encoding="utf-8").splitlines():
                if line:
                    r = json.loads(line)
                    items[r["id"]] = r
        claims = unsupported = 0
        for row in data["rows"]:
            text = row["response"]
            if row["answerability"] in ("answerable", "conflicting"):
                row["false_refusal"] = row["agent"] == "intent_router" or any(text.startswith(r) for r in refusals)
            if row["agent"] == "grounded_answer" and row.get("method") == "llm_grounded":
                q = items[row["id"]]["question"]
                route = agents.router.route(RouteRequest(text=q))
                passages = routed_retrieve(q, route, 8, settings, embedder, store).passages
                evidence = evidence_numbers(" ".join(p.text for p in passages)) | parse_digits(q)
                found = [m.group(0) for m in _DIGITS.finditer(re.sub(r"\[\d+\]", " ", text.split("📚")[0]))]
                row["numeric_claims"] = len(found)
                row["numeric_unsupported"] = [c for c in found if not (parse_digits(c) & evidence)]
                claims += len(found)
                unsupported += len(row["numeric_unsupported"])
        s = data["summary"]
        fr = [r["false_refusal"] for r in data["rows"] if r.get("false_refusal") is not None]
        s["false_refusal_rate"] = {"n": len(fr), "rate": round(sum(fr) / len(fr), 3) if fr else None}
        rej = s["unsupported_rejection"]
        s["false_acceptance_rate"] = {"n": rej["n"], "rate": round(1 - rej["rate"], 3) if rej["rate"] is not None else None}
        s["numeric_claim_support"] = {"claims": claims, "unsupported": unsupported}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(name, {k: s[k] for k in ("false_acceptance_rate", "false_refusal_rate", "numeric_claim_support")})


if __name__ == "__main__":
    main()
