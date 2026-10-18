"""Regression tests for the seven multilingual failures found on 2026-10-18 (multilingual_eval_results.json).

Root causes: (1) the cross-lingual article vocabulary had no lateness concept, so the criminal sanctions of
Law 2018-52 arts. 53-57 outranked art. 51 (the late penalty, "غرامة تأخير"); (2) "غرامة" (AR) and "khtiya"
(Latin Derja) were not penalty words, so the law was not identified; (3) the indefinite/plural Arabic form
"مستفيدا حقيقيا" and the Latin-script Derja names of the beneficial-owner and name-reservation decrees matched
no rule, so the LLM fallback refused or improvised. Expected evidence spans come from eval_set.jsonl (verified
verbatim against the official text).
"""

import pytest

from agents.corpus import Corpus, norm
from agents.intent_router import IntentRouter
from agents.legal_evidence import articles, identify_subject, legal_reply, rank_sections
from agents.prompts import PromptLibrary
from agents.schemas import ComposeRequest, RouteDecision, RouteRequest
from backend.settings import get_settings

settings = get_settings()
corpus = Corpus(settings.raw_dir, settings.processed_dir)
needs_corpus = pytest.mark.skipif(not (settings.processed_dir / "extracted").exists(), reason="no extraction")
router = IntentRouter(None, PromptLibrary(settings.prompts_path), llm_fallback=False)

LATE = {
    "R18": ("ar", "ما هي غرامة التأخير في التسجيل بالسجل الوطني للمؤسسات؟"),
    "R19": ("fr", "Quelle est la pénalité de retard pour une immatriculation tardive au RNE ?"),
    "M11": ("en", "What is the late registration penalty at the RNE?"),
    "M12": ("derja", "9adech el khtiya ki nfout el ajal mta3 tasjil fel RNE?"),
}
LATE_SPAN = "غرامة تأخير للمركز تحدد بنصف مبلغ المعلوم"
OTHERS = {
    "R28": ("ar", "من يعتبر مستفيدا حقيقيا من الشخص المعنوي؟", "rne-decree-beneficial-owners", "أو تفوق 20 % م ن رأس المال"),
    "M10": ("derja", "chkoun yet7seb moustafid 7a9i9i fel charika?", "rne-decree-beneficial-owners", "أو تفوق 20 % م ن رأس المال"),
    "M08": ("derja", "9adech tab9a s7i7a chhedet 7ajz el esm?", "rne-decree-name-reservation", "صالحة لمدة ستة أشهر قابلة للتجديد مرة واحدة"),
}


def answer(query, lang):
    route = RouteDecision(language=lang, intent="procedure_info", procedure_category="business_registration",
                          next_agent="answer", method="rules")
    return legal_reply(ComposeRequest(query=query, route=route, passages=[]), corpus)


@pytest.mark.parametrize("case", sorted(LATE))
def test_late_penalty_questions_identify_law_2018_52(case):
    assert identify_subject(LATE[case][1]) == "rne-law-2018-52-ar"


@needs_corpus
@pytest.mark.parametrize("case", sorted(LATE))
def test_late_penalty_selects_article_51_and_quotes_it(case):
    lang, q = LATE[case]
    secs = articles(corpus.blocks("rne-law-2018-52-ar"))
    assert [s["number"] for s in rank_sections(q, secs, "rne-law-2018-52-ar")] == [51]
    res = answer(q, lang)
    assert res.found and norm(LATE_SPAN) in norm(res.text)
    assert res.citations and res.citations[0].doc_id == "rne-law-2018-52-ar"


@needs_corpus
@pytest.mark.parametrize("query,article", [
    ("What is the penalty for a false declaration to the RNE?", 55),
    ("Quelle sanction si on ne termine pas une opération d'immatriculation au RNE ?", 53),
])
def test_criminal_sanction_questions_keep_their_articles(query, article):
    secs = articles(corpus.blocks("rne-law-2018-52-ar"))
    assert article in [s["number"] for s in rank_sections(query, secs, "rne-law-2018-52-ar")]


def test_remission_of_late_penalties_still_points_to_decree_law_2022_18():
    assert identify_subject("Quelles pénalités de retard sont remises par le décret-loi 2022-18 ?") == "rne-decree-law-2022-18-fr"
    assert identify_subject("remise des pénalités de retard au RNE") == "rne-decree-law-2022-18-fr"


@pytest.mark.parametrize("case", sorted(OTHERS))
@pytest.mark.parametrize("context", [None, {}])
def test_decree_questions_are_routed_by_rule_to_the_answer_agent(case, context):
    _, q, subject, _ = OTHERS[case]
    d = router.route(RouteRequest(text=q, context=context))
    assert (d.procedure_category, d.next_agent, d.method) == ("business_registration", "answer", "rules")
    assert identify_subject(q) == subject


@needs_corpus
@pytest.mark.parametrize("case", sorted(OTHERS))
def test_decree_questions_quote_the_official_evidence(case):
    lang, q, subject, span = OTHERS[case]
    res = answer(q, lang)
    assert res.found and norm(span) in norm(res.text)
    assert res.citations[0].doc_id == subject


@pytest.mark.parametrize("text", [
    "Quelles pièces pour renouveler un passeport ?", "Combien coûte l'immatriculation d'une SARL ?",
    "ما هي الوثائق المطلوبة لتجديد جواز السفر؟", "What documents are needed for the national identity card?",
])
def test_vocabulary_additions_do_not_capture_other_procedures(text):
    assert identify_subject(text) is None
