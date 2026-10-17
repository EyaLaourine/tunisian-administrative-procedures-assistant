"""Answerability gate and multilingual rendering (no running services needed)."""

import pytest

from agents.answer import GroundedAnswerer
from agents.answerability import AnswerabilityGate
from agents.checklist_builder import _localize_row, _same_numbers
from agents.language import detect_language
from agents.prompts import PromptLibrary
from agents.schemas import ComposeRequest, RouteDecision
from backend.settings import REPO_ROOT, get_settings
from rag.retrieval import Citation, RetrievedPassage


@pytest.fixture(scope="module")
def gate() -> AnswerabilityGate:
    path = get_settings().processed_dir / "chunks_structure.jsonl"
    if not path.exists():
        pytest.skip("chunks not built")
    return AnswerabilityGate(path)


def _route(method="llm", category="general", lang="fr", intent="procedure_info") -> RouteDecision:
    return RouteDecision(language=lang, intent=intent, procedure_category=category, next_agent="answer", method=method)


def _passage(text: str, doc="interior-passport-guide-fr") -> RetrievedPassage:
    cit = Citation(doc_id=doc, title="t", source_organization="o", url="https://x", official_reference=None,
                   publication_date=None, applicability="unverified", page_start=None, page_end=None,
                   heading_path=[], sha256="0" * 64)
    return RetrievedPassage(score=0.7, text=text, chunk_id=text[:20], citation=cit)


# Passage texts below are quoted from the official passport guide and the RNE decree-law 2022-18.
PASSPORT = _passage("Pièces à fournir - Copie de la Carte d'identité nationale avec présentation de l'originale")
DECREE = _passage("Décret-loi n° 2022-18 du 29 mars 2022, portant remise des pénalités de retard relatives au "
                  "Registre national des entreprises.", doc="rne-decree-law-2022-18-fr")


def test_procedure_identified_by_rules_is_answerable(gate):
    a = gate.assess("Quelles pièces pour le passeport ?", _route(method="rules", category="passport"), [PASSPORT])
    assert a.answerable and a.reason == "procedure_keywords"


def test_unknown_topic_with_unrelated_evidence_is_refused(gate):
    a = gate.assess("Comment obtenir un permis de conduire ?", _route(), [PASSPORT])
    assert not a.answerable and a.reason == "insufficient_evidence"


def test_llm_routed_question_supported_by_evidence_is_answerable(gate):
    a = gate.assess("Que prévoit le décret-loi n° 2022-18 ?", _route(), [DECREE])
    assert a.answerable and a.reason == "lexical_support"


def test_ambiguous_or_empty_questions_are_refused(gate):
    assert not gate.assess("How much does it cost?", _route(lang="en"), [PASSPORT]).answerable
    assert not gate.assess("Que prévoit le décret-loi ?", _route(), []).answerable


def test_answerer_refuses_without_calling_the_llm(gate):
    class ExplodingLLM:
        def run(self, *a, **k):
            raise AssertionError("LLM must not be called")

    answerer = GroundedAnswerer(ExplodingLLM(), PromptLibrary(REPO_ROOT / "prompts"), gate)
    res = answerer.answer(ComposeRequest(query="Comment obtenir un permis de conduire ?", route=_route(), passages=[PASSPORT]))
    assert not res.found and not res.citations and "contacter l'administration" in res.text


def test_rne_row_labels_are_localised_official_lines_verbatim():
    row = "Code procédure: RNE C 012\nRedevance demandée: cinquante dinars (50 TND)\nDélais: Trente jours"
    assert _localize_row(row, "fr") == row.splitlines()
    en = _localize_row(row, "en")
    assert en == ["Procedure code — Code procédure: RNE C 012", "Fee — Redevance demandée: cinquante dinars (50 TND)",
                  "Deadline — Délais: Trente jours"]
    assert all(official in local for official, local in zip(row.splitlines(), _localize_row(row, "ar")))


def test_translation_validation_accepts_fraction_slash():
    assert _same_numbers("format 3⁄4 cm", "3/4 cm format")
    assert not _same_numbers("format 3⁄4 cm", "3/5 cm format")


def test_latin_derja_detection_with_common_verbs():
    assert detect_language("kifech nekhou madhmoun wleda?") == "derja"
    assert detect_language("Comment obtenir un extrait de naissance ?") == "fr"
