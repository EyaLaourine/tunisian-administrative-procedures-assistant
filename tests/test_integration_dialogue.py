"""Structured conversational tests through the real n8n workflow and deployed agents."""
import httpx
import pytest

pytestmark=pytest.mark.integration
URL='http://localhost:5678/webhook/assistant'


@pytest.fixture
def client():
    with httpx.Client(timeout=900) as c:
        c.get('http://localhost:8000/health').raise_for_status()
        yield c


def ask(client,text,context=None,language='derja'):
    response=client.post(URL,json={'text':text,'context':context or {},'language':language})
    response.raise_for_status()
    data=response.json()
    assert data['text']
    return data


def test_exact_derja_inventory_conversation(client):
    first=ask(client,'Chnowa lewra9 bech naamel passeport?')
    assert first['agent']=='intent_router'
    assert first['context']['category']=='passport'
    second=ask(client,'3andi 4 souwar chamseya chneya lawra9 li ne9ssetni',first['context'])
    assert second['agent']=='intent_router'
    assert second['context']['declared_items']==[{'key':'photos','quantity':4}]
    third=ask(client,'awel marra fi tounes',second['context'])
    assert third['agent']=='checklist_builder' and third['found']
    assert third['route']['intent']=='remaining_documents'
    assert third['context']['residence']=='tunisia'
    assert 'loss' not in third['route']['hints']
    assert 'ضياع' not in third['text'].splitlines()[0]
    assert 'قلت عندك منها' in third['text']
    remaining=third['text'].split('اللي مازال تحضّرو ولا تثبّت فيه — النص الرسمي:',1)[-1]
    assert '04 صور' not in remaining
    assert third['citations']
    assert 'ما يثبتش العدد' in third['text']


@pytest.mark.parametrize('language,initial,inventory,confirmation,heading', [
 ('fr','Quels documents pour renouveler mon passeport ?',"J'ai 4 photos, que me manque-t-il ?",'Je réside en Tunisie','Déjà déclaré disponible'),
 ('en','What documents do I need to renew my passport?','I have 4 photos, what else is missing?','I live in Tunisia','Declared as available'),
 ('ar','ما هي الوثائق المطلوبة لتجديد جواز السفر؟','عندي 4 صور شنو ناقصني؟','في تونس','صرحت بأنها متوفرة'),
])
def test_multilingual_personalized_checklist(client,language,initial,inventory,confirmation,heading):
    first=ask(client,initial,language=language)
    assert first['agent']=='intent_router'
    second=ask(client,inventory,first['context'],language)
    result=ask(client,confirmation,second['context'],language)
    assert result['agent']=='checklist_builder' and result['found']
    assert heading in result['text'] and result['citations']
    assert result['route']['language']==language


def test_fee_question_is_focused_and_loss_not_invented(client):
    state={'category':'passport','hints':['renewal'],'residence':'tunisia'}
    result=ask(client,'Combien coûte le passeport ?',state,'fr')
    assert result['route']['intent']=='fees' and result['found']
    assert '4 photos' not in result['text']
    assert 'Quittance' in result['text']
    assert 'montants différents' in result['text']
    result=ask(client,'Et si je réside à l’étranger ?',result['context'],'fr')
    assert result['context']['residence']=='abroad'
    assert 'abroad' in result['route']['hints']
    assert 'à l’étranger' in result['text'].splitlines()[0]


@pytest.mark.parametrize('declared',[False,True])
def test_targeted_question_uses_grounded_answer(client,declared):
    state={'category':'passport','hints':['renewal'],'residence':'tunisia'}
    if declared:
        state['declared_items']=[{'key':'photos','quantity':4}]
    result=ask(client,'Do I need photos for a passport?',state,'en')
    assert result['agent']=='grounded_answer'
    assert result['citations']
    assert result['method'] in {'llm_grounded','passages_fallback'}


def test_real_local_model_understands_collected_document_paraphrase(client):
    state={'category':'passport','hints':['first_time'],'residence':'tunisia'}
    result=ask(client,"I've already collected 4 photographs; what is still missing?",state,'en')
    assert result['context']['declared_items']==[{'key':'photos','quantity':4}]
    assert result['route']['intent']=='remaining_documents'
    assert result['found'] and result['citations']
    assert 'Declared as available' in result['text']
