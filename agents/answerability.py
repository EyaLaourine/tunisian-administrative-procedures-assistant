"""Answerability gate: decide whether the retrieved official evidence can answer the question.

Two independent signals are combined instead of a single similarity threshold:

1. Procedure classification. When the deterministic keyword rules identified a covered procedure
   (passport, national ID, RNE), the question is in scope and the checklist / answer agents handle
   missing details themselves (they state when the official texts are silent).
2. Lexical evidence support. When the procedure only comes from the LLM fallback or is unknown
   ("general"), the informative words of the question must actually occur in the retrieved official
   passages. Informativeness is the inverse document frequency (IDF) over the indexed corpus; words
   that never occur in the corpus get the maximum IDF, so an unknown topic ("permis de conduire",
   "carte grise") cannot be answered with unrelated passages that merely share generic words.

Embedding similarity alone is not used: cross-lingual dense scores of unrelated passages are often as
high as those of relevant ones in this small corpus (e.g. passport passages for a driving-licence
question).
"""

from dataclasses import dataclass
from pathlib import Path

from agents.retriever import CATEGORY_TERMS, arabizi_terms, entity_terms
from agents.schemas import RouteDecision
from rag.hybrid import _load, tokenize
from rag.retrieval import RetrievedPassage

EVIDENCE_PASSAGES = 5
MIN_SUPPORT = 0.5  # share of the question's IDF mass found in the evidence

# Function words and generic question words (EN, FR, AR, Latin-script Derja); they say nothing about
# which procedure is asked for.
STOPWORDS = set("""
the a an of to for in on at is are was be been what which who whom how much many do does did i me my we our
you your can could should would get need needs needed with from by about and or it its this that these those
when where why there here any some have has had will please tell know want if as than then so not no yes
le la les l un une des de du d et ou en au aux pour par sur dans est sont être etre que qu qui quoi quel quelle
quels quelles comment combien où ou ce cet cette ces mon ma mes ton ta tes son sa ses notre votre nos vos je
tu il elle on nous vous ils elles peut peux puis faut dois doit faire fait obtenir avoir ai as a y s n ne pas
plus moins très tres bien aussi si se me te lui leur leurs quand pourquoi entre avec sans chez
ما هي هو هل كيف كم في من على إلى الى عن أين اين متى ماذا التي الذي الذين و أو او ب ل هذا هذه ذلك تلك لي
chnowa chnoua chnia chniya kifech kifach kifeh 9adech qadech bech bch nheb n7eb el w fel fil mta3 mte3 ya3tik
""".split())


@dataclass
class Answerability:
    answerable: bool
    reason: str  # procedure_keywords | lexical_support | insufficient_evidence | no_evidence
    support: float | None = None


class AnswerabilityGate:
    def __init__(self, chunks_path: Path):
        self.chunks_path = chunks_path

    def _idf(self) -> tuple[dict[str, float], float]:
        _, bm25 = _load(str(self.chunks_path), self.chunks_path.stat().st_mtime)
        return bm25.idf, max(bm25.idf.values(), default=1.0)

    def assess(self, query: str, route: RouteDecision, passages: list[RetrievedPassage]) -> Answerability:
        if not passages:
            return Answerability(False, "no_evidence")
        if route.method == "rules" and route.procedure_category in CATEGORY_TERMS:
            return Answerability(True, "procedure_keywords")
        idf, max_idf = self._idf()
        terms = [t for t in tokenize(" ".join([query, *entity_terms(query, route), *arabizi_terms(query, route)]))
                 if t not in STOPWORDS and (len(t) > 2 or t.isdigit())]
        if not terms:
            return Answerability(False, "insufficient_evidence", 0.0)
        evidence = set(tokenize(" ".join(p.text for p in passages[:EVIDENCE_PASSAGES])))
        total = sum(idf.get(t, max_idf) for t in set(terms))
        found = sum(idf.get(t, max_idf) for t in set(terms) if t in evidence)
        support = found / total if total else 0.0
        if support >= MIN_SUPPORT:
            return Answerability(True, "lexical_support", round(support, 3))
        return Answerability(False, "insufficient_evidence", round(support, 3))
