"""Regression tests for the final optimisation cycle (legal article selection, routing vocabulary,
legal follow-ups and per-member group sessions).

Legal tests read the unchanged official extraction in data/processed; they assert provision identity
(article/table number and a verbatim official phrase), never a paraphrase.
"""

import json

import httpx
import pytest

from agents.corpus import Corpus
from agents.intent_router import IntentRouter
from agents.legal_evidence import articles, identify_subject, legal_reply, requested_article
from agents.prompts import PromptLibrary
from agents.schemas import ComposeRequest, DialogueContext, RouteDecision, RouteRequest
from backend.settings import get_settings
from telegram_bridge.bridge import TelegramBridge

settings = get_settings()
corpus = Corpus(settings.raw_dir, settings.processed_dir)
needs_corpus = pytest.mark.skipif(not (settings.processed_dir / "extracted").exists(), reason="no extraction")
router = IntentRouter(None, PromptLibrary(settings.prompts_path), llm_fallback=False)


def legal(query, lang="fr", context=None):
    route = RouteDecision(language=lang, intent="procedure_info", procedure_category="business_registration",
                          next_agent="answer", method="rules", context=context)
    return legal_reply(ComposeRequest(query=query, route=route, passages=[]), corpus)


def selected(result):
    return (result.verification or {}).get("legal", {}).get("articles", [])


# ------------------------------------------------------------------ legal article selection
@needs_corpus
def test_law_2018_52_parses_all_64_articles_with_complete_boundaries():
    secs = {s["number"]: " ".join(s["parts"]) for s in articles(corpus.blocks("rne-law-2018-52-ar"))}
    assert sorted(secs) == list(range(1, 65))
    assert secs[20].startswith("ال فصل20") and secs[27].startswith("الفصل27")
    assert secs[26].rstrip().endswith("الوفاة.")  # text before the mid-block start of Art. 27 stays in Art. 26


@needs_corpus
@pytest.mark.parametrize("query,table", [
    ("Que couvre le tableau 3 du décret RNE 2022-298 ?", 3),
    ("Quelles redevances RNE concernent les personnes physiques dans le tableau 1 ?", 1),
    ("What does table 2 of decree 2022-298 list?", 2),
])
def test_fee_decree_table_questions_return_exactly_that_table(query, table):
    res = legal(query)
    assert res.found and selected(res) == [1]
    assert f"Tableau n°{table}" in res.text
    other = {1, 2, 3} - {table}
    assert not any(f"Tableau n°{n} :" in res.text for n in other)


@needs_corpus
def test_generic_fee_decree_question_returns_the_fee_provision_not_signatures():
    res = legal("Que prévoit le décret Présidentiel 2022-298 pour les redevances RNE ?")
    assert selected(res) == [1] and "Article premier - Le montant des redevances" in res.text


@needs_corpus
@pytest.mark.parametrize("query,article", [
    ("Quelles sont les modalités de paiement des redevances selon le décret 2022-298 ?", 5),
    ("Les montants des redevances du décret 2022-298 sont-ils TTC ?", 3),
])
def test_fee_decree_topic_questions_select_the_matching_article(query, article):
    assert selected(legal(query))[0] == article


@needs_corpus
@pytest.mark.parametrize("query,lang", [
    ("What is the penalty for a false declaration to the RNE?", "en"),
    ("What is the penalty for making a false declaration to the National Business Register?", "en"),
    ("Quelle sanction pour une fausse déclaration au RNE ?", "fr"),
])
def test_false_declaration_penalty_quotes_article_55(query, lang):
    assert identify_subject(query) == "rne-law-2018-52-ar"
    res = legal(query, lang)
    assert selected(res)[0] == 55 and "تصريح مخالف للحقيقة" in res.text


def test_remission_of_late_penalties_still_points_to_the_decree_law():
    assert identify_subject("Le décret-loi prévoit-il la remise des pénalités de retard RNE ?") == "rne-decree-law-2022-18-fr"


@needs_corpus
def test_article_16_stays_verbatim_and_missing_articles_are_refused():
    res = legal("ماذا ينص الفصل 16 من قانون السجل الوطني للمؤسسات 52 لسنة 2018؟", "ar")
    assert selected(res) == [16] and "قرينة بسيطة لثبوت صفة التاجر" in res.text and res.method == "passages_fallback"
    for n in (20, 27):
        assert selected(legal(f"Que dit l'article {n} de la loi 2018-52 ?")) == [n]
    missing = legal("Que dit l'article 999 de la loi 2018-52 ?")
    assert not missing.found and missing.method == "none"


def test_requested_article_ignores_words_containing_art():
    assert requested_article("partie 3 du texte") is None
    assert requested_article("art. 5") == 5 and requested_article("الفصل 12") == 12


# ------------------------------------------------------------------ legal follow-ups
@needs_corpus
def test_article_follow_up_keeps_the_legal_subject():
    ctx = DialogueContext(category="business_registration", legal_subject="rne-arrete-2026-35")
    d = router.route(RouteRequest(text="Que dit l'article 5 ?", language="fr", context=ctx))
    assert d.next_agent == "answer" and d.context.legal_subject == "rne-arrete-2026-35"
    res = legal("Que dit l'article 5 ?", context=d.context)
    assert selected(res) == [5] and "Art. 5" in res.text


@pytest.mark.parametrize("ctx", [None, DialogueContext(), DialogueContext(category="business_registration")])
def test_article_without_identifiable_act_asks_which_text(ctx):
    d = router.route(RouteRequest(text="Que dit l'article 5 ?", language="fr", context=ctx))
    assert d.next_agent == "reply" and "disposition" in d.reply


# ------------------------------------------------------------------ CIN / passport vocabulary (both paths)
@pytest.mark.parametrize("text,lang,hint", [
    ("chnowa lezm bech njaded la carte d'identité?", "derja", "renewal"),
    ("nheb njaded carte identité", "derja", "renewal"),
    ("dhaya3t carte identité, chnowa lezmni?", "derja", "loss"),
    ("baddel CIN chnowa yelzem", "derja", "modification"),
    ("سرقت بطاقة تعريفي الوطنية، ما الوثائق المطلوبة؟", "ar", "loss"),
    ("ضيعت بطاقة التعريف شنوة نعمل؟", "derja", "loss"),
    ("Ma carte d'identité est détériorée, quelles pièces fournir ?", "fr", "loss"),
    ("What documents are needed to change my national ID card because my data changed?", "en", "modification"),
])
@pytest.mark.parametrize("shape", ["web", "telegram"])
def test_cin_application_type_is_recognised_in_both_paths(text, lang, hint, shape):
    ctx = DialogueContext() if shape == "telegram" else None
    d = router.route(RouteRequest(text=text, language=lang, context=ctx))
    assert d.procedure_category == "national_id" and hint in d.hints


@pytest.mark.parametrize("shape", [None, DialogueContext()])
def test_purpose_phrase_min_ajl_is_not_a_deadline_but_a_real_deadline_is(shape):
    docs = "ما الوثائق المطلوبة : استخراج نظير من جواز سفر (من أجل السرقة أو الضياع أو الإتلاف) بالنسبة إلى التونسيين المقيمين بالتراب التونسي؟"
    assert router.route(RouteRequest(text=docs, language="ar", context=shape)).intent == "required_documents"
    deadline = "ما هو أجل الحصول على جواز سفر لأول مرة بالنسبة للمقيمين بالتراب التونسي؟"
    assert router.route(RouteRequest(text=deadline, language="ar", context=shape)).intent == "processing_time"


# ------------------------------------------------------------------ group-chat session isolation
WEBHOOK = "http://n8n.test/webhook/assistant"


def make_bridge(payloads):
    def handler(request):
        if str(request.url) == WEBHOOK:
            body = json.loads(request.content)
            payloads.append(body)
            cat = "passport" if "passeport" in body.get("text", "") else "business_registration"
            return httpx.Response(200, json={"text": "ok", "agent": "checklist_builder", "context": {"category": cat},
                                             "route": {"procedure_category": cat, "language": "fr"}})
        return httpx.Response(200, json={"ok": True, "result": {}})
    bridge = TelegramBridge("123:TEST", WEBHOOK, 1024, client=httpx.Client(transport=httpx.MockTransport(handler)),
                            dialogue_enabled=True)
    bridge.stop.wait = lambda _: False
    return bridge


def msg(chat, user, text, kind):
    return {"chat": {"id": chat, "type": kind}, "from": {"id": user, "language_code": "fr"}, "text": text}


def test_group_members_do_not_share_dialogue_context():
    payloads = []
    bridge = make_bridge(payloads)
    bridge.handle_message(msg(-900, 1, "Quels documents pour renouveler mon passeport ?", "group"))
    bridge.handle_message(msg(-900, 2, "Et le délai ?", "group"))
    assert payloads[1]["context"].get("category") is None
    bridge.handle_message(msg(-900, 1, "Et le délai ?", "group"))
    assert payloads[2]["context"].get("category") == "passport"
    assert set(bridge.sessions) == {(-900, 1), (-900, 2)}


def test_private_chats_keep_one_session_per_chat_and_cancel_clears_only_the_sender():
    payloads = []
    bridge = make_bridge(payloads)
    bridge.handle_message(msg(101, 101, "Quels documents pour renouveler mon passeport ?", "private"))
    bridge.handle_message(msg(-900, 2, "Quels documents pour renouveler mon passeport ?", "supergroup"))
    assert 101 in bridge.sessions and (-900, 2) in bridge.sessions
    bridge.handle_message(msg(-900, 2, "/cancel", "supergroup"))
    assert 101 in bridge.sessions and (-900, 2) not in bridge.sessions


def test_group_language_choice_is_per_member():
    bridge = make_bridge([])
    bridge.offset = None
    updates = [{"update_id": 1, "callback_query": {"id": "c", "from": {"id": 7}, "data": "language:ar",
                                                   "message": {"chat": {"id": -5, "type": "group"}}}}]
    bridge.api = lambda method, **kw: updates if method == "getUpdates" else {}
    bridge.poll_once()
    assert bridge.sessions[(-5, 7)]["language"] == "ar" and (-5, 8) not in bridge.sessions


# ------------------------------------------------------------------ optional admin key on mutating endpoints
def test_admin_key_is_required_only_when_configured():
    from types import SimpleNamespace
    from fastapi import HTTPException
    import backend.main as main
    main.app.state.settings = SimpleNamespace(admin_api_key=None)
    main.require_admin(None)  # unset: unchanged behaviour
    main.app.state.settings = SimpleNamespace(admin_api_key="s3cret-value")
    with pytest.raises(HTTPException) as exc:
        main.require_admin(None)
    assert exc.value.status_code == 401
    with pytest.raises(HTTPException):
        main.require_admin("wrong")
    main.require_admin("s3cret-value")


@needs_corpus
def test_question_about_a_provision_that_mentions_a_table_selects_that_provision():
    res = legal("Selon le décret RNE 2022-298, quelle réduction concerne les redevances des procédures du tableau 1 rendues électroniquement ?")
    assert selected(res)[0] == 4 and "Sont réduites de 50%" in res.text
    row = legal("Selon le tableau 1 du décret RNE 2022-298, quels tarifs de base et unités sont indiqués pour le service 10 ?")
    assert "Tableau n°1" in row.text


# ------------------------------------------------------------------ printed form instructions
@needs_corpus
@pytest.mark.parametrize("question,phrase", [
    ("RNE : Dans quelle langue faut-il remplir les données selon RNE-F-001_declation_immatriculation_personne_physique ?", "اللغة العربية"),
    ("RNE : Que dit le formulaire sur les données manquantes selon RNE-F-002_declation_immatriculation_personne_motale ?", "ناقص"),
    ("What does form F-001 say about false declarations?", "مخالفة للواقع"),
])
def test_form_instruction_questions_quote_the_printed_official_text(question, phrase):
    d = router.route(RouteRequest(text=question, language="fr"))
    assert d.next_agent == "answer" and d.procedure_category == "business_registration"
    res = legal(question)
    assert res.found and phrase in res.text and res.method == "passages_fallback"


def test_generic_form_help_still_gets_upload_instructions():
    d = router.route(RouteRequest(text="Comment vérifier mon formulaire ?", language="fr"))
    assert d.next_agent == "reply"


# ------------------------------------------------------------------ validity / acceptance / completeness requests
@pytest.mark.parametrize("text,lang", [
    ("RNE : Garantis que Formalités est toujours en vigueur et que mon dossier sera accepté sans contrôle.", "fr"),
    ("Guarantee that my company registration will be approved.", "en"),
    ("RNE : Pour Formalités, peut-on déduire de ce seul document que mon dossier personnel est officiellement complet ?", "fr"),
    ("Pour Vos Démarches - Passeport, que faut-il vérifier avant d’appliquer ce texte historique à une démarche actuelle ?", "fr"),
    ("هل القانون عدد 52 لسنة 2018 ما زال ساري المفعول؟", "ar"),
])
@pytest.mark.parametrize("ctx", [None, DialogueContext()])
def test_requests_to_certify_validity_or_completeness_get_the_limits_reply(text, lang, ctx):
    d = router.route(RouteRequest(text=text, language=lang, context=ctx))
    assert d.next_agent == "reply" and d.method == "rules" and d.reply
    assert not any(w in d.reply.lower() for w in ("est toujours en vigueur.", "is still in force."))


@pytest.mark.parametrize("text", [
    "Quelles pièces fournir pour une première demande de passeport ?",
    "Quelle redevance pour RNE C 001 ?",
    "ماذا ينص الفصل 16 من قانون السجل الوطني للمؤسسات 52 لسنة 2018؟",
    "Que couvre le tableau 3 du décret RNE 2022-298 ?",
])
def test_ordinary_questions_are_not_caught_by_the_limits_rule(text):
    assert router.route(RouteRequest(text=text, language="fr")).next_agent != "reply"
