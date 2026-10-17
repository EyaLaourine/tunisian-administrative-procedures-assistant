"""Regression tests for the four residual defects of the final candidate (A-D).

Assertions check routing decisions, provision identity and verbatim official wording read from the unchanged
extraction; no expected answer is invented.
"""

import re

import pytest

from agents.corpus import Corpus
from agents.intent_router import IntentRouter, UNMATCHED_REPLY
from agents.legal_evidence import legal_reply
from agents.prompts import PromptLibrary
from agents.schemas import ComposeRequest, DialogueContext, RouteDecision, RouteRequest
from backend.settings import get_settings

settings = get_settings()
corpus = Corpus(settings.raw_dir, settings.processed_dir)
router = IntentRouter(None, PromptLibrary(settings.prompts_path), llm_fallback=False)
needs_corpus = pytest.mark.skipif(not (settings.processed_dir / "extracted").exists(), reason="no extraction")


def legal(query, lang="fr", context=None):
    route = RouteDecision(language=lang, intent="procedure_info", procedure_category="business_registration",
                          next_agent="answer", method="rules", context=context)
    return legal_reply(ComposeRequest(query=query, route=route, passages=[]), corpus)


# ------------------------------------------------------------------ A: "my case does not match"
@pytest.mark.parametrize("ctx,key", [
    (DialogueContext(category="national_id", hints=["first_time"]), "national_id"),          # was: CIN checklist repeated
    (DialogueContext(category="passport", hints=["renewal"], residence="tunisia"), "passport"),  # was: passport checklist
    (DialogueContext(category="business_registration", rne_code="RNE C 001"), "business_registration"),  # was: RNE row
    (DialogueContext(category="business_registration", legal_subject="rne-arrete-2026-35"), "legal"),
])
def test_unmatched_case_follow_up_asks_context_aware_clarification_and_keeps_context(ctx, key):
    d = router.route(RouteRequest(text="Et si mon cas ne correspond pas à ce texte ?", language="fr", context=ctx))
    assert d.next_agent == "reply" and d.reply == UNMATCHED_REPLY["fr"][key]
    assert d.context == ctx  # context preserved, nothing reset or invented


@pytest.mark.parametrize("text,lang", [
    ("What if my case does not match this text?", "en"),
    ("My situation is different, what should I do?", "en"),
    ("وإذا كانت حالتي لا تنطبق على هذا النص؟", "ar"),
    ("و كان حالتي ما تنطبقش؟", "derja"),
    ("Mon cas est particulier.", "fr"),
])
def test_unmatched_case_follow_up_in_all_languages(text, lang):
    ctx = DialogueContext(category="passport")
    d = router.route(RouteRequest(text=text, language=lang, context=ctx))
    assert d.next_agent == "reply" and d.reply == UNMATCHED_REPLY[lang]["passport"]


def test_unmatched_reply_uses_only_official_scenario_headings():
    # Every passport scenario named in the French reply is an official heading of the guide.
    blocks = " ".join(b["text"] for b in corpus.blocks("interior-passport-guide-fr")).lower()
    for heading in ("première fois", "renouvellement", "changement d’un passeport ordinaire", "duplicata", "pélerinage",
                    "à l’étranger"):
        assert heading in blocks


# ------------------------------------------------------------------ B: scope of the RNE formalities table
@needs_corpus
@pytest.mark.parametrize("question,lang,phrase", [
    ("RNE: According to this official document, what is its scope and what remains unverified: Formalités?", "en", "table of 95 procedures"),
    ("Que couvre le tableau des formalités du RNE ?", "fr", "tableau de 95 procédures"),
    ("RNE: ما نطاق هذا النص الرسمي: Formalités؟", "ar", "95"),
])
def test_formalities_table_scope_is_computed_from_the_official_rows(question, lang, phrase):
    res = legal(question, lang)
    assert res.found and phrase in res.text
    assert res.verification["legal"]["method"] == "table_scope_from_official_rows"
    # counts come from the rows themselves; no claim of applicability or of supporting documents
    rows = [b["text"] for b in corpus.blocks("rne-formalities-procedure-table") if b["text"].startswith("Code procédure:")]
    modif = sum("Nature du service: Modification ou mise à jour des données du registre" in r for r in rows)
    assert f"Modification ou mise à jour des données du registre ({modif})" in res.text
    assert "Public Establishments" not in res.text and res.citations[0].url.endswith("/formalites/")


@needs_corpus
def test_specific_rne_code_question_is_not_turned_into_a_scope_summary():
    route = RouteDecision(language="fr", intent="fees", procedure_category="business_registration",
                          next_agent="checklist", method="rules")
    res = legal_reply(ComposeRequest(query="Quelle redevance pour RNE C 001 ?", route=route, passages=[]), corpus)
    assert res is None  # not a legal or scope question: the table row path answers it


# ------------------------------------------------------------------ C: Arabic duplicate ("نظير")
@pytest.mark.parametrize("ctx", [None, DialogueContext()])
@pytest.mark.parametrize("text", [
    "ما هي الشروط من أجل استخراج نظير من جواز السفر بالنسبة إلى التونسيين المقيمين بالتراب التونسي؟",  # failing case
    "نحب نطلع نظير من الباسبور، شنوة يلزم؟",
    "Quelles pièces pour un duplicata de passeport ?",
    "How do I get a duplicate passport?",
])
def test_duplicate_requests_select_the_loss_theft_damage_scenario(text, ctx):
    d = router.route(RouteRequest(text=text, language=None, context=ctx))
    assert d.procedure_category == "passport"
    assert "loss" in d.hints or (d.context and "loss" in d.context.hints)


@pytest.mark.parametrize("ctx", [None, DialogueContext()])
def test_first_application_is_not_mistaken_for_a_duplicate(ctx):
    d = router.route(RouteRequest(text="ما الوثائق المطلوبة للحصول على جواز سفر لأول مرة؟", language="ar", context=ctx))
    assert "loss" not in d.hints and "first_time" in (d.hints or d.context.hints)


# ------------------------------------------------------------------ D: concise, labelled legal answers
@needs_corpus
@pytest.mark.parametrize("question,lang,header,article", [
    ("What is the penalty for a false declaration to the RNE?", "en", "Source:", 55),
    ("Quelle sanction pour une fausse déclaration au RNE ?", "fr", "Source :", 55),
    ("ماذا ينص الفصل 16 من قانون السجل الوطني للمؤسسات 52 لسنة 2018؟", "ar", "المصدر:", 16),
])
def test_legal_answer_starts_with_a_header_in_the_user_language(question, lang, header, article):
    res = legal(question, lang)
    first = res.text.splitlines()[0]
    assert first.startswith(header) and str(article) in first
    assert res.verification["legal"]["articles"][0] == article
    # the explanation never presents itself as an official translation
    assert re.search(r"no official translation|aucune traduction officielle|دون ترجمة رسمية", first)


@needs_corpus
def test_long_legal_answers_show_a_verbatim_key_passage_and_list_remaining_articles():
    res = legal("Quelles autorités compétentes peuvent obtenir les informations sur le bénéficiaire effectif ?")
    text = res.text
    key = re.search(r"« (.+?) »", text).group(1).rstrip(" …")
    official = " ".join(b["text"] for b in corpus.blocks("rne-arrete-2026-35"))
    assert key in official  # the highlighted passage is verbatim official text
    assert "Banque centrale de Tunisie" in text  # the enumerated authorities remain in the answer
    assert "Autres articles du même texte" in text and len(text) < 4300


@needs_corpus
def test_short_legal_answer_has_no_redundant_key_passage():
    res = legal("Que dit l'article 20 de la loi 2018-52 ?")
    assert res.verification["legal"]["articles"] == [20] and "Passage le plus pertinent" not in res.text


def test_ambiguous_article_reference_and_follow_up_still_behave():
    assert router.route(RouteRequest(text="Que dit l'article 5 ?", language="fr")).next_agent == "reply"
    ctx = DialogueContext(category="business_registration", legal_subject="rne-decree-name-reservation")
    d = router.route(RouteRequest(text="Et l'article 3 ?", language="fr", context=ctx))
    assert d.next_agent == "answer" and d.context.legal_subject == "rne-decree-name-reservation"
