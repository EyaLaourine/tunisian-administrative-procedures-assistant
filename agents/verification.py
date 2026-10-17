"""Evidence verification gate: topic consistency and numerical-claim support.

Two failure types motivated this module (held-out evaluation, docs/EVALUATION.md):
  H17  a question about an uncovered procedure ("carte grise") was answered with national-ID evidence,
       because shared generic words passed the lexical answerability check;
  H14  an accepted LLM answer stated a fine of "510,000 TND" while the cited Arabic article states
       "fifty thousand dinars" in words.

Topic consistency
  * Procedure identified by the keyword rules: the evidence must come from documents of that procedure
    (source metadata `procedure_category`). The checklist and answer agents only receive such passages,
    so this is checked deterministically and costs nothing.
  * Procedure guessed by the LLM fallback or unknown: a short versioned prompt (`evidence_topic`) asks
    the local LLM whether the retrieved official documents describe the same administrative procedure as
    the question. The JSON verdict is validated; any error or invalid output means refusal.

Numerical claims (deterministic)
  Every number written with digits in an LLM answer must occur in the passages cited by the same
  sentence (or in the question). Source numbers are read both as digits and as number words (French,
  English, Arabic), so that "خمسون ألف دينار" supports 50,000. Citation markers, the sources footer and
  page numbers are not claims. Sentences with unsupported numbers are removed; if no cited sentence
  remains, the answer is refused. No number is ever replaced.
"""

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field

from agents.llm import LLMError, OllamaChatClient
from agents.prompts import PromptLibrary
from agents.retriever import CATEGORY_TERMS
from agents.schemas import RouteDecision
from rag.retrieval import RetrievedPassage

log = logging.getLogger(__name__)

TOPIC_EVIDENCE_PASSAGES = 3
TOPIC_EXCERPT_CHARS = 400

# ---------------------------------------------------------------------- numbers
_ARABIC_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_DIGITS = re.compile(r"\d+(?:[  .,]\d{3})+(?![\d])|\d+(?:[.,]\d+)?")
_CITATION = re.compile(r"\[\d+\]")

_WORDS = {
    # French
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9,
    "dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15, "seize": 16, "vingt": 20,
    "vingts": 20, "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60, "cent": 100, "cents": 100,
    # English
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "hundred": 100,
    # Arabic (normalised: alef variants -> ا, ta marbuta -> ه)
    "واحد": 1, "اثنان": 2, "اثنين": 2, "ثلاث": 3, "ثلاثه": 3, "اربع": 4, "اربعه": 4, "خمس": 5, "خمسه": 5,
    "ست": 6, "سته": 6, "سبع": 7, "سبعه": 7, "ثمان": 8, "ثمانيه": 8, "تسع": 9, "تسعه": 9, "عشر": 10, "عشره": 10,
    "عشرون": 20, "عشرين": 20, "ثلاثون": 30, "ثلاثين": 30, "اربعون": 40, "اربعين": 40, "خمسون": 50, "خمسين": 50,
    "ستون": 60, "ستين": 60, "سبعون": 70, "سبعين": 70, "ثمانون": 80, "ثمانين": 80, "تسعون": 90, "تسعين": 90,
    "مائه": 100, "مئه": 100, "مائتي": 200, "مائتين": 200, "ثلاثمائه": 300, "اربعمائه": 400, "خمسمائه": 500,
}
_SCALES = {"mille": 1000, "thousand": 1000, "الف": 1000, "الاف": 1000, "million": 1_000_000, "مليون": 1_000_000}
_DUALS = {"الفين": 2000, "الفان": 2000, "مليونين": 2_000_000}


def _norm_word(w: str) -> str:
    w = unicodedata.normalize("NFKC", w).lower()
    w = re.sub(r"[ً-ْـ]", "", w)
    w = re.sub("[أإآ]", "ا", w).replace("ة", "ه").replace("ى", "ي")
    return w


def _word_value(w: str) -> tuple[str, int] | None:
    """('unit'|'scale'|'dual', value) for a number word, trying the Arabic conjunction prefix 'و'."""
    for cand in (w, w[1:] if w.startswith("و") and len(w) > 2 else None):
        if not cand:
            continue
        if cand in _WORDS:
            return "unit", _WORDS[cand]
        if cand in _SCALES:
            return "scale", _SCALES[cand]
        if cand in _DUALS:
            return "dual", _DUALS[cand]
    return None


def parse_digits(text: str) -> set[float]:
    text = text.translate(_ARABIC_INDIC).replace("⁄", "/")
    out: set[float] = set()
    for m in _DIGITS.finditer(text):
        raw = m.group(0)
        if re.fullmatch(r"\d+(?:[  .,]\d{3})+", raw):  # thousands separators: 510,000 / 50 000 / 5.000
            out.add(float(re.sub(r"[  .,]", "", raw)))
            # "3.500" may also be a decimal; accept both readings to avoid false alarms
            if raw.count(".") == 1 or raw.count(",") == 1:
                out.add(float(raw.replace(",", ".")))
        else:
            out.add(float(raw.replace(",", ".")))
    return out


def parse_number_words(text: str) -> set[float]:
    """Values of number-word sequences (e.g. 'cinquante dinars', 'خمسون ألف', 'عشرة آلاف')."""
    out: set[float] = set()
    words = re.findall(r"[\w']+", text.replace("-", " "))
    total = current = 0
    active = False
    for raw in words + [""]:
        w = _norm_word(raw)
        v = _word_value(w) if w else None
        if v is None:
            if w in ("et", "and", "و") and active:
                continue
            if active:
                out.add(float(total + current))
            total = current = 0
            active = False
            continue
        kind, value = v
        active = True
        if kind == "unit":
            current = current * value if value == 100 and 0 < current < 10 else current + value
        elif kind == "scale":
            total += max(current, 1) * value
            current = 0
        else:
            total += value
        out.add(float(value))  # each component is also mentioned, e.g. 'ألف' alone
    return out


def evidence_numbers(text: str) -> set[float]:
    return parse_digits(text) | parse_number_words(text)


@dataclass
class NumericCheck:
    text: str  # answer with unsupported sentences removed
    claims: int  # numbers checked
    unsupported: list[str] = field(default_factory=list)
    removed_sentences: int = 0

    @property
    def supported_share(self) -> float | None:
        return None if not self.claims else round(1 - len(self.unsupported) / self.claims, 3)


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?؟])\s+(?=\S)|\n+")


def verify_numbers(answer: str, passages: list[RetrievedPassage], question: str) -> NumericCheck:
    """`answer` uses passage numbers [n] (1-based indices into `passages`)."""
    allowed_q = parse_digits(question)
    by_n = {n: evidence_numbers(p.text) for n, p in enumerate(passages, 1)}
    all_evidence = set().union(*by_n.values()) if by_n else set()
    kept, unsupported, claims, removed = [], [], 0, 0
    for sentence in _SENTENCE_SPLIT.split(answer):
        if not sentence.strip():
            continue
        cited = [int(n) for n in re.findall(r"\[(\d+)\]", sentence) if int(n) in by_n]
        evidence = set().union(*(by_n[n] for n in cited)) if cited else all_evidence
        bad = []
        for m in _DIGITS.finditer(_CITATION.sub(" ", sentence).translate(_ARABIC_INDIC).replace("⁄", "/")):
            values = parse_digits(m.group(0))
            claims += 1
            if not (values & evidence or values & allowed_q):
                bad.append(m.group(0))
        if bad:
            unsupported += bad
            removed += 1
        else:
            kept.append(sentence.strip())
    return NumericCheck(text="\n".join(kept), claims=claims, unsupported=unsupported, removed_sentences=removed)


# ---------------------------------------------------------------------- topic
@dataclass
class TopicCheck:
    consistent: bool
    method: str  # metadata | llm | llm_error | no_evidence
    detail: dict = field(default_factory=dict)


# French verb endings: verbs ("prévoit", "conduire") describe the action, not the subject asked about.
_FR_VERB = re.compile(r"(?:oit|ait|aient|oient|ent|ez|ons|ira|era|ire|oir)$")
_STEM_SUFFIXES = ("ements", "ement", "ations", "ation", "ances", "ance", "euses", "euse", "ables", "able",
                  "aux", "ées", "ée", "és", "é", "es", "s", "e")


def _stem(t: str) -> str:
    for suffix in _STEM_SUFFIXES:
        if len(t) > 5 and t.endswith(suffix):
            return t[: -len(suffix)]
    return t


def _topical(term: str, lang: str) -> bool:
    if lang == "ar":
        return term.startswith("ال") or term.endswith(("ة", "ه"))  # definite or feminine nouns
    return not _FR_VERB.search(term)


class EvidenceVerifier:
    def __init__(self, llm: OllamaChatClient | None, prompts: PromptLibrary, chunks_path=None, topic_check: bool = True):
        self.llm = llm
        self.prompts = prompts
        self.topic_check = topic_check
        self.chunks_path = chunks_path  # corpus vocabulary for the deterministic topic rule

    def _vocabulary(self) -> tuple[set[str], set[str]]:
        from rag.hybrid import _load
        _, bm25 = _load(str(self.chunks_path), self.chunks_path.stat().st_mtime)
        if getattr(self, "_vocab_key", None) != id(bm25):
            self._vocab = set(bm25.idf)
            self._stems = {_stem(v) for v in self._vocab}
            self._vocab_key = id(bm25)
        return self._vocab, self._stems

    def topic_gaps(self, query: str, lang: str) -> list[str]:
        """Topical content words of a French or Arabic question that occur nowhere in the corpus."""
        from agents.answerability import STOPWORDS
        from rag.hybrid import tokenize
        vocab, stems = self._vocabulary()
        terms = [t for t in tokenize(query) if t not in STOPWORDS and len(t) > 2 and not t.isdigit()]
        return [t for t in terms if t not in vocab and _stem(t) not in stems and _topical(t, lang)]

    def check_topic(self, query: str, route: RouteDecision, passages: list[RetrievedPassage]) -> TopicCheck:
        if not passages:
            return TopicCheck(False, "no_evidence")
        if not self.topic_check:
            return TopicCheck(True, "disabled")
        if route.method == "rules" and route.procedure_category in CATEGORY_TERMS:
            categories = {_category(p) for p in passages if _category(p)}
            ok = not categories or categories == {route.procedure_category}
            return TopicCheck(ok, "metadata", {"categories": sorted(categories)})
        # The corpus is written in French and Arabic. For questions in these languages, the corpus vocabulary
        # is a deterministic topic signal: a subject named with words that occur in none of the official
        # documents is not covered. (English and Derja questions differ from the corpus by language, so
        # they go to the LLM verdict.)
        if self.chunks_path is not None and route.language in ("fr", "ar"):
            gaps = self.topic_gaps(query, route.language)
            return TopicCheck(not gaps, "corpus_vocabulary", {"missing_terms": gaps})
        if self.llm is None:
            return TopicCheck(False, "llm_error", {"error": "no llm"})
        spec = self.prompts.get("evidence_topic")
        # The verifier must see the passages the answer would use: the top passages, not one passage per
        # document (several rows of the RNE table are distinct passages of a single document).
        docs = []
        for p in passages[:TOPIC_EVIDENCE_PASSAGES]:
            heading = " > ".join(p.citation.heading_path[-2:])
            first, _, rest = p.text.partition("\n")
            excerpt = rest if " > " in first and rest.strip() else p.text  # drop the heading-path prefix
            docs.append(f"- {p.citation.title} ({p.citation.source_organization}); section: {heading}\n"
                        f"  excerpt: {excerpt[:TOPIC_EXCERPT_CHARS].replace(chr(10), ' ')}")
        try:
            res = self.llm.run(spec, question=query, documents="\n".join(docs))
            data = json.loads(res.text)
            same = data.get("same_procedure")
            if not isinstance(same, bool):
                raise ValueError("same_procedure is not a boolean")
        except (LLMError, ValueError, json.JSONDecodeError, TypeError, AttributeError) as exc:
            log.warning("topic_check_failed", extra={"fields": {"error": type(exc).__name__}})
            return TopicCheck(False, "llm_error", {"error": type(exc).__name__, "prompt_ref": spec.ref})
        return TopicCheck(same, "llm", {
            "question_procedure": str(data.get("question_procedure", ""))[:200],
            "evidence_procedure": str(data.get("evidence_procedure", ""))[:200],
            "prompt_ref": res.prompt_ref, "seconds": res.seconds,
        })


def _category(p: RetrievedPassage) -> str | None:
    """Procedure category of a passage from the source registry, via the citation's document."""
    return getattr(p.citation, "procedure_category", None)
