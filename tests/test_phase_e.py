"""Phase E: fee-warning relevance (A2), national ID card (CIN) and RNE routing, CIN content from the official guide.

Every asserted administrative fact is read from the indexed official corpus (data/processed); nothing is invented.
"""
import re

import pytest

from agents.checklist_builder import AMOUNT, ChecklistBuilder
from agents.conversation import REPLIES
from agents.corpus import Corpus
from agents.dialogue import UI
from agents.i18n import t
from agents.intent_router import IntentRouter
from agents.prompts import PromptLibrary
from agents.schemas import ComposeRequest, DeclaredItem, DialogueContext, RouteRequest
from backend.settings import REPO_ROOT, get_settings
from rag.retrieval import RetrievedPassage

CIN = "interior-national-id-guide-fr"
PASSPORT_FR = "interior-passport-guide-fr"


@pytest.fixture(scope="module")
def corpus():
    s = get_settings()
    c = Corpus(s.raw_dir, s.processed_dir)
    if not c.scenarios(CIN) or not c.scenarios(PASSPORT_FR):
        pytest.skip("Official extraction unavailable")
    return c


@pytest.fixture(scope="module")
def builder(corpus):
    return ChecklistBuilder(corpus, None, PromptLibrary(REPO_ROOT / "prompts"))


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


def passage(corpus, doc, scenario):
    return RetrievedPassage(score=.7, text="neutral", chunk_id="neutral", citation=corpus.citation(doc, scenario.path))


def official_lines(corpus, doc):
    return {i.strip() for sc in corpus.scenarios(doc) for s in sc.sections for i in s.items}


def official_amounts(corpus, docs):
    return {m.group(1) for d in docs for i in official_lines(corpus, d) for m in AMOUNT.finditer(i)}


def build(builder, corpus, route, doc, scenario, query="neutral"):
    return builder.build(ComposeRequest(query=query, route=route, passages=[passage(corpus, doc, scenario)]))


# ---------------------------------------------------------------- A2: fee-discrepancy warning relevance
PASSPORT_CTX = dict(category="passport", hints=["renewal"], residence="tunisia", language="fr")


def renewal_scenario(corpus):
    return next(s for s in corpus.scenarios(PASSPORT_FR) if "renouvellement" in s.title.lower() and "étranger" not in s.title.lower())


def test_a2_observed_submission_place_has_no_fee_warning(router, builder, corpus):
    """Observed in production: "je veux savoir le lieu de depot" returned the place plus a fee-discrepancy warning."""
    (route, _), = chain(router, ["je veux savoir le lieu de depot"], DialogueContext(**PASSPORT_CTX))
    assert route.intent == "submission_place"
    r = build(builder, corpus, route, PASSPORT_FR, renewal_scenario(corpus))
    assert r.found and [s.kind for s in r.sections] == ["place"]
    assert r.fee_discrepancy  # the conflict exists in the official versions...
    assert r.warnings == [] and r.fee_discrepancy not in r.text  # ...but is unrelated to this answer
    assert all(i in r.text for s in r.sections for i in s.items)  # official place text unchanged
    assert r.citations and t("disclaimer", "fr") in r.text      # citations and general disclaimer kept


@pytest.mark.parametrize("text,intent,shown", [
    ("et les frais ?", "fees", True),                      # fees explicitly requested
    ("Quelles pièces fournir ?", "required_documents", True),  # the document list contains the fee amount
    ("quel est le délai ?", "processing_time", False),
    ("je veux savoir le lieu de depot", "submission_place", False),
])
def test_a2_fee_warning_follows_the_content_of_the_answer(router, builder, corpus, text, intent, shown):
    (route, _), = chain(router, [text], DialogueContext(**PASSPORT_CTX))
    assert route.intent == intent
    r = build(builder, corpus, route, PASSPORT_FR, renewal_scenario(corpus))
    has_amount = any(AMOUNT.search(i) for s in r.sections for i in s.items)
    assert (r.fee_discrepancy in r.warnings) is shown
    assert shown == (intent == "fees" or has_amount)
    if shown:
        assert r.fee_discrepancy in r.text


def test_a2_fee_warning_without_dialogue_context(builder, corpus):
    from agents.schemas import RouteDecision
    for intent, shown in [("submission_place", False), ("fees", True), ("required_documents", True)]:
        route = RouteDecision(language="fr", intent=intent, procedure_category="passport", hints=["renewal"],
                              next_agent="checklist", method="rules")
        r = build(builder, corpus, route, PASSPORT_FR, renewal_scenario(corpus))
        assert (bool(r.warnings) and r.fee_discrepancy in r.warnings) is shown, intent


def test_a2_cin_has_no_parallel_version_so_no_discrepancy(builder, corpus):
    from agents.schemas import RouteDecision
    route = RouteDecision(language="fr", intent="fees", procedure_category="national_id", hints=[],
                          next_agent="checklist", method="rules")
    r = build(builder, corpus, route, CIN, corpus.scenarios(CIN)[1])
    assert r.fee_discrepancy is None and not r.warnings


# ---------------------------------------------------------------- CIN routing
@pytest.mark.parametrize("text,hint,intent,lang", [
    ("Quelles pièces pour obtenir la carte d'identité nationale pour la première fois ?", "first_time", "required_documents", "fr"),
    ("Comment renouveler ma carte d'identité ?", "renewal", "procedure_info", "fr"),
    ("J'ai perdu ma carte d'identité, que faire ?", "loss", "procedure_info", "fr"),
    ("Ma carte d'identité est abîmée, quelles pièces ?", "loss", "required_documents", "fr"),
    ("On m'a volé ma carte d'identité", "loss", None, "fr"),
    ("شنوة يلزمني باش نجدد بطاقة التعريف؟", "renewal", "required_documents", "derja"),
    ("What documents do I need to renew my national ID card?", "renewal", "required_documents", "en"),
])
def test_cin_application_types(router, text, hint, intent, lang):
    (d, _), = chain(router, [text])
    assert d.procedure_category == "national_id" and hint in d.hints and d.language == lang
    if intent:
        assert d.intent == intent


@pytest.mark.parametrize("text,intent", [
    ("Où déposer la demande de carte d'identité ?", "submission_place"),
    ("Combien coûte la carte d'identité ?", "fees"),
    ("Quel est le délai pour obtenir la carte d'identité ?", "processing_time"),
])
def test_cin_specific_intents(router, text, intent):
    (d, _), = chain(router, [text])
    assert d.procedure_category == "national_id" and d.intent == intent and d.next_agent == "checklist"


@pytest.mark.parametrize("text,answer,hint", [
    ("Je veux changer ma carte d'identité", "perte", "loss"),
    ("Je veux changer ma carte d'identité", "changement de données", "modification"),
    ("Je veux changer ma carte d'identité", "première carte", "first_time"),
    ("نحب نبدل بطاقة التعريف", "تجديد", "renewal"),
])
def test_cin_ambiguous_change_is_clarified_then_resolved(router, text, answer, hint):
    (q, ctx), (d, _) = chain(router, [text, answer])
    assert q.next_agent == "reply" and q.reply == UI[q.language]["cin_application"] and q.retrieval_query is None
    assert hint in d.hints and d.next_agent in {"checklist", "answer"}


def test_cin_pending_clarification_reasked_on_yes(router):
    (_, ctx), (d, _) = chain(router, ["Je veux changer ma carte d'identité", "oui"])
    assert d.reply.startswith(REPLIES["reask"]["fr"]) and UI["fr"]["cin_application"] in d.reply


def test_cin_latin_baddel_remains_modification(router):
    (d, _), = chain(router, ["baddel CIN chnowa yelzem"])
    assert "modification" in d.hints and d.next_agent == "checklist"


def test_context_switch_passport_to_cin_to_rne(router):
    turns = chain(router, ["Quelles pièces fournir pour renouveler un passeport ?", "En Tunisie, j'ai 4 photos",
                           "Et pour la carte d'identité ?", "Quelle redevance pour RNE C 001 ?"])
    (_, _), (_, passport_ctx), (cin, cin_ctx), (rne, rne_ctx) = turns
    assert passport_ctx.declared_items == [DeclaredItem(key="photos", quantity=4)]
    assert cin.procedure_category == "national_id" and cin_ctx.declared_items == [] and "renewal" not in cin_ctx.hints
    assert rne.procedure_category == "business_registration" and rne.next_agent == "checklist"
    assert rne_ctx.declared_items == [] and rne_ctx.rne_code == "RNE C 001"


@pytest.mark.parametrize("first,second,langs", [
    ("Où déposer la demande de carte d'identité ?", "وين نحط الملف متاع بطاقة التعريف؟", ["fr", "derja"]),
    ("What documents do I need to renew my national ID card?", "Quel est le délai ?", ["en", "fr"]),
])
def test_cin_language_switching(router, first, second, langs):
    assert [d.language for d, _ in chain(router, [first, second])] == langs


# ---------------------------------------------------------------- CIN content (official guide only)
@pytest.mark.parametrize("index,hint", [(0, "first_time"), (1, "renewal"), (2, "modification"), (3, "loss")])
def test_cin_checklist_quotes_the_official_guide(router, builder, corpus, index, hint):
    sc = corpus.scenarios(CIN)[index]
    from agents.schemas import RouteDecision
    route = RouteDecision(language="fr", intent="required_documents", procedure_category="national_id", hints=[hint],
                          next_agent="checklist", method="rules")
    r = build(builder, corpus, route, CIN, sc)
    assert r.found and r.doc_id == CIN and r.scenario == sc.title
    lines = official_lines(corpus, CIN)
    shown = [i for s in r.sections for i in s.items]
    assert shown and all(i.strip() in lines for i in shown)                 # verbatim official items only
    assert {m.group(1) for m in AMOUNT.finditer(r.text)} <= official_amounts(corpus, [CIN])  # no invented amount
    assert r.citations and r.citations[0].doc_id == CIN


@pytest.mark.parametrize("intent,kind", [("submission_place", "place"), ("processing_time", "delay")])
def test_cin_place_and_delay_from_official_guide(builder, corpus, intent, kind):
    from agents.schemas import RouteDecision
    route = RouteDecision(language="fr", intent=intent, procedure_category="national_id", hints=["renewal"],
                          next_agent="checklist", method="rules")
    r = build(builder, corpus, route, CIN, corpus.scenarios(CIN)[1])
    assert r.found and r.sections and r.sections[0].kind == kind
    official = {i.strip() for s in corpus.scenarios(CIN)[1].sections if s.kind == kind for i in s.items}
    assert all(i.strip() in official for i in r.sections[0].items)


def test_cin_fees_only_from_official_text(builder, corpus):
    from agents.schemas import RouteDecision
    route = RouteDecision(language="fr", intent="fees", procedure_category="national_id", hints=["renewal"],
                          next_agent="checklist", method="rules")
    r = build(builder, corpus, route, CIN, corpus.scenarios(CIN)[1])
    # Either official fee lines are quoted, or the absence is stated: never an invented amount.
    assert {m.group(1) for m in AMOUNT.finditer(r.text)} <= official_amounts(corpus, [CIN])
    if r.found:
        assert all(i.strip() in official_lines(corpus, CIN) for s in r.sections for i in s.items)


def test_cin_arabic_user_gets_french_official_text_with_note(builder, corpus):
    from agents.schemas import RouteDecision
    route = RouteDecision(language="ar", intent="required_documents", procedure_category="national_id", hints=["renewal"],
                          next_agent="checklist", method="rules")
    r = build(builder, corpus, route, CIN, corpus.scenarios(CIN)[1])
    assert r.found and r.source_language == "fr"
    assert t("original_language", "ar", source="FR") in r.text   # quoted, not machine-translated
    assert t("sources", "ar") in r.text and t("disclaimer", "ar") in r.text


# ---------------------------------------------------------------- RNE routing
@pytest.mark.parametrize("text,intent,nxt", [
    ("Comment immatriculer une SARL au RNE ?", "procedure_info", "answer"),
    ("Que contient le formulaire F-001 ?", "procedure_info", "answer"),
    ("Que contient le formulaire F-002 ?", "procedure_info", "answer"),
    ("Quelles pièces pour l'immatriculation d'une personne physique au RNE ?", "required_documents", "checklist"),
    ("Quelle redevance pour RNE C 001 ?", "fees", "checklist"),
    ("Quel délai pour RNE C 001 ?", "processing_time", "checklist"),
    ("Qui peut accéder aux informations sur le bénéficiaire effectif ?", "procedure_info", "answer"),
])
def test_rne_routing(router, text, intent, nxt):
    (d, _), = chain(router, [text])
    assert d.procedure_category == "business_registration" and d.intent == intent and d.next_agent == nxt


def test_rne_unknown_code_still_goes_to_the_official_table(router):
    (d, ctx), = chain(router, ["Quelle redevance pour RNE C 999 ?"])
    assert d.next_agent == "checklist" and ctx.rne_code == "RNE C 999"  # the table lookup reports "not found"


def test_context_switch_cin_to_rne(router):
    (_, cin_ctx), (rne, rne_ctx) = chain(router, ["Ma carte d'identité est abîmée, quelles pièces ?",
                                                  "Quelle redevance pour RNE C 001 ?"])
    assert "loss" in cin_ctx.hints
    assert rne.procedure_category == "business_registration" and "loss" not in rne_ctx.hints


def test_uncovered_procedure_is_declared_not_answered(router):
    (d, _), = chain(router, ["Comment obtenir un extrait de naissance ?"])
    assert d.next_agent == "reply" and d.reply == t("uncovered_category", "fr")


# ---------------------------------------------------------------- official form questions never reach the LLM fallback
class _OutOfScopeLLM:
    """Stand-in for the local model returning what production returned for these questions."""
    calls = 0

    def run(self, spec, **values):
        from types import SimpleNamespace
        _OutOfScopeLLM.calls += 1
        return SimpleNamespace(text='{"procedure_category": "none", "intent": "out_of_scope"}')


@pytest.mark.parametrize("text", ["Que contient le formulaire F-001 ?", "Que contient le formulaire F-002 ?"])
@pytest.mark.parametrize("context", [None, DialogueContext(category="business_registration", rne_code="RNE C 999", language="fr")])
def test_official_form_question_is_routed_without_llm(text, context):
    """Observed in the isolated baseline run (LLM fallback enabled, as in production): out-of-scope refusal."""
    _OutOfScopeLLM.calls = 0
    router = IntentRouter(_OutOfScopeLLM(), PromptLibrary(REPO_ROOT / "prompts"), True)
    d = router.route(RouteRequest(text=text, context=context))
    assert d.procedure_category == "business_registration" and d.next_agent == "answer" and d.method == "rules"
    assert _OutOfScopeLLM.calls == 0


# ---------------------------------------------------------------- localized file errors (found in the isolated run)
@pytest.mark.parametrize("lang,phrase", [("fr", "le PDF est endommagé ou illisible"), ("en", "the PDF is damaged or unreadable"),
                                         ("ar", "ملف PDF تالف"), ("derja", "الـPDF مفسود")])
def test_corrupt_pdf_error_is_fully_localized(corpus, lang, phrase):
    import base64
    from agents.form_helper import FormHelper
    from agents.schemas import FormCheckRequest
    s = get_settings()
    data = b"%PDF-1.4\n%neutral test\n" + bytes(range(256)) * 8
    r = FormHelper(corpus, s.max_upload_bytes).check(FormCheckRequest(mime_type="application/pdf", language=lang,
                                                                       data_b64=base64.b64encode(data).decode()))
    assert r.recognised is False and r.error == "unreadable PDF"   # technical reason kept for clients/logs
    assert phrase in r.text and "unreadable PDF" not in r.text      # user text has no English fragment
