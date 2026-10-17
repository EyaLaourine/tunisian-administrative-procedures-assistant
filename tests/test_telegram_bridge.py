"""Isolated Telegram tests: no credentials or private documents required."""
import base64
import json
import httpx
import pytest
from telegram_bridge.bridge import TelegramBridge, split_message
from telegram_bridge.ui import COMMANDS
from telegram_bridge.contracts import AssistantRequest, AssistantResponse

TOKEN = '123:TEST'
WEBHOOK = 'http://n8n.test/webhook/assistant'

class FakeServers:
    def __init__(self):
        self.sent = []
        self.payloads = []
        self.reply = {'text': 'reply text', 'agent': 'checklist_builder'}
        self.status = 200
        self.updates = [{'update_id': 7, 'message': {'chat': {'id': 1}, 'text': 'hello'}}]
        self.file = b'\xff\xd8\xff\xe0'
    def handler(self, request):
        url = str(request.url)
        if url == WEBHOOK:
            self.payloads.append(json.loads(request.content))
            return httpx.Response(self.status, json=self.reply)
        if url.endswith('/sendMessage'):
            self.sent.append(json.loads(request.content))
        if url.endswith('/getUpdates'):
            return httpx.Response(200, json={'ok': True, 'result': self.updates})
        if url.endswith('/getFile'):
            return httpx.Response(200, json={'ok': True, 'result': {'file_path': 'files/a', 'file_size': len(self.file)}})
        if '/file/bot' in url:
            return httpx.Response(200, content=self.file)
        return httpx.Response(200, json={'ok': True, 'result': {}})

@pytest.fixture
def pair():
    server = FakeServers()
    bridge = TelegramBridge(TOKEN, WEBHOOK, 1024, client=httpx.Client(transport=httpx.MockTransport(server.handler)))
    bridge.stop.wait = lambda _: False
    return bridge, server

def message(text):
    return {'chat': {'id': 1}, 'from': {'language_code': 'en'}, 'text': text}

@pytest.mark.parametrize('command', COMMANDS)
def test_commands(pair, command):
    bridge, server = pair
    bridge.handle_message(message('/' + command))
    assert server.sent
    if command in {'passport', 'birth_certificate', 'business'}:
        assert server.payloads
    else:
        assert not server.payloads

@pytest.mark.parametrize('lang', ['en', 'fr', 'ar', 'derja'])
def test_language_callback(pair, lang):
    bridge, server = pair
    server.updates = [{'update_id': 1, 'callback_query': {'id': 'c', 'message': message(''), 'data': 'language:' + lang}}]
    bridge.poll_once()
    bridge.handle_message(message('question'))
    assert server.payloads[-1]['language'] == lang
    assert len(server.sent[0]['reply_markup']['inline_keyboard']) == 4

def test_procedure_callback_and_context(pair):
    bridge, server = pair
    server.updates = [{'update_id': 1, 'callback_query': {'id': 'c', 'message': message(''), 'data': 'procedure:passport'}}]
    for msg in bridge.poll_once():
        bridge.handle_message(msg)
    bridge.handle_message(message('renewal abroad'))
    assert 'passport' in server.payloads[-1]['text']
    bridge.handle_message(message('/cancel'))
    assert not bridge.sessions

def test_text_and_citations(pair):
    bridge, server = pair
    server.reply.update(citations=[{'url': 'https://official.example/source'}], warnings=['Source applicability unverified'])
    bridge.handle_message(message('question'))
    assert server.payloads == [{'text': 'question'}]
    assert 'https://official.example/source' in server.sent[-1]['text']
    assert 'Source applicability unverified' in server.sent[-1]['text']
    assert 'parse_mode' not in server.sent[-1]

@pytest.mark.parametrize('mime,data', [('application/pdf', b'%PDF-neutral'), ('image/png', b'\x89PNG\r\n\x1a\nneutral'), ('image/jpeg', b'\xff\xd8\xffneutral')])
def test_supported_upload(pair, mime, data):
    bridge, server = pair
    server.file = data
    bridge.handle_message({'chat': {'id': 1}, 'document': {'file_id': 'f', 'mime_type': mime, 'file_name': '../form'}})
    file = server.payloads[0]['file']
    assert file['filename'] == 'form'
    assert base64.b64decode(file['data_b64']) == data

def test_photo(pair):
    bridge, server = pair
    bridge.handle_message({'chat': {'id': 1}, 'photo': [{'file_id': 'f', 'file_size': 4}], 'caption': 'neutral'})
    assert server.payloads[0]['caption'] == 'neutral'

@pytest.mark.parametrize('doc', [ {'file_id':'f','mime_type':'application/zip'}, {'file_id':'f','mime_type':'application/pdf','file_size':1025} ])
def test_reject_upload(pair, doc):
    bridge, server = pair
    bridge.handle_message({'chat': {'id': 1}, 'document': doc})
    assert not server.payloads and server.sent

def test_reject_signature(pair):
    bridge, server = pair
    bridge.handle_message({'chat': {'id':1}, 'document': {'file_id':'f','mime_type':'application/pdf'}})
    assert not server.payloads

def test_duplicate_update(pair):
    bridge, _ = pair
    assert len(bridge.poll_once()) == 1
    assert not bridge.poll_once()
    assert bridge.offset == 8

def test_failure_and_no_sensitive_logs(pair, caplog):
    bridge, server = pair
    server.status = 500
    bridge.handle_message(message('PRIVATE QUESTION'))
    assert 'temporarily unavailable' in server.sent[-1]['text']
    assert TOKEN not in caplog.text and 'PRIVATE QUESTION' not in caplog.text

def test_timeout(pair):
    bridge, server = pair
    original = server.handler
    def handler(request):
        if str(request.url) == WEBHOOK:
            raise httpx.ReadTimeout('sensitive URL ' + TOKEN)
        return original(request)
    bridge.client = httpx.Client(transport=httpx.MockTransport(handler))
    bridge.handle_message(message('question'))
    assert 'temporarily unavailable' in server.sent[-1]['text']

def test_rate_limit(pair):
    bridge, _ = pair
    calls = []
    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, json={'ok':False,'error_code':429,'parameters':{'retry_after':1}})
        return httpx.Response(200, json={'ok':True,'result':{}})
    bridge.client = httpx.Client(transport=httpx.MockTransport(handler))
    bridge.send_text(1,'hello')
    assert len(calls) == 2

def test_missing_token():
    with pytest.raises(ValueError, match='TELEGRAM_BOT_TOKEN'):
        TelegramBridge('', WEBHOOK, 1024)

def test_contracts():
    with pytest.raises(ValueError):
        AssistantRequest(text='a'*2001)
    with pytest.raises(ValueError):
        AssistantResponse(text=42)

def test_split():
    assert split_message('x'*1200, 500) == ['x'*500, 'x'*500, 'x'*200]
    assert all(len(p.encode('utf-16-le'))//2 <= 4000 for p in split_message('😀'*5000))

def test_stream_limit(pair):
    bridge, server = pair
    server.file = b'x'*1025
    with pytest.raises(ValueError):
        bridge.download_file('f')

def test_session_expiry(pair):
    import time
    bridge, server = pair
    bridge.sessions[1] = {'seen': time.monotonic()-1801, 'language':'ar', 'procedure':'passport'}
    bridge.handle_message(message('question'))
    assert server.payloads[-1] == {'text':'question'}

def test_poll_conflict(pair):
    from telegram_bridge.bridge import PollingConflict
    bridge, _ = pair
    bridge.client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(409, json={'ok':False,'error_code':409})))
    with pytest.raises(PollingConflict):
        bridge.poll_once()

def test_telegram_api_failure(pair, caplog):
    bridge, _ = pair
    bridge.client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(401, json={'ok':False})))
    bridge.handle_message(message('PRIVATE QUESTION'))
    assert 'telegram_send_failed' in caplog.text
    assert TOKEN not in caplog.text and 'PRIVATE QUESTION' not in caplog.text

def test_missing_token_entrypoint(monkeypatch, capsys):
    from types import SimpleNamespace
    import telegram_bridge.__main__ as entry
    monkeypatch.setattr(entry, 'get_settings', lambda: SimpleNamespace(log_level='INFO', telegram_bot_token=None))
    assert entry.main() == 2
    assert 'TELEGRAM_BOT_TOKEN' in capsys.readouterr().err

@pytest.mark.parametrize('data', ['menu:main', 'menu:new', 'menu:procedures', 'menu:language', 'menu:form_check'])
def test_navigation_callbacks(pair, data):
    bridge, server = pair
    bridge.sessions[1] = {'seen': __import__('time').monotonic(), 'language':'fr', 'procedure':'passport'}
    server.updates = [{'update_id':1,'callback_query':{'id':'c','message':message(''),'data':data}}]
    for msg in bridge.poll_once():
        bridge.handle_message(msg)
    assert server.sent[-1]['reply_markup']['inline_keyboard']
    if data == 'menu:new':
        assert 'procedure' not in bridge.sessions[1]
        assert bridge.sessions[1]['language'] == 'fr'
    assert not server.payloads

@pytest.mark.parametrize('text', [
    'Quels documents pour renouveler mon passeport ?',
    'شنوما الأوراق اللازمة للباسبور؟',
    'Chnowa lewra9 bech naamel passeport?',
    'What documents do I need for a passport?',
])
def test_multilingual_input_preserved(pair, text):
    bridge, server = pair
    bridge.handle_message(message(text))
    assert server.payloads[-1]['text'] == text
    assert 'language' not in server.payloads[-1]

@pytest.mark.parametrize('reply', [{}, {'text':None}, {'text':42}, {'text':'x','citations':'bad'}, {'text':'x','route':None}])
def test_malformed_backend_reply(pair, reply):
    bridge, server = pair
    server.reply = reply
    bridge.handle_message(message('question'))
    assert 'temporarily unavailable' in server.sent[-1]['text']

def test_long_answer_single_navigation(pair):
    bridge, server = pair
    server.reply = {'text':'😀'*6000}
    bridge.handle_message(message('question'))
    assert len(server.sent) == 3
    assert all(len(m['text'].encode('utf-16-le'))//2 <= 4000 for m in server.sent)
    assert sum('reply_markup' in m for m in server.sent) == 1

def test_long_question_local_help(pair):
    bridge, server = pair
    bridge.handle_message(message('x'*2001))
    assert not server.payloads
    assert '2,000' in server.sent[-1]['text']

@pytest.mark.parametrize('recognised,error,missing,expected', [
    (True,None,['neutral field'],'Potentially missing fields: 1'),
    (True,None,[],'No potentially missing fields'),
    (False,None,[],'not recognised'),
    (False,'neutral read failure',[],'could not be read reliably'),
])
def test_form_status_distinctions(pair, recognised, error, missing, expected):
    bridge, server = pair
    server.reply = {'agent':'form_helper','text':'neutral result','recognised':recognised,'error':error,'missing':missing}
    bridge.handle_message(message('neutral'))
    text = server.sent[-1]['text']
    assert expected in text
    assert 'Manual verification required' in text


def test_unknown_command_is_local_help(pair):
    bridge, server = pair
    bridge.handle_message(message('/unknown'))
    assert not server.payloads
    assert '/help' in server.sent[-1]['text']

def test_checklist_adds_intent_without_agent_logic(pair):
    bridge, server = pair
    bridge.handle_message(message('/checklist'))
    bridge.handle_message(message('business registration'))
    assert server.payloads[-1]['text'] == 'Required documents: business registration'


def test_menu_send_failure_does_not_stop_handler(pair, caplog):
    bridge, server = pair
    bridge.client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(401,json={'ok':False})))
    bridge.handle_message(message('/start'))
    assert 'telegram_send_failed' in caplog.text
    assert TOKEN not in caplog.text


def test_token_not_in_api_exception(pair):
    bridge, server = pair
    from telegram_bridge.bridge import TelegramAPIError
    bridge.client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(401,json={'ok':False})))
    with pytest.raises(TelegramAPIError) as exc:
        bridge.api('getMe')
    assert TOKEN not in str(exc.value)
    assert 'https://' not in str(exc.value)


def test_missing_token_idle_mode(monkeypatch, tmp_path, capsys):
    import threading
    import telegram_bridge.__main__ as entry
    stop = threading.Event()
    monkeypatch.setattr(entry,'HEALTH_FILE',tmp_path/'health')
    stop.wait = lambda _: stop.set()
    assert entry.wait_without_token(stop) == 0
    assert (tmp_path/'health').exists()
    assert 'LIVE_CONNECTIVITY_PENDING' in capsys.readouterr().out


def test_cancel_suppresses_inflight_response(pair):
    import threading
    bridge, server = pair
    entered, release, done = threading.Event(), threading.Event(), threading.Event()
    original = server.handler
    def handler(request):
        if str(request.url) == WEBHOOK:
            entered.set()
            assert release.wait(5)
        return original(request)
    bridge.client = httpx.Client(transport=httpx.MockTransport(handler))
    cancelled = threading.Event()
    bridge.inflight[1] = cancelled
    def work():
        try:
            bridge.handle_message(message('neutral'),cancelled)
        finally:
            done.set()
    thread = threading.Thread(target=work)
    thread.start()
    assert entered.wait(5)
    bridge.handle_message(message('/cancel'))
    assert cancelled.is_set()
    release.set()
    assert done.wait(5)
    thread.join()
    assert all(m['text'] != 'reply text' for m in server.sent)
    assert not bridge.sessions


def test_backend_wire_schema_compatibility():
    from agents.schemas import RouteRequest, FormCheckRequest
    payload = AssistantRequest(text='neutral',language='fr').model_dump(exclude_none=True)
    assert RouteRequest.model_validate(payload).language == 'fr'
    payload = AssistantRequest(file={'filename':'neutral.pdf','mime_type':'application/pdf','data_b64':'bmV1dHJhbA=='}).model_dump(exclude_none=True)
    assert FormCheckRequest.model_validate(payload['file']).filename == 'neutral.pdf'


def test_callback_session_retention_bound(pair):
    import time
    bridge, server = pair
    bridge.sessions = {i:{'seen':time.monotonic(),'language':'en'} for i in range(1000)}
    server.updates = [{'update_id':1,'callback_query':{'id':'c','message':{'chat':{'id':2000}},'data':'language:fr'}}]
    bridge.poll_once()
    assert len(bridge.sessions) == 1000

@pytest.mark.parametrize('kind', ['status','timeout'])
def test_download_errors_are_safe(pair, kind):
    bridge, server = pair
    original = server.handler
    def handler(request):
        if '/file/bot' in str(request.url):
            if kind == 'timeout':
                raise httpx.ReadTimeout('sensitive ' + TOKEN)
            return httpx.Response(404,json={})
        return original(request)
    bridge.client = httpx.Client(transport=httpx.MockTransport(handler))
    from telegram_bridge.bridge import TelegramAPIError
    with pytest.raises(TelegramAPIError) as exc:
        bridge.download_file('neutral')
    assert TOKEN not in str(exc.value)


def test_rate_limit_honors_long_retry_after(pair):
    bridge, _ = pair
    calls, delays = [], []
    bridge.stop.wait = lambda delay: delays.append(delay)
    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429,json={'ok':False,'error_code':429,'parameters':{'retry_after':120}})
        return httpx.Response(200,json={'ok':True,'result':{}})
    bridge.client = httpx.Client(transport=httpx.MockTransport(handler))
    bridge.send_text(1,'neutral')
    assert delays == [120]


def test_startup_and_graceful_cleanup(pair, monkeypatch):
    import socket
    bridge, server = pair
    methods = []
    def handler(request):
        method = request.url.path.rsplit('/',1)[-1]
        methods.append(method)
        if method == 'getUpdates':
            bridge.stop.set()
            return httpx.Response(200,json={'ok':True,'result':[]})
        if method == 'setMyCommands':
            assert {item['command'] for item in json.loads(request.content)['commands']} == set(COMMANDS)
        return httpx.Response(200,json={'ok':True,'result':{}})
    bridge.client = httpx.Client(transport=httpx.MockTransport(handler))
    class Lock:
        def bind(self, address):
            assert address[0] == '127.0.0.1'
        def close(self):
            pass
    monkeypatch.setattr(socket,'socket',lambda:Lock())
    bridge.run_forever()
    assert methods == ['getMe','setMyCommands','deleteWebhook','getUpdates']
    assert bridge.client.is_closed and bridge.stop.is_set() and not bridge.sessions


def test_overlapping_requests_receive_busy_reply(pair):
    import threading
    bridge, server = pair
    entered, release, complete = threading.Event(), threading.Event(), threading.Event()
    bridge.session(1)['language'] = 'en'
    original = server.handler
    def handler(request):
        if str(request.url) == WEBHOOK:
            entered.set()
            assert release.wait(5)
        return original(request)
    bridge.client = httpx.Client(transport=httpx.MockTransport(handler))
    original_handle = bridge.handle_message
    def handle(*args):
        try:
            original_handle(*args)
        finally:
            complete.set()
    bridge.handle_message = handle
    bridge.dispatch_message(message('neutral first'))
    assert entered.wait(5)
    bridge.dispatch_message(message('neutral second'))
    assert any('still running' in m['text'] for m in server.sent)
    release.set()
    assert complete.wait(5)
    assert len(server.payloads) == 1


def test_deployment_and_workflow_contract():
    from pathlib import Path
    import yaml
    root = Path(__file__).resolve().parents[1]
    compose = yaml.safe_load((root/'docker-compose.yml').read_text(encoding='utf-8'))
    bridge = compose['services']['telegram-bridge']
    assert bridge['image'] != compose['name']+'-backend'
    assert bridge['build']['dockerfile'] == 'telegram_bridge/Dockerfile'
    assert bridge['profiles'] == ['telegram'] and bridge['restart'] == 'unless-stopped'
    assert 'ports' not in bridge and 'env_file' not in bridge
    assert '--wait-for-token' in bridge['command']
    assert 'TELEGRAM_BOT_TOKEN=' in (root/'.env.example').read_text(encoding='utf-8')
    workflow = json.loads((root/'workflows/03_assistant_multi_agent.json').read_text(encoding='utf-8'))
    assert workflow['settings']['saveDataSuccessExecution'] == 'none'
    assert workflow['settings']['saveDataErrorExecution'] == 'none'
    webhook = next(n for n in workflow['nodes'] if n['type'] == 'n8n-nodes-base.webhook')
    assert webhook['parameters']['path'] == 'assistant'

@pytest.mark.parametrize('selected,expected', [(None,'القائمة الرئيسية'),('en','Main menu')])
def test_navigation_uses_selected_or_backend_language(pair, selected, expected):
    bridge, server = pair
    if selected:
        bridge.session(1)['language'] = selected
    server.reply = {'text':'neutral','route':{'language':'ar'}}
    bridge.handle_message(message('neutral'))
    assert server.sent[-1]['reply_markup']['inline_keyboard'][0][0]['text'] == expected

@pytest.mark.parametrize('language', ['en','fr','ar','derja'])
def test_dossier_multilingual_menu_and_callback(pair, language):
    from telegram_bridge.ui import main_keyboard, TEXT
    bridge, server = pair
    bridge.session(1)['language'] = language
    buttons = [button for row in main_keyboard(language)['inline_keyboard'] for button in row]
    assert any(b['text'] == TEXT[language]['dossier_title'] and b['callback_data'] == 'menu:dossier_check' for b in buttons)
    assert any(b['callback_data'] == 'menu:form_check' for b in buttons)
    server.updates = [{'update_id':1,'callback_query':{'id':'neutral','message':message(''),'data':'menu:dossier_check'}}]
    for msg in bridge.poll_once():
        bridge.handle_message(msg)
    assert bridge.sessions[1]['upload_mode'] == 'dossier'
    assert TEXT[language]['dossier_title'] in server.sent[-1]['text']
    assert not server.payloads


@pytest.mark.parametrize('kind,data,mime', [
    ('pdf',b'%PDF-neutral','application/pdf'),
    ('png',b'\x89PNG\r\n\x1a\nneutral','image/png'),
    ('jpeg',b'\xff\xd8\xffneutral','image/jpeg'),
    ('photo',b'\xff\xd8\xffneutral','image/jpeg'),
])
def test_dossier_and_form_upload_modes(pair, kind, data, mime):
    bridge, server = pair
    server.file = data
    attachment = {'photo':[{'file_id':'neutral','file_size':len(data)}]} if kind == 'photo' else {
        'document':{'file_id':'neutral','mime_type':mime,'file_name':'neutral.'+kind}}
    msg = {'chat':{'id':1},**attachment}
    bridge.handle_message(message('/dossier_check'))
    bridge.handle_message(msg)
    assert server.payloads[-1]['mode'] == 'dossier'
    assert server.payloads[-1]['file']['mime_type'] == mime
    bridge.handle_message(message('neutral question'))
    assert server.payloads[-1] == {'text':'neutral question'}
    bridge.handle_message(message('/form_check'))
    bridge.handle_message(msg)
    assert 'mode' not in server.payloads[-1]
    bridge.handle_message(message('/dossier_check'))
    bridge.handle_message(message('/cancel'))
    bridge.handle_message(msg)
    assert 'mode' not in server.payloads[-1]


def neutral_dossier_reply():
    return {'agent':'dossier_validator','text':'Original official evidence: neutral quotation.', 'recognised':True,
            'citations':[{'url':'https://official.example/source'}],
            'report':{'form_fields':{'filled':['neutral filled'],'missing':['neutral missing'],
                                    'unreadable':['neutral unreadable'],'cannot_verify':['neutral unknown']},
                      'dossier':{'official_requirements':[{'id':'neutral-a','status':'supported_by_official_source','note':'neutral supported'},
                                                         {'id':'neutral-b','status':'official_requirement_unavailable','note':'neutral unavailable'},
                                                         {'id':'neutral-c','status':'not_verified','note':'neutral unverified'}],
                                 'requirements_not_verified':['neutral check'], 'completeness_certified':False},
                      'readiness_summary':'neutral readiness','limitations':['neutral limitation']}}


@pytest.mark.parametrize('language', ['en','fr','ar','derja'])
def test_dossier_report_format_and_private_logs(pair, language, caplog):
    import logging
    from telegram_bridge.ui import TEXT
    bridge, server = pair
    bridge.session(1)['language'] = language
    server.reply = neutral_dossier_reply()
    with caplog.at_level(logging.INFO):
        bridge.handle_message(message('PRIVATE VALUE'))
    text = ''.join(item['text'] for item in server.sent)
    for key in ['dossier_filled','dossier_missing','dossier_unreadable','dossier_unverifiable','dossier_supported']:
        assert TEXT[language][key] + ': 1' in text
    assert TEXT[language]['dossier_unverified'] in text
    assert 'neutral unavailable' in text and 'neutral unverified' in text and 'neutral check' in text
    assert server.reply['text'] in text and 'neutral readiness' in text and 'neutral limitation' in text
    assert TEXT[language]['dossier_disclaimer'] in text
    assert 'https://official.example/source' in text
    assert 'PRIVATE VALUE' not in caplog.text and 'neutral filled' not in caplog.text


@pytest.mark.parametrize('error', [None,'neutral decoding failure'])
def test_dossier_unsupported_and_unreadable(pair, error):
    bridge, server = pair
    server.reply = {'text':'neutral unsupported','agent':'dossier_validator','recognised':False,'error':error,
                    'report':{'form_fields':{'filled':[],'missing':[],'unreadable':[],'cannot_verify':[]}}}
    bridge.handle_message(message('neutral'))
    text = ''.join(item['text'] for item in server.sent)
    assert 'Not assessed / not reported' in text
    assert 'could not be read reliably' in text if error else 'not recognised' in text
    assert 'does not certify legal completeness or official approval' in text


def test_dossier_rejects_false_certification_and_malformed_fields(pair):
    bridge, server = pair
    server.reply = neutral_dossier_reply()
    server.reply['report']['dossier']['completeness_certified'] = True
    bridge.handle_message(message('neutral'))
    assert 'temporarily unavailable' in server.sent[-1]['text']
    server.reply = neutral_dossier_reply()
    server.reply['report']['form_fields']['filled'] = 'not a list'
    bridge.handle_message(message('neutral'))
    assert 'temporarily unavailable' in server.sent[-1]['text']
    with pytest.raises(ValueError):
        AssistantRequest(text='neutral',mode='dossier')


def test_new_question_clears_dossier_mode(pair):
    bridge, server = pair
    bridge.handle_message(message('/dossier_check'))
    server.updates = [{'update_id':1,'callback_query':{'id':'neutral','message':message(''),'data':'menu:new'}}]
    bridge.poll_once()
    assert 'upload_mode' not in bridge.sessions[1]


@pytest.mark.parametrize('doc', [
    {'file_id':'neutral','mime_type':'application/zip'},
    {'file_id':'neutral','mime_type':'application/pdf','file_size':1025},
    {'file_id':'neutral','mime_type':'application/pdf'},
])
def test_dossier_bad_upload_does_not_reach_n8n(pair, doc):
    bridge, server = pair
    bridge.handle_message(message('/dossier_check'))
    bridge.handle_message({'chat':{'id':1},'document':doc})
    assert not server.payloads

@pytest.mark.parametrize('stale', [None,'birth certificate'])
def test_latest_routed_procedure_is_retained_for_followup(pair, stale):
    bridge, server = pair
    bridge.session(1)['language'] = 'fr'
    if stale:
        bridge.session(1)['procedure'] = stale
    server.reply = {'text':'neutral answer','route':{'procedure_category':'passport','language':'fr'}}
    bridge.handle_message(message('Quels documents pour renouveler mon passeport ?'))
    assert bridge.sessions[1]['procedure'] == 'passport'
    bridge.handle_message(message('Et si je réside à l’étranger ?'))
    assert server.payloads[-1]['language'] == 'fr'
    assert server.payloads[-1]['text'].endswith('Procedure context: passport')
    assert 'birth certificate' not in server.payloads[-1]['text']
    assert set(bridge.sessions[1]) <= {'seen','language','procedure'}


def test_unvalidated_route_category_is_not_retained(pair):
    bridge, server = pair
    server.reply = {'text':'neutral answer','route':{'procedure_category':'PRIVATE VALUE'}}
    bridge.handle_message(message('neutral'))
    assert 'procedure' not in bridge.sessions[1]


def test_structured_dialogue_bridge_forwards_context_and_clears_it(pair):
    bridge, server = pair
    bridge.dialogue_enabled = True
    ctx={'category':'passport','hints':['renewal'],'residence':None,'declared_items':[], 'pending_intent':'required_documents'}
    server.reply={'text':'neutral clarification','agent':'intent_router','context':ctx,'route':{'procedure_category':'passport','language':'fr'}}
    bridge.handle_message(message('Quels documents pour renouveler mon passeport ?'))
    assert server.payloads[-1]['context']['declared_items'] == []
    assert bridge.sessions[1]['dialogue']['hints'] == ['renewal']
    ctx={**ctx,'declared_items':[{'key':'photos','quantity':4}]}
    server.reply={**server.reply,'context':ctx}
    bridge.handle_message(message('3andi 4 souwar'))
    assert server.payloads[-1]['context']['category'] == 'passport'
    assert 'Procedure context:' not in server.payloads[-1]['text']
    assert bridge.sessions[1]['dialogue']['declared_items'] == [{'key':'photos','quantity':4}]
    bridge.handle_message(message('/cancel'))
    assert not bridge.sessions
