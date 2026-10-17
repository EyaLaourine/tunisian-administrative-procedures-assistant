"""Grounded Answer agent: free-form questions answered strictly from retrieved official passages.

The LLM output is accepted only if it cites at least one passage and every cited number exists.
Otherwise the agent falls back to quoting the top passages verbatim, so the user always receives
verifiable official text rather than an unsupported answer.
"""

import logging
import re

from agents import i18n
from agents.answerability import AnswerabilityGate
from agents.verification import EvidenceVerifier, verify_numbers
from agents.checklist_builder import sources_footer
from agents.language import LANGUAGE_NAMES
from agents.llm import LLMError, OllamaChatClient
from agents.prompts import PromptLibrary
from agents.schemas import AnswerResult, ComposeRequest
from rag.retrieval import RetrievedPassage

log = logging.getLogger(__name__)

MAX_PASSAGES = 5
MAX_PASSAGE_CHARS = 1500
FALLBACK_PASSAGES = 2
FALLBACK_CHARS = 700


class GroundedAnswerer:
    def __init__(self, llm: OllamaChatClient | None, prompts: PromptLibrary, gate: AnswerabilityGate | None = None,
                 verifier: EvidenceVerifier | None = None):
        self.llm = llm
        self.prompts = prompts
        self.gate = gate
        self.verifier = verifier

    def answer(self, req: ComposeRequest) -> AnswerResult:
        lang = req.route.language
        passages = _dedupe(req.passages)[:MAX_PASSAGES]
        if not passages:
            return AnswerResult(text=i18n.t("not_found", lang), found=False, method="none")
        if self.gate is not None and not self.gate.assess(req.query, req.route, passages).answerable:
            # Refuse rather than answer (or quote) passages that do not address the question.
            return AnswerResult(text=i18n.t("insufficient_evidence", lang), found=False, method="none")
        verification: dict = {}
        if self.verifier is not None:
            topic = self.verifier.check_topic(req.query, req.route, passages)
            verification["topic"] = {"consistent": topic.consistent, "method": topic.method, **topic.detail}
            if not topic.consistent:
                return AnswerResult(text=i18n.t("topic_mismatch", lang), found=False, method="none",
                                    verification=verification)

        spec = self.prompts.get("grounded_answer")
        if self.llm is not None:
            numbered = "\n\n".join(
                f"[{n}] ({p.citation.title}; {' > '.join(p.citation.heading_path[-2:])})\n{p.text[:MAX_PASSAGE_CHARS]}"
                for n, p in enumerate(passages, 1)
            )
            try:
                res = self.llm.run(spec, passages=numbered, question=req.query, language_name=LANGUAGE_NAMES[lang])
                cited = _cited_numbers(res.text)
                if cited and cited <= set(range(1, len(passages) + 1)):
                    text = _trim_incomplete(res.text) if res.truncated else res.text
                    if self.verifier is not None:
                        num = verify_numbers(text, passages, req.query)
                        verification["numbers"] = {"claims": num.claims, "unsupported": num.unsupported,
                                                   "removed_sentences": num.removed_sentences}
                        text = num.text
                        cited = _cited_numbers(text)
                        if not cited:
                            # Nothing verifiable is left: refuse rather than invent a replacement figure.
                            return AnswerResult(text=i18n.t("unsupported_claim", lang), found=False, method="none",
                                                prompt_ref=res.prompt_ref, model=res.model, seconds=res.seconds,
                                                verification=verification)
                    text, used, pages = _renumber_by_document(text, passages, cited)
                    return AnswerResult(text="\n".join([text] + sources_footer(lang, used, pages)), found=True,
                                        method="llm_grounded", citations=used, prompt_ref=res.prompt_ref,
                                        model=res.model, seconds=res.seconds, verification=verification or None)
                log.info("answer_rejected", extra={"fields": {"reason": "citations", "prompt": spec.ref}})
            except LLMError as exc:
                log.warning("answer_llm_failed", extra={"fields": {"error": type(exc).__name__}})

        top = passages[:FALLBACK_PASSAGES]
        lines = [i18n.t("answer_fallback", lang)]
        for n, p in enumerate(top, 1):
            lines += ["", f"[{n}] {p.text[:FALLBACK_CHARS].strip()}{'…' if len(p.text) > FALLBACK_CHARS else ''}"]
        cites = [p.citation for p in top]
        return AnswerResult(text="\n".join(lines + sources_footer(lang, cites)), found=True,
                            method="passages_fallback", citations=cites, prompt_ref=spec.ref)


def _renumber_by_document(text: str, passages: list[RetrievedPassage], cited: set[int]):
    """One source entry per cited document: passage numbers are remapped and repeats collapsed."""
    docs: list[str] = []
    mapping: dict[int, int] = {}
    citations, pages = [], {}
    for n in sorted(cited):
        c = passages[n - 1].citation
        if c.doc_id not in docs:
            docs.append(c.doc_id)
            citations.append(c)
        mapping[n] = docs.index(c.doc_id) + 1
        if c.page_start is not None and c.page_start not in pages.setdefault(c.doc_id, []):
            pages[c.doc_id].append(c.page_start)
    text = re.sub(r"\[(\d+)\]", lambda m: f"[{mapping.get(int(m.group(1)), m.group(1))}]", text)
    # "[1], [1], and [1]" -> "[1]"
    text = re.sub(r"(\[(\d+)\])(?:(?:\s*,\s*(?:and\s+|et\s+)?|\s+(?:and|et|و)\s+|\s*)\[\2\])+", r"\1", text)
    return text, citations, {k: sorted(v) for k, v in pages.items()}


def _trim_incomplete(text: str) -> str:
    """Drops a trailing sentence cut off by the generation limit."""
    cut = max(text.rfind(ch) for ch in (".", "؟", "?", "!", "\n", "]"))
    return text[: cut + 1].rstrip() if cut > len(text) // 2 else text


def _cited_numbers(text: str) -> set[int]:
    return {int(n) for n in re.findall(r"\[(\d+)\]", text)}


def _dedupe(passages: list[RetrievedPassage]) -> list[RetrievedPassage]:
    seen, out = set(), []
    for p in passages:
        if p.chunk_id not in seen:
            seen.add(p.chunk_id)
            out.append(p)
    return out
