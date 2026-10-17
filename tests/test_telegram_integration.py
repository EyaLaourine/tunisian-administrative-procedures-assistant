"""Mock Telegram only; exercise production handlers through the real local n8n and FastAPI stack."""
import json
from pathlib import Path

import fitz
import httpx
import pytest

from telegram_bridge.bridge import TelegramBridge

pytestmark = pytest.mark.integration
WEBHOOK = 'http://localhost:5678/webhook/assistant'
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def live_bridge():
    try:
        httpx.get('http://localhost:5678/healthz', timeout=5).raise_for_status()
        httpx.get('http://localhost:8000/health', timeout=5).raise_for_status()
    except httpx.HTTPError:
        pytest.skip('Local n8n/FastAPI services unavailable')
    sent, replies, payloads = [], [], []
    upload = {'bytes':b''}
    with httpx.Client(timeout=900) as real:
        def handler(request):
            url = str(request.url)
            if url == WEBHOOK:
                payloads.append(json.loads(request.content))
                response = real.post(WEBHOOK, content=request.content, headers={'content-type':'application/json'})
                if response.is_success:
                    replies.append(response.json())
                return httpx.Response(response.status_code, content=response.content)
            if url.endswith('/sendMessage'):
                sent.append(json.loads(request.content))
            if url.endswith('/getFile'):
                return httpx.Response(200,json={'ok':True,'result':{'file_path':'neutral/file','file_size':len(upload['bytes'])}})
            if '/file/bot' in url:
                return httpx.Response(200,content=upload['bytes'])
            return httpx.Response(200,json={'ok':True,'result':{}})
        client = httpx.Client(transport=httpx.MockTransport(handler))
        bridge = TelegramBridge('MOCK_TELEGRAM_ONLY', WEBHOOK, 10*1024*1024, client=client)
        yield bridge, sent, replies, payloads, upload
        bridge.stop.set()
        client.close()


@pytest.mark.parametrize('text,language,selected', [
    ('Quels documents pour renouveler mon passeport ?', 'fr', None),
    # The existing detector classifies this inflected spelling as Arabic.
    ('شنوما الأوراق اللازمة للباسبور؟', 'ar', None),
    ('شنوما الأوراق اللازمة للباسبور؟', 'derja', 'derja'),
    ('Chnowa lewra9 bech naamel passeport?', 'derja', None),
    ('What documents do I need for a passport?', 'en', None),
])
def test_real_multilingual_checklist(live_bridge, text, language, selected):
    bridge, sent, replies, payloads, _ = live_bridge
    if selected:
        bridge.session(1)['language'] = selected
    bridge.handle_message({'chat':{'id':1},'text':text})
    assert replies, 'Real n8n did not return a successful response'
    result = replies[-1]
    assert result['agent'] == 'checklist_builder'
    assert result['route']['language'] == language
    assert result['route']['procedure_category'] == 'passport'
    assert result['citations'] and result['found']
    assert payloads[-1]['text'] == text
    assert result['text'] in ''.join(item['text'] for item in sent)
    assert 'services.interieur.gov.tn' in ''.join(item['text'] for item in sent)


@pytest.mark.parametrize('kind', ['pdf','png','jpeg','photo'])
def test_real_official_blank_form_upload(live_bridge, kind):
    bridge, sent, replies, payloads, upload = live_bridge
    path = next((ROOT/'data/raw/rne-form-f002-legal-entity-registration').glob('*.pdf'))
    mime = {'pdf':'application/pdf','png':'image/png','jpeg':'image/jpeg','photo':'image/jpeg'}[kind]
    if kind == 'pdf':
        upload['bytes'] = path.read_bytes()
    else:
        with fitz.open(path) as document:
            pixmap = document[0].get_pixmap(dpi=200)
            upload['bytes'] = pixmap.tobytes('png' if kind == 'png' else 'jpeg')
    bridge.session(1)['language'] = 'en'
    message = {'chat':{'id':1},'caption':'neutral'}
    if kind == 'photo':
        message['photo'] = [{'file_id':'neutral','file_size':len(upload['bytes'])}]
    else:
        message['document'] = {'file_id':'neutral','mime_type':mime,'file_name':'neutral.'+kind,'file_size':len(upload['bytes'])}
    bridge.handle_message(message)
    assert replies, 'Real n8n did not return a successful response'
    result = replies[-1]
    assert result['agent'] == 'form_helper' and result['recognised']
    assert result['form_doc_id'] == 'rne-form-f002-legal-entity-registration'
    assert len(result['missing']) == 8
    assert payloads[-1]['language'] == 'en'
    combined = ''.join(item['text'] for item in sent)
    assert 'Potentially missing fields: 8' in combined
    assert 'Manual verification required' in combined

@pytest.mark.parametrize('mode', ['form','dossier'])
@pytest.mark.parametrize('kind', ['pdf','png'])
def test_real_dossier_mode_selection(live_bridge, mode, kind):
    bridge, sent, replies, payloads, upload = live_bridge
    path = next((ROOT/'data/raw/rne-form-f002-legal-entity-registration').glob('*.pdf'))
    if kind == 'pdf':
        upload['bytes'] = path.read_bytes()
    else:
        with fitz.open(path) as document:
            upload['bytes'] = document[0].get_pixmap(dpi=200).tobytes('png')
    bridge.session(1)['language'] = 'en'
    bridge.handle_message({'chat':{'id':1},'text':'/dossier_check'})
    if mode == 'form':
        bridge.handle_message({'chat':{'id':1},'text':'/form_check'})
    bridge.handle_message({'chat':{'id':1},'document':{'file_id':'neutral','file_name':'neutral.'+kind,
                          'mime_type':'application/pdf' if kind == 'pdf' else 'image/png'}})
    assert replies, 'No successful response from real n8n'
    result = replies[-1]
    assert result['recognised']
    assert result['form_doc_id'] == 'rne-form-f002-legal-entity-registration'
    text = ''.join(item['text'] for item in sent)
    assert 'https://' in text
    if mode == 'dossier':
        assert payloads[-1]['mode'] == 'dossier'
        assert result['agent'] == 'dossier_validator'
        assert result['report']['dossier']['completeness_certified'] is False
        fields = result['report']['form_fields']
        assert len(fields['missing']) == 8
        assert 'Missing fields: 8' in text
        assert f"Unreadable fields: {len(fields['unreadable'])}" in text
        assert result['citations'] and result['report']['dossier']['official_requirements']
        assert 'does not certify legal completeness or official approval' in text
    else:
        assert 'mode' not in payloads[-1]
        assert result['agent'] == 'form_helper'
        assert 'Potentially missing fields: 8' in text

@pytest.mark.parametrize('stale', [False,True])
def test_real_passport_followup_context(live_bridge, stale):
    bridge, sent, replies, payloads, _ = live_bridge
    bridge.session(1)['language'] = 'fr'
    if stale:
        bridge.session(1)['procedure'] = 'birth certificate'
    bridge.handle_message({'chat':{'id':1},'text':'Quels documents pour renouveler mon passeport ?'})
    assert replies[-1]['route']['procedure_category'] == 'passport'
    assert bridge.sessions[1]['procedure'] == 'passport'
    bridge.handle_message({'chat':{'id':1},'text':'Et si je réside à l’étranger ?'})
    assert payloads[-1]['text'].endswith('Procedure context: passport')
    result = replies[-1]
    assert result['route']['procedure_category'] == 'passport'
    assert result['route']['language'] == 'fr'
    assert 'abroad' in result['route']['hints']
    assert result['agent'] == 'checklist_builder' and result['found']
    assert result['citations']
    assert 'pas encore couverte' not in result['text']
