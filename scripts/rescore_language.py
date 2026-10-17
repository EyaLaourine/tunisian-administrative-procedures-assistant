"""Recompute the assistant-text language metric for recorded agent results (no model calls).

The metric was added after some runs had been recorded. Because every run stores its responses, the
metric can be computed on them deterministically, which allows a before/after comparison on the same
recorded outputs.

Usage: .venv/Scripts/python scripts/rescore_language.py agent_results_heldout_before.json [...]
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.corpus import Corpus  # noqa: E402
from agents.language import detect_language  # noqa: E402
from backend.settings import get_settings  # noqa: E402
from rag.evaluation import norm  # noqa: E402

ARABIC = re.compile(r"[؀-ۿ]")
LATIN = re.compile(r"[A-Za-zÀ-ÿ]")


def body(text: str) -> str:
    return text.split("📚")[0]


def language_ok(text: str, lang: str) -> bool:
    b = body(text)
    ar, la = len(ARABIC.findall(b)), len(LATIN.findall(b))
    if lang in ("ar", "derja"):
        return ar > la
    return la > ar and detect_language(b) == lang if lang == "en" else la > ar


def main() -> None:
    s = get_settings()
    corpus = Corpus(s.raw_dir, s.processed_dir)
    doc_text = {d: norm("".join(b["text"] for b in corpus.blocks(d))) for d in corpus.records()}

    def assistant_text(text: str) -> str:
        kept = []
        for line in body(text).splitlines():
            line = re.sub(r"^[^\w\[(]+", "", line.strip())
            for seg in re.split(r" \| |: ", line):
                n = norm(seg)
                if len(n) > 3 and any(n in t for t in doc_text.values()):
                    continue
                kept.append(seg)
        return "\n".join(x for x in kept if x.strip())

    for name in sys.argv[1:]:
        path = ROOT / "data" / "evaluation" / name
        data = json.loads(path.read_text(encoding="utf-8"))
        vals = []
        for r in data["rows"]:
            lang = r["language"]
            own = assistant_text(r["response"])
            r["assistant_language_ok"] = language_ok(own, lang) if own.strip() else None
            if r["assistant_language_ok"] is not None:
                vals.append(r["assistant_language_ok"])
        data["summary"]["assistant_language_consistency"] = {
            "n": len(vals), "rate": round(sum(vals) / len(vals), 3) if vals else None}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        strict = data["summary"]["language_consistency"]["rate"]
        print(f"{name}: strict={strict} assistant_text={data['summary']['assistant_language_consistency']}")


if __name__ == "__main__":
    main()
