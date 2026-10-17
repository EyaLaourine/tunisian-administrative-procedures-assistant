"""Hybrid retrieval: dense agent retrieval fused with BM25 over the same chunks (reciprocal rank fusion).

Motivation (measured in data/evaluation/): dense BGE-M3 retrieval ranks the 95 near-identical rows of
the RNE formalities table poorly for exact procedure codes ("RNE M 004.03") and entity names
("SUARL"). BM25 over the raw user question rewards these exact tokens. Both lists are restricted to
the routed procedure category, so fusion cannot introduce documents the router excluded.
"""

import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from agents.retriever import CATEGORY_TERMS, LANGUAGE_BONUS, PREFERRED_CHUNK_LANGUAGE, _script_language, arabizi_terms, entity_terms, expand_query
from agents.schemas import RouteDecision
from backend.settings import Settings
from rag.embeddings import EmbeddingClient
from rag.retrieval import Citation, RetrievalFilters, RetrievalRequest, RetrievedPassage, retrieve_by_vector
from rag.vector_store import QdrantStore

# Procedure codes keep their dots ("004.03"); other tokens are word characters.
_TOKEN = re.compile(r"\d+(?:\.\d+)+|\w+", re.UNICODE)
RRF_K = 60
CANDIDATES = 20
BM25_K1, BM25_B = 1.2, 0.75


def tokenize(text: str) -> list[str]:
    import unicodedata
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[ً-ْـ]", "", text)
    return [t for t in _TOKEN.findall(text) if len(t) > 1 or t.isdigit()]


class BM25:
    def __init__(self, docs: list[list[str]]):
        self.docs = docs
        self.n = len(docs)
        self.avgdl = sum(len(d) for d in docs) / max(self.n, 1)
        df = Counter(t for d in docs for t in set(d))
        self.idf = {t: math.log(1 + (self.n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.tf = [Counter(d) for d in docs]

    def scores(self, query: list[str], allowed: list[int]) -> list[tuple[int, float]]:
        out = []
        for i in allowed:
            tf, dl, s = self.tf[i], len(self.docs[i]), 0.0
            for t in query:
                f = tf.get(t)
                if f:
                    s += self.idf[t] * f * (BM25_K1 + 1) / (f + BM25_K1 * (1 - BM25_B + BM25_B * dl / self.avgdl))
            if s > 0:
                out.append((i, s))
        return sorted(out, key=lambda x: x[1], reverse=True)


@lru_cache(maxsize=4)
def _load(path: str, _mtime: float) -> tuple[list[dict], BM25]:
    payloads = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]
    return payloads, BM25([tokenize(p["text"]) for p in payloads])


def _passage_language(p: RetrievedPassage) -> str:
    return p.citation.language if p.citation.language in ("fr", "ar") else _script_language(p.text)


def _passage(payload: dict, score: float) -> RetrievedPassage:
    return RetrievedPassage(
        score=score, text=payload["text"], chunk_id=payload["chunk_id"],
        citation=Citation(
            doc_id=payload["doc_id"], title=payload["title"], source_organization=payload["source_organization"],
            url=payload["url"], official_reference=payload.get("official_reference"),
            publication_date=payload.get("publication_date"), applicability=payload.get("applicability", "unverified"),
            page_start=payload.get("page_start"), page_end=payload.get("page_end"),
            heading_path=payload.get("heading_path") or [], sha256=payload["sha256"],
            language=payload.get("language"), document_type=payload.get("document_type"),
            procedure_category=payload.get("procedure_category"),
        ),
    )


class HybridRetriever:
    """Reciprocal rank fusion of up to three ranked lists, all restricted to the routed category:
      raw      dense retrieval of the user's own words (keeps specific terms dominant)
      expanded the production agent retrieval (bilingual expansion, language preference)
      bm25     lexical retrieval of the user's own words (exact codes and names)
    """

    def __init__(self, settings: Settings, embedder: EmbeddingClient, store: QdrantStore,
                 strategy: str = "structure", components: tuple[str, ...] = ("raw", "expanded", "bm25"),
                 max_per_doc: int | None = None):
        self.settings, self.embedder, self.store, self.strategy = settings, embedder, store, strategy
        self.components = components
        # Caps how many of the top_k results may come from one document, so that the 95 near-identical
        # rows of the RNE formalities table cannot crowd out the legal texts.
        self.max_per_doc = max_per_doc
        self.path = settings.processed_dir / f"chunks_{strategy}.jsonl"

    def _dense(self, query: str, vector: list[float], category: str | None) -> list[RetrievedPassage]:
        filters = RetrievalFilters(procedure_category=category) if category else RetrievalFilters()
        req = RetrievalRequest(query=query[:2000], top_k=CANDIDATES * 2, strategy=self.strategy, filters=filters,
                               min_score=self.settings.retrieval_min_score)
        return retrieve_by_vector(req, vector, self.settings, self.store)

    def retrieve(self, query: str, route: RouteDecision, top_k: int) -> list[RetrievedPassage]:
        payloads, bm25 = _load(str(self.path), self.path.stat().st_mtime)
        category = route.procedure_category if route.procedure_category in CATEGORY_TERMS else None
        lists: list[list[RetrievedPassage]] = []
        texts = [t for c, t in (("raw", query), ("expanded", expand_query(query, route))) if c in self.components]
        vectors = dict(zip(texts, self.embedder.embed(texts))) if texts else {}  # one batched call
        if "raw" in self.components:
            lists.append(self._dense(query, vectors[query], category)[:CANDIDATES])
        if "expanded" in self.components:
            expanded = expand_query(query, route)
            ranked = self._dense(expanded, vectors[expanded], category)
            preferred = PREFERRED_CHUNK_LANGUAGE.get(route.language)
            ranked.sort(key=lambda p: p.score + (LANGUAGE_BONUS if _passage_language(p) == preferred else 0.0),
                        reverse=True)
            lists.append(ranked[:CANDIDATES])
        if "bm25" in self.components:
            allowed = [i for i, p in enumerate(payloads) if category is None or p["procedure_category"] == category]
            # Lexical query: the user's words plus normalised company-type and Arabizi terms.
            lexical_query = " ".join([query, *entity_terms(query, route), *arabizi_terms(query, route)])
            lists.append([_passage(payloads[i], s) for i, s in bm25.scores(tokenize(lexical_query), allowed)[:CANDIDATES]])

        fused: dict[str, float] = {}
        by_id: dict[str, RetrievedPassage] = {}
        for ranked in lists:
            for rank, p in enumerate(ranked, 1):
                fused[p.chunk_id] = fused.get(p.chunk_id, 0.0) + 1 / (RRF_K + rank)
                by_id.setdefault(p.chunk_id, p)
        best, per_doc = [], {}
        for cid in sorted(fused, key=fused.get, reverse=True):
            doc = by_id[cid].citation.doc_id
            if self.max_per_doc and per_doc.get(doc, 0) >= self.max_per_doc:
                continue
            per_doc[doc] = per_doc.get(doc, 0) + 1
            best.append(cid)
            if len(best) == top_k:
                break
        return [by_id[c].model_copy(update={"score": round(fused[c], 5)}) for c in best]


__all__ = ["HybridRetriever", "BM25", "tokenize"]
