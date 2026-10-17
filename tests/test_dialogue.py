"""Conversation regression tests. Administrative passages are read from the real official corpus."""
import json
from types import SimpleNamespace

import pytest

from agents.dialogue import UI, understand
from agents.schemas import DialogueContext, DeclaredItem, RouteRequest, ComposeRequest
from agents.intent_router import IntentRouter
from agents.prompts import PromptLibrary
from agents.corpus import Corpus
from agents.checklist_builder import ChecklistBuilder
from backend.settings import get_settings, REPO_ROOT
from rag.retrieval import RetrievedPassage


@pytest.fixture
def router():
    return IntentRouter(None,PromptLibrary(REPO_ROOT/'prompts'),False)


def ask(router,text,state=None,language='derja'):
    return router.route(RouteRequest(text=text,context=state or DialogueContext(),language=language))


def test_exact_derja_conversation_retains_inventory_and_clarifies(router):
    first = ask(router,'Chnowa lewra9 bech naamel passeport?')
    assert first.next_agent == 'reply' and first.context.category == 'passport'
    assert UI['derja']['application'] in first.reply and UI['derja']['residence'] in first.reply
    second = ask(router,'3andi 4 souwar chamseya chneya lawra9 li ne9ssetni',first.context)
    assert second.context.declared_items == [DeclaredItem(key='photos',quantity=4)]
    assert second.intent == 'remaining_documents' and 'loss' not in second.hints
    assert second.next_agent == 'reply' and UI['derja']['ack'] in second.reply
    third = ask(router,'awel marra fi tounes',second.context)
    assert third.next_agent == 'checklist'
    assert third.intent == 'remaining_documents'
    assert third.hints == ['first_time'] and third.context.residence == 'tunisia'
    assert third.context.declared_items[0].quantity == 4
    assert 'first time' in third.retrieval_query


@pytest.mark.parametrize('language,first,second,answer', [
 ('fr','Quels documents pour renouveler mon passeport ?',"J'ai 4 photos, que me manque-t-il ?",'Je réside en Tunisie'),
 ('en','What documents do I need to renew my passport?','I have 4 photos, what else is missing?','I live in Tunisia'),
 ('ar','ما هي الوثائق المطلوبة لتجديد جواز السفر؟','عندي 4 صور شنو ناقصني؟','في تونس'),
])
def test_multilingual_remaining_documents(router,language,first,second,answer):
    r=ask(router,first,language=language)
    assert r.next_agent == 'reply'
    r=ask(router,second,r.context,language)
    assert r.context.declared_items[0].quantity == 4
    r=ask(router,answer,r.context,language)
    assert r.next_agent == 'checklist' and r.intent == 'remaining_documents'
    assert 'renewal' in r.hints


def test_new_procedure_resets_declarations(router):
    state=DialogueContext(category='passport',hints=['first_time'],residence='tunisia',declared_items=[DeclaredItem(key='photos',quantity=4)])
    r=ask(router,'How long does business registration take?',state,'en')
    assert r.context.category == 'business_registration' and not r.context.declared_items


def test_negated_possession_does_not_mark_ready():
    state=DialogueContext(category='passport',declared_items=[DeclaredItem(key='photos',quantity=4)])
    state,_,_=understand("I don't have photos",state)
    assert not state.declared_items


def test_context_does_not_hold_private_values():
    state,_,_=understand("J'ai une copie de carte d'identité numéro PRIVATE-VALUE",DialogueContext(category='passport'))
    assert 'PRIVATE-VALUE' not in state.model_dump_json()
    assert state.declared_items[0].key == 'identity_card_copy'


def test_llm_evidence_is_required_and_quantities_checked():
    class Model:
        def run(self,*args,**kwargs):
            return SimpleNamespace(text=json.dumps({'residence':{'value':'abroad','evidence':'NOT IN MESSAGE'},
                'items':[{'key':'photos','quantity':99,'available':True,'evidence':'neutral'}]}))
    state,_,_=understand('already collected neutral',DialogueContext(),Model(),PromptLibrary(REPO_ROOT/'prompts'))
    assert state.residence is None
    assert state.declared_items[0].quantity is None


def test_targeted_questions_do_not_return_full_checklist(router):
    state=DialogueContext(category='passport',hints=['renewal'],residence='tunisia')
    fee=ask(router,'Combien coûte le passeport ?',state,'fr')
    assert fee.intent == 'fees' and fee.next_agent == 'checklist'
    specific=ask(router,'Do I need photos for a passport?',state,'en')
    assert specific.next_agent == 'answer'


@pytest.fixture
def official_builder():
    settings=get_settings()
    corpus=Corpus(settings.raw_dir,settings.processed_dir)
    if not corpus.scenarios('interior-passport-guide-ar'):
        pytest.skip('Official extraction unavailable')
    builder=ChecklistBuilder(corpus,None,PromptLibrary(REPO_ROOT/'prompts'))
    return corpus,builder


def test_personalized_documents_are_official_and_photos_not_repeated_as_missing(router,official_builder):
    corpus,builder=official_builder
    state=DialogueContext(category='passport',hints=['first_time'],residence='tunisia',declared_items=[DeclaredItem(key='photos',quantity=4)])
    route=ask(router,'3andi 4 souwar chamseya chneya lawra9 li ne9ssetni',state)
    sc=corpus.scenarios('interior-passport-guide-ar')[2]  # A different retrieved scenario must not force it.
    citation=corpus.citation('interior-passport-guide-ar',sc.path)
    passage=RetrievedPassage(score=.7,text='neutral',chunk_id='neutral',citation=citation)
    result=builder.build(ComposeRequest(query='neutral',route=route,passages=[passage]))
    assert result.found and result.citations
    assert 'ضياع' not in result.scenario and 'السرقة' not in result.scenario
    assert UI['derja']['declared'] in result.text
    remaining=result.text.split(UI['derja']['remaining']+':',1)[-1].split(UI['derja']['review'],1)[0]
    assert '04 صور' not in remaining
    assert 'نسخة من بطاقة التعريف' in remaining
    assert UI['derja']['verify'] in result.text  # Specifications are not automatically certified.
    assert result.text.count('PRIVATE') == 0


def test_unknown_photo_count_is_not_removed_from_review(router,official_builder):
    corpus,builder=official_builder
    state=DialogueContext(category='passport',hints=['renewal'],residence='tunisia',declared_items=[DeclaredItem(key='photos')])
    route=ask(router,'What is still missing?',state,'en')
    sc=corpus.scenarios('interior-passport-guide-fr')[0]
    p=RetrievedPassage(score=.7,text='neutral',chunk_id='neutral',citation=corpus.citation('interior-passport-guide-fr',sc.path))
    result=builder.build(ComposeRequest(query='neutral',route=route,passages=[p]))
    assert UI['en']['verify'] in result.text


def test_negated_loss_does_not_switch_scenario():
    state,_,_=understand('I have not lost my passport',DialogueContext(category='passport',hints=['renewal']))
    assert 'loss' not in state.hints and 'renewal' in state.hints


def test_supporting_identity_card_does_not_switch_procedure(router):
    state=DialogueContext(category='passport',hints=['renewal'],residence='tunisia')
    result=ask(router,"J'ai une copie de carte d'identité",state,'fr')
    assert result.procedure_category == 'passport'
    assert result.context.declared_items[0].key == 'identity_card_copy'


def test_pending_clarification_does_not_override_unsupported_question(router):
    state=DialogueContext(category='passport',pending_intent='remaining_documents')
    result=ask(router,'quelle est la météo demain',state,'fr')
    assert result.context is None


def test_dialogue_fee_answer_omits_full_document_checklist(router,official_builder):
    corpus,builder=official_builder
    state=DialogueContext(category='passport',hints=['renewal'],residence='tunisia')
    route=ask(router,'Combien coûte le passeport ?',state,'fr')
    sc=corpus.scenarios('interior-passport-guide-fr')[0]
    p=RetrievedPassage(score=.7,text='neutral',chunk_id='neutral',citation=corpus.citation('interior-passport-guide-fr',sc.path))
    result=builder.build(ComposeRequest(query='neutral',route=route,passages=[p]))
    assert result.found and [s.kind for s in result.sections] == ['fees']
    assert '4 photos' not in result.text
    assert result.warnings and result.citations


def test_specific_question_stays_specific_after_inventory(router):
    state=DialogueContext(category='passport',hints=['renewal'],residence='tunisia',declared_items=[DeclaredItem(key='photos',quantity=4)])
    result=ask(router,'Do I need a copy of my identity card for my passport?',state,'en')
    assert result.next_agent == 'answer' and result.intent == 'procedure_info'
    assert result.context.declared_items == state.declared_items


def test_bad_model_record_does_not_discard_grounded_document_claim():
    class Model:
        def run(self,*args,**kwargs):
            return SimpleNamespace(text=json.dumps({'items':[
                {'key':'photos','quantity':3,'available':True,'evidence':'already collected 3 photographs'},
                {'key':'invalid|choices','available':True,'evidence':'not provided'}]}))
    state,_,_=understand('already collected 3 photographs',DialogueContext(),Model(),PromptLibrary(REPO_ROOT/'prompts'))
    assert state.declared_items==[DeclaredItem(key='photos',quantity=3)]


@pytest.mark.parametrize('structured',[False,True])
def test_schema_format_is_opt_in_and_existing_json_prompts_are_unchanged(monkeypatch,structured):
    import httpx
    from agents.llm import OllamaChatClient
    from agents.prompts import PromptSpec
    original=httpx.Client
    bodies=[]
    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200,json={'message':{'content':'{}'},'done_reason':'stop'})
    monkeypatch.setattr('agents.llm.httpx.Client',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    schema={'type':'object','properties':{'neutral':{'type':'boolean'}}} if structured else None
    spec=PromptSpec(name='neutral',version='v1',json_output=True,response_schema=schema,user_template='{message}')
    OllamaChatClient('http://model.test','neutral').run(spec,message='neutral')
    assert bodies[0]['format'] == (schema if structured else 'json')
