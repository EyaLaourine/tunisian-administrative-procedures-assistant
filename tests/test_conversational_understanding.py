"""Conversational intents (affirmation, negation, gratitude, greeting, farewell), short contextual replies and
ambiguous passport requests. No administrative content is asserted or generated here."""
import json
import re
from pathlib import Path

import pytest

from agents.conversation import REPLIES, classify, strip_courtesy
from agents.dialogue import UI
from agents.i18n import t
from agents.intent_router import IntentRouter
from agents.legal_evidence import CLARIFY
from agents.prompts import PromptLibrary
from agents.schemas import DeclaredItem, DialogueContext, RouteRequest
from backend.settings import REPO_ROOT

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "phase_c_acceptance_session.json").read_text(encoding="utf-8"))


@pytest.fixture
def router():
    return IntentRouter(None, PromptLibrary(REPO_ROOT / "prompts"), False)


def chain(router, messages, ctx=None):
    ctx, out = ctx or DialogueContext(), []
    for text in messages:
        d = router.route(RouteRequest(text=text, context=ctx))
        ctx = d.context if d.context is not None else ctx.model_copy(update={"language": d.language})
        out.append((d, ctx))
    return out


# ---------------------------------------------------------------- classification
@pytest.mark.parametrize("text,kind", [
    ("oui", "affirm"), ("Oui !", "affirm"), ("yes", "affirm"), ("ok", "affirm"), ("d'accord", "affirm"),
    ("نعم", "affirm"), ("إي", "affirm"), ("ey", "affirm"), ("behi", "affirm"), ("باهي", "affirm"),
    ("non", "deny"), ("no", "deny"), ("لا", "deny"), ("le", "deny"),
    ("merci", "thanks"), ("Merci beaucoup !", "thanks"), ("merciii", "thanks"), ("thanks", "thanks"),
    ("thank you", "thanks"), ("شكرا", "thanks"), ("شكرا برشا", "thanks"), ("يعطيك الصحة", "thanks"),
    ("ya3tik saha", "thanks"), ("ok merci", "thanks"), ("non merci", "thanks"), ("يعيشك", "thanks"),
    ("bonjour", "greeting"), ("Salam", "greeting"), ("عسلامة", "greeting"), ("السلام عليكم", "greeting"),
    ("hello", "greeting"), ("au revoir", "farewell"), ("bye", "farewell"), ("بالسلامة", "farewell"),
    ("bslema", "farewell"), ("bonne journée", "farewell"),
])
def test_small_talk_is_classified(text, kind):
    assert classify(text) == kind


@pytest.mark.parametrize("text", [
    "oui, en Tunisie", "non, à l'étranger", "merci, et pour les frais ?", "la carte d'identité",
    "Bonjour, je veux renouveler mon passeport", "En Tunisie", "في تونس", "تجديد", "RNE C 001",
    "Que dit l'article 5 ?", "passport", "oui je vis à l'étranger", "يعطيك الصحة شنوة يلزمني للباسبور",
])
def test_messages_with_content_are_not_small_talk(text):
    assert classify(text) is None


@pytest.mark.parametrize("text,rest", [
    ("merci, et pour les frais ?", "et pour les frais ?"),
    ("Merci ! Et pour la carte d'identité ?", "Et pour la carte d'identité ?"),
    ("ok et pour les délais ?", "et pour les délais ?"),
    ("Bonjour, je veux renouveler mon passeport", "je veux renouveler mon passeport"),
    ("et pour les frais ? merci", "et pour les frais ?"),
    ("شكرا، و قداش المعاليم؟", "و قداش المعاليم؟"),
    ("non, à l'étranger", "non, à l'étranger"),        # a negation is never removed
    ("merci", "merci"),                                # nothing substantive would remain
    ("En Tunisie", "En Tunisie"),
])
def test_courtesy_words_are_stripped_around_real_questions(text, rest):
    assert strip_courtesy(text) == rest


# ---------------------------------------------------------------- Phase C acceptance session (regression fixture)
def test_phase_c_acceptance_session(router):
    turns = FIXTURE["turns"]
    results = chain(router, [turn["text"] for turn in turns])
    for turn, (d, ctx) in zip(turns, results):
        exp = turn["expected"]
        assert d.language == exp["language"], turn["text"]
        assert d.next_agent == exp["next"], turn["text"]
        if "hints" in exp:
            assert [h for h in d.hints if h != "abroad"] == exp["hints"], turn["text"]
        if "reply_key" in exp:
            assert UI[exp["language"]][exp["reply_key"]] in d.reply
        if "small_talk" in exp:
            assert d.reply == REPLIES[exp["small_talk"]][exp["language"]]
            assert d.reply != t("out_of_scope", exp["language"]) and d.reply != t("greeting", exp["language"])


# ---------------------------------------------------------------- affirmation / negation against the pending question
@pytest.mark.parametrize("answer", ["oui", "non", "إي", "ok"])
def test_yes_or_no_to_an_either_or_clarification_reasks_it(router, answer):
    (q, _), (d, ctx) = chain(router, ["Quelles pièces fournir pour renouveler un passeport ?", answer])
    assert q.reply == UI["fr"]["residence"] and ctx.pending_intent == "required_documents"
    assert d.next_agent == "reply" and UI["fr"]["residence"] in d.reply
    assert d.reply.startswith(REPLIES["reask"]["fr"])
    assert ctx.category == "passport" and ctx.hints == ["renewal"]  # context kept
    (*_, (after, _)) = chain(router, ["En Tunisie"], ctx)
    assert after.next_agent == "checklist" and after.hints == ["renewal"]


def test_affirmation_to_legal_act_question_reasks_it(router):
    (*_, (q, ctx)) = chain(router, ["Comment immatriculer une SARL ?", "Que dit l'article 5 ?"])
    assert q.reply == CLARIFY["fr"]
    (d, _), = chain(router, ["oui"], ctx)
    assert CLARIFY["fr"] in d.reply


@pytest.mark.parametrize("kind,word", [("affirm", "oui"), ("deny", "non")])
def test_yes_or_no_without_pending_question_is_answered_naturally(router, kind, word):
    (*_, (d, ctx)) = chain(router, ["Quelles pièces fournir pour renouveler un passeport ?", "En Tunisie", word])
    assert d.reply == REPLIES[kind]["fr"] and d.intent != "out_of_scope"
    assert ctx.category == "passport" and ctx.hints == ["renewal"] and ctx.residence == "tunisia"


# ---------------------------------------------------------------- gratitude, greetings, farewells
@pytest.mark.parametrize("word,previous,lang", [("merci", "fr", "fr"), ("شكرا", "derja", "derja"),
                                                ("thanks", "ar", "ar"), ("يعطيك الصحة", "derja", "derja"),
                                                ("merci", "en", "en")])
def test_gratitude_is_brief_and_in_conversation_language(router, word, previous, lang):
    ctx = DialogueContext(category="passport", hints=["renewal"], residence="tunisia", language=previous,
                          declared_items=[DeclaredItem(key="photos", quantity=4)])
    (d, after), = chain(router, [word], ctx)
    assert d.language == lang and d.reply == REPLIES["thanks"][lang]
    assert after.declared_items == ctx.declared_items and after.hints == ["renewal"]  # nothing lost


def test_gratitude_then_contextual_question_continues_the_procedure(router):
    *_, (d, _) = chain(router, ["Quelles pièces fournir pour renouveler un passeport ?", "En Tunisie", "merci",
                                "merci, et pour les frais ?"])
    assert d.intent == "fees" and d.procedure_category == "passport" and d.hints == ["renewal"]


def test_first_greeting_gets_welcome_but_ongoing_conversation_gets_short_greeting(router):
    (first, _), = chain(router, ["Bonjour"])
    assert first.reply == t("greeting", "fr")
    *_, (later, _) = chain(router, ["Quelles pièces fournir pour renouveler un passeport ?", "En Tunisie", "Bonjour"])
    assert later.reply == REPLIES["greeting_short"]["fr"]


@pytest.mark.parametrize("word,lang", [("au revoir", "fr"), ("bslema", "derja"), ("bye", "en")])
def test_farewell(router, word, lang):
    (d, _), = chain(router, [word], DialogueContext(language=lang))
    assert d.reply == REPLIES["farewell"][lang]


def test_small_talk_replies_contain_no_administrative_facts():
    for kind, texts in REPLIES.items():
        for lang, text in texts.items():
            assert not re.search(r"\d|dinar|دينار|DT\b", text), (kind, lang)


# ---------------------------------------------------------------- ambiguous passport transitions
@pytest.mark.parametrize("text,lang", [
    ("نحب نبدّل الباسبور، شنوة يلزمني؟", "derja"),
    ("nheb nbaddel passport chnowa yelzemni", "derja"),
    ("Je veux changer mon passeport, quelles pièces ?", "fr"),
    ("I want to replace my passport, what do I need?", "en"),
])
def test_ambiguous_change_asks_application_instead_of_inheriting_duplicate(router, text, lang):
    duplicate = "ما هي الشروط من أجل استخراج نظير من جواز السفر بالنسبة إلى التونسيين المقيمين بالتراب التونسي؟"
    (_, dup_ctx), (d, ctx) = chain(router, [duplicate, text])
    assert "loss" in dup_ctx.hints
    assert d.next_agent == "reply" and UI[lang]["application"] in d.reply
    assert not any(h in {"loss", "renewal", "first_time", "modification"} for h in ctx.hints)
    assert ctx.residence == "tunisia"  # already stated, not asked again


@pytest.mark.parametrize("answer,hint", [("تجديد", "renewal"), ("ضاع", "loss"), ("renouvellement", "renewal"),
                                         ("perdu", "loss")])
def test_answering_the_ambiguity_resolves_it(router, answer, hint):
    *_, (d, _) = chain(router, ["Je veux changer mon passeport, quelles pièces ? J'habite en Tunisie", answer])
    assert d.next_agent == "checklist" and hint in d.hints


def test_explicit_cases_are_not_treated_as_ambiguous(router):
    (d, _), = chain(router, ["Je veux changer mon passeport car il est perdu, en Tunisie"])
    assert "loss" in d.hints and not (d.reply and UI["fr"]["application"] in d.reply)
    (m, _), = chain(router, ["nheb nbaddel l'adresse fil passport, fi tounes"])
    assert "modification" in m.hints
