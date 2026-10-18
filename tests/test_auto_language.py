"""Automatic per-message language (AUTO mode) and procedure-state isolation.

Messages come from the Telegram acceptance checklist and the language-fix specification. Official passages
are read from the real corpus; no administrative content is invented here.
"""
import json
from types import SimpleNamespace

import httpx
import pytest

from agents.checklist_builder import ChecklistBuilder
from agents.corpus import Corpus
from agents.dialogue import UI
from agents.i18n import t
from agents.intent_router import IntentRouter
from agents.language import detect_language, detect_language_details, resolve_language
from agents.prompts import PromptLibrary
from agents.schemas import ComposeRequest, DeclaredItem, DialogueContext, RouteRequest
from backend.settings import REPO_ROOT, get_settings
from rag.retrieval import RetrievedPassage
from telegram_bridge.bridge import TelegramBridge
from telegram_bridge.ui import TEXT, language_keyboard

FR_PASSPORT = "Quelles pièces fournir pour renouveler un passeport ?"
AR_DUPLICATE = "ما هي الشروط من أجل استخراج نظير من جواز السفر بالنسبة إلى التونسيين المقيمين بالتراب التونسي؟"
DERJA_DUPLICATE = "نحب نطلع نظير من الباسبور وأنا ساكن في تونس، شنوة يلزم؟"
EN_PASSPORT = "What documents do I need to renew my passport? I live in Tunisia."
LATIN_DERJA = "Chnowa lezemni bech njadded passport?"
FR_LEGAL = "Quelles autorités compétentes peuvent obtenir les informations sur le bénéficiaire effectif ?"
AR_LEGAL = "ماذا ينص الفصل 16 من قانون السجل الوطني للمؤسسات 52 لسنة 2018؟"


# ---------------------------------------------------------------- detection
@pytest.mark.parametrize("text,expected", [
    (FR_PASSPORT, "fr"),
    ("ما هي شروط استخراج جواز السفر؟", "ar"),
    ("نحب نبدّل الباسبور، شنوة يلزمني؟", "derja"),
    (LATIN_DERJA, "derja"),
    ("What documents do I need?", "en"),
    (AR_DUPLICATE, "ar"),
    (DERJA_DUPLICATE, "derja"),
    (EN_PASSPORT, "en"),
    (FR_LEGAL, "fr"),
    (AR_LEGAL, "ar"),
    ("Comment obtenir une carte grise ?", "fr"),
    ("Et si mon cas ne correspond pas à ce texte ?", "fr"),
    ("كيفاش نسجل شركة؟", "derja"),
    ("ما هي الوثائق المطلوبة لتجديد بطاقة التعريف الوطنية؟", "ar"),
    ("Kifech na3mel passport jdid?", "derja"),
    ("3andi 4 tsawer w copie mta3 la carte", "derja"),
    ("How much does it cost to register a company?", "en"),
])
def test_substantive_messages_are_detected_confidently(text, expected):
    guess = detect_language_details(text)
    assert guess.language == expected and guess.confident
    assert detect_language(text) == expected


@pytest.mark.parametrize("text", ["oui", "ok", "merci", "yes", "اي", "شكرا", "في تونس", "En Tunisie", "RNE C 001",
                                  "passport", "Tunisie", "fi tounes", "behi"])
def test_short_or_ambiguous_messages_are_not_confident(text):
    assert not detect_language_details(text).confident


@pytest.mark.parametrize("text,previous", [("oui", "derja"), ("اي", "fr"), ("في تونس", "derja"), ("ok", "ar"),
                                           ("En Tunisie", "ar"), ("merci", "en")])
def test_ambiguous_follow_up_keeps_conversation_language(text, previous):
    assert resolve_language(text, None, DialogueContext(language=previous)) == (previous, "context")


def test_preference_resolves_ambiguity_but_never_overrides_a_clear_message():
    ctx = DialogueContext(preferred_language="derja")
    assert resolve_language("ok", None, ctx) == ("derja", "preference")
    assert resolve_language(FR_PASSPORT, None, ctx) == ("fr", "detected")
    # The conversation language (latest answer) comes before the stored preference.
    assert resolve_language("ok", None, DialogueContext(language="en", preferred_language="derja"))[0] == "en"


def test_forced_language_is_kept_for_api_clients():
    assert resolve_language(FR_PASSPORT, "ar", DialogueContext(language="en")) == ("ar", "forced")


class FakeLLM:
    def __init__(self, text):
        self.text, self.calls = text, 0

    def run(self, spec, **values):
        self.calls += 1
        assert spec.name == "language_identification"
        return SimpleNamespace(text=self.text)


def test_model_fallback_only_for_long_unmarked_latin_messages_and_is_validated():
    prompts = PromptLibrary(REPO_ROOT / "prompts")
    unmarked = "Zzz qwerty brrr plop"
    llm = FakeLLM(json.dumps({"language": "derja"}))
    assert resolve_language(unmarked, None, DialogueContext(), llm, prompts) == ("derja", "model")
    invalid = FakeLLM(json.dumps({"language": "ar"}))  # not allowed for Latin script: falls back to context
    assert resolve_language(unmarked, None, DialogueContext(language="fr"), invalid, prompts) == ("fr", "context")
    unused = FakeLLM("{}")
    resolve_language(FR_PASSPORT, None, DialogueContext(), unused, prompts)
    resolve_language("ok", None, DialogueContext(), unused, prompts)
    assert unused.calls == 0


# ---------------------------------------------------------------- router (no /language)
@pytest.fixture
def router():
    return IntentRouter(None, PromptLibrary(REPO_ROOT / "prompts"), False)


def chain(router, messages, ctx=None):
    """Mimics the bridge: the returned context (or, when None, the answered language) feeds the next turn."""
    ctx, out = ctx or DialogueContext(), []
    for text in messages:
        d = router.route(RouteRequest(text=text, context=ctx))
        ctx = d.context if d.context is not None else ctx.model_copy(update={"language": d.language})
        out.append(d)
    return out


@pytest.mark.parametrize("first,second,expected", [
    (FR_PASSPORT, AR_DUPLICATE, ["fr", "ar"]),             # French -> Arabic
    (AR_DUPLICATE, FR_PASSPORT, ["ar", "fr"]),             # Arabic -> French
    (FR_PASSPORT, DERJA_DUPLICATE, ["fr", "derja"]),       # French -> Derja
    (DERJA_DUPLICATE, EN_PASSPORT, ["derja", "en"]),       # Derja -> English
    (EN_PASSPORT, FR_PASSPORT, ["en", "fr"]),              # English -> French
    (FR_LEGAL, LATIN_DERJA, ["fr", "derja"]),              # Latin-script Derja
    ("نحب نبدّل الباسبور، شنوة يلزمني؟", FR_LEGAL, ["derja", "fr"]),  # Arabic-script Derja
])
def test_language_switches_without_language_command(router, first, second, expected):
    assert [d.language for d in chain(router, [first, second])] == expected


def test_clarification_answers_stay_in_conversation_language(router):
    derja = chain(router, ["نحب نجدد الباسبور، شنوة يلزمني؟", "في تونس"])
    assert [d.language for d in derja] == ["derja", "derja"]
    assert derja[0].reply and UI["derja"]["residence"] in derja[0].reply
    assert derja[1].context.residence == "tunisia" and derja[1].next_agent == "checklist"
    french = chain(router, [FR_PASSPORT, "En Tunisie"])
    assert [d.language for d in french] == ["fr", "fr"] and french[0].reply == UI["fr"]["residence"]
    latin = chain(router, [LATIN_DERJA, "fi tounes"])
    assert [d.language for d in latin] == ["derja", "derja"]


def test_selected_language_is_a_preference_not_a_lock(router):
    ctx = DialogueContext(preferred_language="derja")
    turns = chain(router, [FR_PASSPORT, "oui", AR_DUPLICATE], ctx)
    assert [d.language for d in turns] == ["fr", "fr", "ar"]
    assert all(d.context is None or d.context.preferred_language == "derja" for d in turns)
    assert chain(router, ["ok"], DialogueContext(preferred_language="ar"))[0].language == "ar"


def test_return_to_auto_drops_preference(router):
    # AUTO = no preferred_language in the context; ambiguous messages then follow the conversation only.
    assert chain(router, ["ok"], DialogueContext(language="en"))[0].language == "en"


def test_legal_citation_questions_follow_message_language(router):
    fr, ar = chain(router, [FR_LEGAL, AR_LEGAL])
    assert (fr.language, fr.next_agent) == ("fr", "answer")
    assert (ar.language, ar.next_agent) == ("ar", "answer")


def test_unsupported_request_refusal_follows_message_language(router):
    (derja_first, refusal) = chain(router, [DERJA_DUPLICATE, "Comment obtenir une carte grise ?"])
    assert refusal.language == "fr" and refusal.intent == "out_of_scope"
    assert refusal.reply == t("out_of_scope", "fr")


# ---------------------------------------------------------------- procedure-state isolation
def test_duplicate_after_renewal_does_not_reuse_declared_photos(router):
    renewal, photos, duplicate = chain(router, [FR_PASSPORT, "En Tunisie, j'ai 4 photos", AR_DUPLICATE])
    assert photos.context.declared_items == [DeclaredItem(key="photos", quantity=4)]
    assert "renewal" in photos.hints and "loss" in duplicate.hints
    assert duplicate.context.declared_items == []
    assert duplicate.intent != "remaining_documents"
    assert duplicate.context.residence == "tunisia"  # a fact about the person, not about the procedure


def test_same_procedure_keeps_declared_items(router):
    _, photos, missing = chain(router, [FR_PASSPORT, "En Tunisie, j'ai 4 photos", "Qu'est-ce qui me manque ?"])
    assert missing.context.declared_items == [DeclaredItem(key="photos", quantity=4)]
    assert missing.intent == "remaining_documents"


@pytest.mark.parametrize("switch,category", [
    ("Quelles pièces pour obtenir la carte d'identité nationale pour la première fois ?", "national_id"),
    ("Quelle redevance pour RNE C 001 ?", "business_registration"),
    (FR_LEGAL, "business_registration"),
])
def test_switching_procedure_drops_procedure_specific_state(router, switch, category):
    *_, after = chain(router, [FR_PASSPORT, "En Tunisie, j'ai 4 photos", switch])
    assert after.procedure_category == category
    assert after.context is None or after.context.declared_items == []
    if after.context is not None:
        assert "renewal" not in after.context.hints and after.context.language == "fr"


def test_first_time_to_renewal_resets_items_but_explicit_redeclaration_counts(router):
    first, items = chain(router, ["Passeport pour la première fois, en Tunisie", "J'ai 4 photos"])
    assert items.context.declared_items
    (renew,) = chain(router, ["Et pour un renouvellement ? J'ai 2 photos"], items.context)
    assert renew.context.declared_items == [DeclaredItem(key="photos", quantity=2)]


# ---------------------------------------------------------------- Derja rendering of official MSA text
@pytest.fixture
def official_builder():
    settings = get_settings()
    corpus = Corpus(settings.raw_dir, settings.processed_dir)
    if not corpus.scenarios("interior-passport-guide-ar"):
        pytest.skip("Official extraction unavailable")
    return corpus, ChecklistBuilder(corpus, None, PromptLibrary(REPO_ROOT / "prompts"))


def test_derja_checklist_explains_verbatim_msa_official_text(router, official_builder):
    corpus, builder = official_builder
    (route,) = chain(router, [DERJA_DUPLICATE])
    assert route.language == "derja" and route.next_agent == "checklist"
    sc = corpus.scenarios("interior-passport-guide-ar")[0]
    passage = RetrievedPassage(score=.7, text="neutral", chunk_id="neutral",
                               citation=corpus.citation("interior-passport-guide-ar", sc.path))
    result = builder.build(ComposeRequest(query=DERJA_DUPLICATE, route=route, passages=[passage]))
    assert result.found and result.source_language == "ar"
    assert t("official_msa", "derja") in result.text
    official_items = [i for s in result.sections for i in s.items]
    assert official_items and all(i in result.text for i in official_items[:3])  # official text not rewritten
    assert t("sources", "derja") in result.text and t("disclaimer", "derja") in result.text


# ---------------------------------------------------------------- Telegram bridge (AUTO by default)
WEBHOOK = "http://n8n.test/webhook/assistant"


class Server:
    def __init__(self):
        self.sent, self.payloads, self.replies = [], [], []
        self.updates = []

    def handler(self, request):
        url = str(request.url)
        if url == WEBHOOK:
            self.payloads.append(json.loads(request.content))
            return httpx.Response(200, json=self.replies.pop(0))
        if url.endswith("/sendMessage"):
            self.sent.append(json.loads(request.content))
        if url.endswith("/getUpdates"):
            return httpx.Response(200, json={"ok": True, "result": self.updates})
        return httpx.Response(200, json={"ok": True, "result": {}})


@pytest.fixture
def bridge():
    server = Server()
    b = TelegramBridge("123:TEST", WEBHOOK, 1024, client=httpx.Client(transport=httpx.MockTransport(server.handler)),
                       dialogue_enabled=True)
    b.stop.wait = lambda _: False
    return b, server


def msg(text):
    return {"chat": {"id": 1}, "from": {"language_code": "fr"}, "text": text}


def reply(language, context=None):
    return {"text": "neutral", "agent": "intent_router", "route": {"language": language, "procedure_category": "none"},
            **({"context": context} if context is not None else {})}


def test_bridge_sends_no_language_and_remembers_answer_language(bridge):
    b, server = bridge
    server.replies = [reply("ar"), reply("ar")]
    b.handle_message(msg(AR_DUPLICATE))
    assert "language" not in server.payloads[-1]
    assert "preferred_language" not in server.payloads[-1]["context"]
    assert b.sessions[1]["conv_language"] == "ar"
    b.handle_message(msg("في تونس"))
    assert server.payloads[-1]["context"]["language"] == "ar" and "language" not in server.payloads[-1]
    assert server.sent[-1]["reply_markup"]["inline_keyboard"][0][0]["text"] == TEXT["ar"]["main"]


def test_bridge_selected_language_is_sent_as_preference_only(bridge):
    b, server = bridge
    server.updates = [{"update_id": 1, "callback_query": {"id": "c", "message": msg(""), "data": "language:derja"}}]
    b.poll_once()
    assert server.sent[-1]["text"] == TEXT["derja"]["selected"]
    server.replies = [reply("fr")]
    b.handle_message(msg(FR_PASSPORT))
    assert "language" not in server.payloads[-1]
    assert server.payloads[-1]["context"]["preferred_language"] == "derja"
    # Menus keep the chosen language; the answer itself followed the message (fr).
    assert server.sent[-1]["reply_markup"]["inline_keyboard"][0][0]["text"] == TEXT["derja"]["main"]
    assert b.sessions[1]["conv_language"] == "fr"


def test_bridge_auto_button_returns_to_auto(bridge):
    b, server = bridge
    b.session(1)["language"] = "en"
    b.session(1)["conv_language"] = "fr"
    server.updates = [{"update_id": 1, "callback_query": {"id": "c", "message": msg(""), "data": "language:auto"}}]
    b.poll_once()
    assert "language" not in b.sessions[1]
    # Confirmed in the conversation language, not in the preference that was just removed.
    assert server.sent[-1]["text"] == TEXT["fr"]["auto_selected"]
    server.replies = [reply("en")]
    b.handle_message(msg(EN_PASSPORT))
    assert "preferred_language" not in server.payloads[-1]["context"]


def test_language_keyboard_offers_auto_first():
    rows = language_keyboard("fr")["inline_keyboard"]
    assert rows[0][0]["callback_data"] == "language:auto"
    assert [r[0]["callback_data"] for r in rows[1:5]] == ["language:en", "language:fr", "language:ar", "language:derja"]


def test_procedure_menu_command_uses_display_language(bridge):
    b, server = bridge
    b.session(1)["conv_language"] = "ar"
    server.replies = [reply("ar")]
    b.handle_message(msg("/passport"))
    assert server.payloads[-1]["language"] == "ar"  # synthetic English command text is not detected
