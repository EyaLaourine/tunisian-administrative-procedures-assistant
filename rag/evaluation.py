"""Retrieval evaluation: relevance judgement and ranking metrics.

Relevance is decided deterministically. A retrieved chunk is relevant to an evidence group when it
comes from one of the group's documents and contains that alternative's verbatim evidence span
(after Unicode/whitespace/diacritic normalisation). An alternative without an evidence span accepts
any chunk of its document (document-level relevance, used only for ambiguous questions).

A question may have several evidence groups (e.g. both conflicting official amounts). Each group
lists equivalent alternatives (e.g. the same requirement in the French and Arabic guides).
"""

import re
import statistics
import unicodedata
from collections import defaultdict
from dataclasses import dataclass

_DIACRITICS = re.compile(r"[ً-ْـٰ]")
_SPACES = re.compile(r"\s+")


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("’", "'").replace(" ", " ")
    text = _DIACRITICS.sub("", text)
    # Arabic PDF extraction inserts spurious spaces inside words; spaces are not significant here.
    return _SPACES.sub("", text).lower()


@dataclass(frozen=True)
class Alternative:
    doc_id: str
    evidence: str | None = None

    def matches(self, doc_id: str, text: str) -> bool:
        return doc_id == self.doc_id and (self.evidence is None or norm(self.evidence) in norm(text))


def group_hit_ranks(groups: list[list[Alternative]], retrieved: list[tuple[str, str]]) -> list[int | None]:
    """For each evidence group, the 1-based rank of the first relevant retrieved chunk (or None)."""
    ranks: list[int | None] = []
    for group in groups:
        rank = next((i for i, (doc_id, text) in enumerate(retrieved, 1)
                     if any(a.matches(doc_id, text) for a in group)), None)
        ranks.append(rank)
    return ranks


def question_metrics(ranks: list[int | None], ks: tuple[int, ...] = (1, 3, 5)) -> dict[str, float]:
    """Recall@k = share of evidence groups found in the top k; Hit@5 = at least one group found;
    MRR@5 = reciprocal rank of the first relevant chunk within the top 5."""
    out = {f"recall@{k}": sum(1 for r in ranks if r is not None and r <= k) / len(ranks) for k in ks}
    first = min((r for r in ranks if r is not None), default=None)
    out["hit@5"] = 1.0 if first is not None and first <= 5 else 0.0
    out["mrr@5"] = 1.0 / first if first is not None and first <= 5 else 0.0
    return out


def aggregate(rows: list[dict], keys: tuple[str, ...] = ("recall@1", "recall@3", "recall@5", "mrr@5", "hit@5")) -> dict:
    if not rows:
        return {"n": 0}
    out = {"n": len(rows)}
    for k in keys:
        out[k] = round(statistics.mean(r[k] for r in rows), 3)
    lat = [r["latency_ms"] for r in rows if "latency_ms" in r]
    if lat:
        out["latency_ms_median"] = round(statistics.median(lat), 1)
        out["latency_ms_p95"] = round(sorted(lat)[max(0, int(len(lat) * 0.95) - 1)], 1)
    return out


def breakdown(rows: list[dict], field: str) -> dict[str, dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r[field]].append(r)
    return {k: aggregate(v) for k, v in sorted(groups.items())}
