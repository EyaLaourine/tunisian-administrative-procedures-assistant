"""Bounded Derja conversation closing, with no administrative retrieval or generation."""
import pytest
from agents.conversation import REPLIES, classify, expression_language
from agents.intent_router import IntentRouter
from agents.prompts import PromptLibrary
from agents.schemas import DialogueContext, RouteRequest
from backend.settings import REPO_ROOT


@pytest.fixture
def router():
    class ForbiddenModel:
        def run(self,*args,**kwargs):
            raise AssertionError('A pure closing must not invoke a language model')
    return IntentRouter(ForbiddenModel(),PromptLibrary(REPO_ROOT/'prompts'),True)


def passport_context(**updates):
    state=DialogueContext(category='passport',hints=['renewal','abroad'],residence='abroad',
                          last_intent='required_documents',language='fr')
    return state.model_copy(update=updates)


@pytest.mark.parametrize('text',[
    'le manheb chay ekhr','lé ma nheb chay ekher','la merci','non merci','barra yatik saha',
    'LE MANHEB CHAY EKHR!!!','lé   ma nheb chey ekher.','le manhebb chay e5er',
    'barra yaatik sa7a','barra ya3tik saha','Le merci',
])
def test_full_message_closings_never_enter_administrative_pipeline(router,text):
    state=passport_context()
    assert classify(text)=='closing'
    result=router.route(RouteRequest(text=text,context=state))
    assert result.next_agent=='reply' and result.procedure_category=='none'
    assert result.retrieval_query is None and result.prompt_ref is None
    language=result.reply_language or result.language
    assert result.reply==REPLIES['closing'][language] and len(result.reply)<90
    assert 'http' not in result.reply and 'Sources' not in result.reply
    assert result.context.model_dump()==state.model_dump()
    if text!='non merci':
        assert language=='derja' and any('\u0600'<=c<='\u06ff' for c in result.reply)


def test_exact_telegram_gratitude_then_negative_closing(router):
    state=passport_context()
    for text,reply in [
        ('merci',REPLIES['thanks']['fr']),
        ('yaatik saha',REPLIES['thanks']['derja']),
        ('le manheb chay ekhr',REPLIES['closing']['derja']),
    ]:
        result=router.route(RouteRequest(text=text,context=state))
        assert result.next_agent=='reply' and result.reply==reply
        assert result.retrieval_query is None and result.prompt_ref is None
        state=result.context
    assert state.category=='passport' and state.residence=='abroad' and state.language=='fr'


@pytest.mark.parametrize('text',[
    'le manheb chay ekhr, ama chnowa les frais ?',
    'lé ma nheb chay ekher pour le passeport ?',
    'non merci, et pour les frais ?',
    'la merci, chnowa lewra9 ?',
    'barra yatik saha, combien coûte le renouvellement ?',
    'le manheb chay ekhr et quels sont les délais ?',
    'ma nhebch njadded el passeport',
    'ma 3andich tasawer',
    "non, je réside à l’étranger",
    "Je ne veux pas renouveler mon passeport, je veux un duplicata",
    'barra', 'nheb chay ekher', 'la carte nationale',
])
def test_substantive_or_incomplete_messages_are_not_closings(text):
    assert classify(text) is None


@pytest.mark.parametrize('text',[
    'Et pour les frais ?',
    'non merci, et pour les frais ?',
    'barra yatik saha, combien coûte le renouvellement ?',
])
def test_genuine_followup_preserves_passport_context(text):
    # Use deterministic routing only: tests must never contact a real model.
    route=IntentRouter(None,PromptLibrary(REPO_ROOT/'prompts'),False)
    state=passport_context()
    closed=route.route(RouteRequest(text='le manheb chay ekhr',context=state))
    follow=route.route(RouteRequest(text=text,context=closed.context,language='fr'))
    assert follow.next_agent=='checklist' and follow.intent=='fees'
    assert follow.procedure_category=='passport' and follow.context.residence=='abroad'


def test_explicit_closing_does_not_repeat_a_pending_clarification(router):
    state=passport_context(residence=None,hints=['renewal'],last_intent=None,pending_intent='fees')
    result=router.route(RouteRequest(text='le manheb chay ekhr',context=state))
    assert result.next_agent=='reply' and result.reply==REPLIES['closing']['derja']
    assert result.context.pending_intent=='fees'  # Preserve context for a later genuine question.


@pytest.mark.parametrize('previous',['fr','en','ar','derja'])
def test_derja_closing_reply_language_is_independent_of_saved_language(router,previous):
    result=router.route(RouteRequest(text='lé ma nheb chay ekher',context=passport_context(language=previous)))
    assert result.reply_language=='derja' and result.language==previous


def test_barra_with_thanks_answers_pending_residence_instead_of_closing():
    router=IntentRouter(None,PromptLibrary(REPO_ROOT/'prompts'),False)
    state=passport_context(residence=None,hints=['renewal'],last_intent=None,pending_intent='fees')
    assert classify('barra yatik saha',state) is None
    result=router.route(RouteRequest(text='barra yatik saha',context=state,language='derja'))
    assert result.next_agent=='checklist' and result.intent=='fees'
    assert result.context.residence=='abroad' and 'abroad' in result.hints
    assert result.context.language==result.language=='derja'
