"""Evidence verification gate: numerical claims and topic consistency (no running services needed).

Passage texts are quoted from the official corpus (Law 2018-52, RNE formalities table, Ministry of the
Interior guides). Generated answers are scripted through a fake LLM.
"""

import json

import pytest

from agents.answer import GroundedAnswerer
from agents.checklist_builder import ChecklistBuilder
from agents.corpus import Corpus
from agents.llm import LLMResult
from agents.prompts import PromptLibrary
from agents.schemas import ComposeRequest, RouteDecision
from agents.verification import EvidenceVerifier, parse_digits, parse_number_words, verify_numbers
from backend.settings import REPO_ROOT, get_settings
from rag.retrieval import Citation, RetrievedPassage

PROMPTS = PromptLibrary(REPO_ROOT / "prompts")

# Official wording (Law 2018-52 art. 55 and art. 53; RNE table; passport guide).
ART55 = "الفصل55 يعاقب بالسجن مدة خمس سنوات وبخطية قدرها خمسون ألف دينار كل من تعمد تق ديم تصريح مخالف للحقيقة"
ART53 = "الفصل53 يعاقب بخطية من ألف دينار إلى خمسة آلاف دينار كل شخص تقاعس عن إتمام إحدى العمليات المذكورة"
C012 = "Code procédure: RNE C 012\nRedevance demandée: cinquante dinars (50 TND)\nDélais: Trente jours à compter de la date de signature des statuts"
ID_RENEW = "Pièces à fournir - Copie de la carte à renouveler avec présentation de l'originale - Quittance de paiement du droit de timbre fiscal dû."


def _p(text: str, doc: str, category: str, n: int = 0) -> RetrievedPassage:
    cit = Citation(doc_id=doc, title=doc, source_organization="o", url="https://x", official_reference=None,
                   publication_date=None, applicability="unverified", page_start=9, page_end=9, heading_path=["a", "b"],
                   sha256="0" * 64, procedure_category=category)
    return RetrievedPassage(score=0.7, text=text, chunk_id=f"{doc}:{n}", citation=cit)


LAW55 = _p(ART55, "rne-law-2018-52-ar", "business_registration")
LAW53 = _p(ART53, "rne-law-2018-52-ar", "business_registration", 1)
TABLE = _p(C012, "rne-formalities-procedure-table", "business_registration")
IDDOC = _p(ID_RENEW, "interior-national-id-guide-fr", "national_id")


def _route(method="rules", category="business_registration", lang="en", intent="procedure_info"):
    return RouteDecision(language=lang, intent=intent, procedure_category=category, next_agent="answer", method=method)


class ScriptedLLM:
    """Returns the scripted answer for grounded_answer and the scripted verdict for evidence_topic."""

    def __init__(self, answer: str = "", same: bool | None = None, raw_topic: str | None = None):
        self.answer, self.same, self.raw_topic, self.calls = answer, same, raw_topic, []

    def run(self, spec, **values):
        self.calls.append(spec.name)
        if spec.name == "evidence_topic":
            text = self.raw_topic if self.raw_topic is not None else json.dumps(
                {"question_procedure": "q", "evidence_procedure": "e", "same_procedure": self.same})
        else:
            text = self.answer
        return LLMResult(text=text, model="fake", prompt_ref=spec.ref, seconds=0.1, eval_tokens=1)


# ---------------------------------------------------------------------- number parsing
def test_number_words_in_official_arabic_and_french():
    assert {50000.0, 5.0} <= parse_number_words(ART55)
    assert {1000.0, 5000.0} <= parse_number_words(ART53)
    assert 50.0 in parse_number_words("cinquante dinars")
    assert 7.0 in parse_number_words("في أجل سبعة أيام")


def test_digit_formats():
    assert parse_digits("510,000 TND") == {510000.0, 510.0}
    assert 50000.0 in parse_digits("50 000 TND")
    assert {3.5, 4.5} <= parse_digits("format 3.5/4.5 cm")
    assert 25.0 in parse_digits("٢٥ دينارا")


# ---------------------------------------------------------------------- H14-type numerical claims
def test_h14_type_invented_fine_is_detected():
    check = verify_numbers("The fine is up to 510,000 TND [1].", [LAW55], "What is the penalty for a false declaration?")
    assert check.unsupported == ["510,000"] and check.text == ""


def test_supported_fine_written_in_words_in_source_is_accepted():
    check = verify_numbers("Imprisonment of 5 years and a fine of 50,000 TND [1].", [LAW55], "penalty?")
    assert not check.unsupported and check.claims == 2


def test_number_must_come_from_the_cited_passage():
    answer = "The registration fee is 50 TND [2]. The fine ranges from 1,000 to 5,000 dinars [1]."
    ok = verify_numbers(answer, [LAW53, TABLE], "fees?")
    assert not ok.unsupported
    swapped = verify_numbers("The registration fee is 50 TND [1].", [LAW53, TABLE], "fees?")
    assert swapped.unsupported == ["50"]  # 50 exists in passage 2, not in the cited passage 1


def test_unsupported_sentence_is_removed_and_rest_kept():
    answer = "The fine ranges from 1,000 to 5,000 dinars [1].\nRepeat offences cost 99,000 dinars [1]."
    check = verify_numbers(answer, [LAW53], "fine?")
    assert check.unsupported == ["99,000"] and check.removed_sentences == 1
    assert "1,000 to 5,000" in check.text and "99,000" not in check.text


def test_citation_markers_and_question_numbers_are_not_claims():
    check = verify_numbers("Decree-law 2022-18 waived the penalties [1].", [LAW53], "What does decree-law 2022-18 provide?")
    assert not check.unsupported


# ---------------------------------------------------------------------- answer agent integration
def test_answer_with_invented_figure_is_refused_not_rewritten():
    llm = ScriptedLLM(answer="The penalty is a fine of up to 510,000 TND [1].")
    res = GroundedAnswerer(llm, PROMPTS, verifier=EvidenceVerifier(llm, PROMPTS)).answer(
        ComposeRequest(query="What is the penalty for a false declaration?", route=_route(), passages=[LAW55]))
    assert not res.found and "510,000" not in res.text and res.verification["numbers"]["unsupported"] == ["510,000"]


def test_answer_with_supported_figures_is_kept_with_citation():
    llm = ScriptedLLM(answer="Five years of imprisonment and a fine of 50,000 TND [1].")
    res = GroundedAnswerer(llm, PROMPTS, verifier=EvidenceVerifier(llm, PROMPTS)).answer(
        ComposeRequest(query="What is the penalty for a false declaration?", route=_route(), passages=[LAW55]))
    assert res.found and res.method == "llm_grounded" and "50,000" in res.text
    assert res.citations[0].doc_id == "rne-law-2018-52-ar"
    assert "evidence_topic" not in llm.calls  # keyword-routed: metadata check only, no extra LLM call


# ---------------------------------------------------------------------- H17-type topic consistency
def test_h17_type_topic_mismatch_is_refused_before_generation():
    llm = ScriptedLLM(answer="(must not be generated)", same=False)
    res = GroundedAnswerer(llm, PROMPTS, verifier=EvidenceVerifier(llm, PROMPTS)).answer(
        ComposeRequest(query="Comment renouveler une carte grise ?", route=_route(method="llm", category="general", lang="fr"),
                       passages=[IDDOC]))
    assert not res.found and llm.calls == ["evidence_topic"] and "autre démarche" in res.text


def test_driving_licence_with_passport_evidence_is_refused():
    passport = _p("Pièces à fournir - Un imprimé d’obtention d'un passeport ordinaire", "interior-passport-guide-fr", "passport")
    llm = ScriptedLLM(same=False)
    check = EvidenceVerifier(llm, PROMPTS).check_topic("How do I renew my driving licence?",
                                                       _route(method="llm", category="passport"), [passport])
    assert not check.consistent and check.method == "llm"


def test_llm_routed_question_with_matching_evidence_is_accepted():
    llm = ScriptedLLM(same=True)
    check = EvidenceVerifier(llm, PROMPTS).check_topic("Que prévoit le décret-loi 2022-18 ?",
                                                       _route(method="llm", category="general", lang="fr"),
                                                       [_p("Décret-loi n° 2022-18 portant remise des pénalités", "rne-decree-law-2022-18-fr", "business_registration")])
    assert check.consistent


def test_invalid_or_failed_verdict_means_refusal():
    for raw in ("not json", json.dumps({"same_procedure": "yes"})):
        check = EvidenceVerifier(ScriptedLLM(raw_topic=raw), PROMPTS).check_topic("q", _route(method="llm", category="general"), [IDDOC])
        assert not check.consistent and check.method == "llm_error"
    assert not EvidenceVerifier(None, PROMPTS).check_topic("q", _route(method="llm", category="general"), [IDDOC]).consistent


def test_keyword_routed_questions_use_metadata_only():
    v = EvidenceVerifier(ScriptedLLM(raw_topic="never called"), PROMPTS)
    assert v.check_topic("pièces passeport", _route(category="passport", lang="fr"), [_p("x", "interior-passport-guide-fr", "passport")]).consistent
    mixed = v.check_topic("pièces passeport", _route(category="passport", lang="fr"), [IDDOC])
    assert not mixed.consistent and mixed.method == "metadata"


# ---------------------------------------------------------------------- checklist path on the real corpus
@pytest.fixture(scope="module")
def corpus() -> Corpus:
    s = get_settings()
    c = Corpus(s.raw_dir, s.processed_dir)
    if not c.blocks("interior-passport-guide-fr"):
        pytest.skip("extracted corpus not available")
    return c


def _guide_passage(corpus, doc_id, i):
    sc = corpus.scenarios(doc_id)[i]
    return RetrievedPassage(score=0.7, text="x", chunk_id=f"{doc_id}{i}", citation=corpus.citation(doc_id, ["t"] + sc.path + ["s"]))


@pytest.mark.parametrize("doc_id,category,lang", [
    ("interior-passport-guide-fr", "passport", "fr"),
    ("interior-passport-guide-ar", "passport", "derja"),
    ("interior-national-id-guide-fr", "national_id", "en"),
])
def test_valid_keyword_routed_checklists_are_unchanged(corpus, doc_id, category, lang):
    llm = ScriptedLLM(raw_topic="never called")
    builder = ChecklistBuilder(corpus, None, PROMPTS, verifier=EvidenceVerifier(llm, PROMPTS))
    route = RouteDecision(language=lang, intent="required_documents", procedure_category=category, next_agent="checklist", method="rules")
    res = builder.build(ComposeRequest(query="documents", route=route, passages=[_guide_passage(corpus, doc_id, 0)]))
    assert res.found and llm.calls == []


def test_source_conflict_warning_survives_verification(corpus):
    builder = ChecklistBuilder(corpus, None, PROMPTS, verifier=EvidenceVerifier(None, PROMPTS))
    route = RouteDecision(language="fr", intent="fees", procedure_category="passport", next_agent="checklist", method="rules")
    res = builder.build(ComposeRequest(query="timbre passeport", route=route, passages=[_guide_passage(corpus, "interior-passport-guide-fr", 0)]))
    assert res.found and res.warnings and "20/60" in res.warnings[0]


def test_llm_guessed_checklist_with_mismatching_topic_is_refused(corpus):
    builder = ChecklistBuilder(corpus, None, PROMPTS, verifier=EvidenceVerifier(ScriptedLLM(same=False), PROMPTS))
    route = RouteDecision(language="ar", intent="required_documents", procedure_category="national_id", next_agent="checklist", method="llm")
    res = builder.build(ComposeRequest(query="كيف أحصل على رخصة بناء؟", route=route,
                                       passages=[_guide_passage(corpus, "interior-national-id-guide-fr", 0)]))
    assert not res.found and not res.sections


def test_topic_check_sees_several_passages_of_the_same_document():
    """Regression: rows of one document (RNE table) must not be collapsed to the first row."""
    seen = {}

    class Capture(ScriptedLLM):
        def run(self, spec, **values):
            seen["documents"] = values.get("documents", "")
            return super().run(spec, **values)

    rows = [_p(f"Formalités > Table\nCode procédure: RNE M 004.{n:02d}", "rne-formalities-procedure-table", "business_registration", n)
            for n in (1, 12, 13)]
    EvidenceVerifier(Capture(same=True), PROMPTS).check_topic("cession de parts", _route(method="llm"), rows)
    assert all(f"RNE M 004.{n:02d}" in seen["documents"] for n in (1, 12, 13))
    assert "Formalités > Table" not in seen["documents"].split("excerpt:")[1]


# ---------------------------------------------------------------------- deterministic topic rule (FR/AR)
@pytest.fixture(scope="module")
def vocab_verifier() -> EvidenceVerifier:
    path = get_settings().processed_dir / "chunks_structure.jsonl"
    if not path.exists():
        pytest.skip("chunks not built")
    return EvidenceVerifier(ScriptedLLM(raw_topic="never called"), PROMPTS, path)


@pytest.mark.parametrize("question,lang,missing", [
    ("Comment renouveler une carte grise ?", "fr", ["grise"]),            # H17 type
    ("Quelles pièces pour obtenir un permis de conduire ?", "fr", ["permis"]),
    ("كيف أجدد رخصة السياقة؟", "ar", ["السياقة"]),
])
def test_uncovered_subjects_have_topic_gaps(vocab_verifier, question, lang, missing):
    check = vocab_verifier.check_topic(question, _route(method="llm", category="general", lang=lang), [IDDOC])
    assert not check.consistent and check.method == "corpus_vocabulary" and check.detail["missing_terms"] == missing


@pytest.mark.parametrize("question,lang", [
    ("Que prévoit le décret-loi n° 2022-18 ?", "fr"),                     # verb form is not a topic gap
    ("Comment renouveler la carte d'identité nationale ?", "fr"),
    ("من يعتبر مستفيدا حقيقيا من الشخص المعنوي؟", "ar"),
])
def test_covered_subjects_pass_without_llm_call(vocab_verifier, question, lang):
    llm = vocab_verifier.llm
    llm.calls.clear()
    check = vocab_verifier.check_topic(question, _route(method="llm", category="general", lang=lang), [IDDOC])
    assert check.consistent and llm.calls == []


def test_english_questions_still_use_the_llm_verdict(vocab_verifier):
    v = EvidenceVerifier(ScriptedLLM(same=False), PROMPTS, vocab_verifier.chunks_path)
    check = v.check_topic("How do I renew my driving licence?", _route(method="llm", category="general", lang="en"), [IDDOC])
    assert not check.consistent and check.method == "llm"


def test_topic_check_can_be_disabled_numbers_still_verified():
    v = EvidenceVerifier(ScriptedLLM(raw_topic="never called"), PROMPTS, topic_check=False)
    assert v.check_topic("q", _route(method="llm", category="general"), [IDDOC]).method == "disabled"
    assert verify_numbers("The fine is 510,000 TND [1].", [LAW55], "q").unsupported == ["510,000"]
