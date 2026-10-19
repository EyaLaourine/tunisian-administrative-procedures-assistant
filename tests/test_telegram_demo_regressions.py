"""Regressions for the 19 October manual Telegram findings; no real messaging or services."""
import base64
from pathlib import Path

import fitz
import pytest

from agents import i18n
from agents.answer import GroundedAnswerer
from agents.checklist_arabic import translate_cin
from agents.checklist_builder import ChecklistBuilder, _same_numbers
from agents.corpus import Corpus
from agents.dossier_validator import DossierValidator
from agents.form_helper import FormHelper
from agents.prompts import PromptLibrary
from agents.schemas import ComposeRequest, FormCheckRequest, RouteDecision
from backend.settings import REPO_ROOT, get_settings
from rag.retrieval import RetrievedPassage
from telegram_bridge.contracts import AssistantResponse
from telegram_bridge.dossier import render_dossier

CIN = 'interior-national-id-application-form'
F001 = 'rne-form-f001-natural-person-registration'

@pytest.fixture(scope='module')
def services():
    s = get_settings()
    corpus = Corpus(s.raw_dir, s.processed_dir)
    helper = FormHelper(corpus, s.max_upload_bytes)
    prompts = PromptLibrary(REPO_ROOT / 'prompts')
    builder = ChecklistBuilder(corpus, None, prompts)
    return corpus, helper, builder, DossierValidator(helper, builder, corpus), prompts


def request(corpus, doc_id, lang='en', data=None):
    data = data or (REPO_ROOT / corpus.records()[doc_id].file_path).read_bytes()
    return FormCheckRequest(language=lang, mime_type='application/pdf', data_b64=base64.b64encode(data).decode())


def passage(corpus, doc_id, index=0):
    scenario = corpus.scenarios(doc_id)[index]
    return RetrievedPassage(score=.9, text='\n'.join(item for s in scenario.sections for item in s.items),
                            chunk_id=doc_id+str(index), citation=corpus.citation(doc_id, scenario.path))


@pytest.mark.parametrize('language', ['en','fr','ar','derja'])
def test_blank_cin_counts_survive_dossier_wire_and_bridge(services, language):
    corpus, helper, _, validator, _ = services
    req = request(corpus, CIN, language)
    checked = helper.check(req)
    def forbidden(*args):
        raise AssertionError('No invented dossier retrieval for a form without rules')
    report = validator.validate(req, forbidden)
    assert len(report.missing_fields) == len(checked.missing) == 10
    assert len(report.unverifiable_fields) == len(checked.manual_verification) == 6
    assert len([f for f in report.recognized_fields if f.status == 'if_applicable']) == 3
    assert not any(f.role == 'administration' for f in report.recognized_fields)
    assert report.official_requirements == [] and not report.official_checklist_available
    assert report.requirements_not_verified and report.readiness_summary
    assert report.source_references[0].doc_id == CIN
    # Existing WF03 mapping, unchanged: no workflow deployment required.
    response = AssistantResponse(text=report.text, recognised=True, agent='dossier_validator', report={
        'form_fields': {'filled':report.filled_fields,'missing':report.missing_fields,
                        'unreadable':report.unreadable_fields,'cannot_verify':report.unverifiable_fields},
        'dossier': {'official_checklist_available':report.official_checklist_available,
                    'official_requirements':report.official_requirements,
                    'requirements_not_verified':report.requirements_not_verified},
        'readiness_summary':report.readiness_summary, 'limitations':report.limitations})
    rendered = render_dossier(response, language)
    from telegram_bridge.ui import TEXT
    assert TEXT[language]['dossier_missing']+': 10' in rendered
    assert TEXT[language]['dossier_unverifiable']+': 6' in rendered
    assert TEXT[language]['dossier_completeness_unavailable'] in rendered
    assert all(label in rendered for label in checked.missing + checked.if_applicable)


@pytest.mark.parametrize('language', ['ar','derja'])
@pytest.mark.parametrize('scenario,hints', [(0,[]),(1,['renewal']),(2,['modification']),(3,['loss'])])
def test_all_cin_scenarios_translate_arabic_without_model(services,language,scenario,hints):
    corpus,_,builder,_,_ = services
    route = RouteDecision(language=language,intent='required_documents',procedure_category='national_id',
                          hints=hints,next_agent='checklist',method='rules')
    result = builder.build(ComposeRequest(query='بطاقة التعريف',route=route,
                           passages=[passage(corpus,'interior-national-id-guide-fr',scenario)]))
    assert result.found and result.translation['method'] == 'explicit_cin_ar_v1'
    assert result.translation['validated']
    assert all(s.translated_items and len(s.items)==len(s.translated_items) for s in result.sections)
    assert all(_same_numbers(a,b) for s in result.sections for a,b in zip(s.items,s.translated_items))
    assert all(any('\u0600' <= c <= '\u06ff' for c in item) for s in result.sections for item in s.translated_items)
    assert result.citations[0].doc_id == 'interior-national-id-guide-fr'
    assert i18n.t('application_translation',language,source=i18n.SOURCE_LANGUAGE_LABEL['fr']) in result.text
    if scenario == 2:
        assert 'بالنسبة للأرملة' in result.text and 'العوراء' not in result.text


@pytest.mark.parametrize('language',['ar','derja'])
def test_unknown_translation_is_explicit_atomic_fallback(services,language):
    _,_,builder,_,_ = services
    assert translate_cin(['Unknown changed source text']) is None
    from agents.schemas import ChecklistSection
    sections=[ChecklistSection(kind='documents',heading='Pièces',items=['Unknown changed source text'])]
    title,metadata=builder._translate('Changed title',sections,'fr','ar','interior-national-id-guide-fr')
    assert not metadata['validated'] and sections[0].translated_items is None
    from agents.schemas import ChecklistResult
    r=ChecklistResult(text='',found=True,source_language='fr',sections=sections,translation=metadata)
    route=RouteDecision(language=language,procedure_category='national_id',intent='required_documents',next_agent='checklist',method='rules')
    assert i18n.t('translation_unavailable',language,source=i18n.SOURCE_LANGUAGE_LABEL['fr']) in builder._render(route,title,r)


def test_partial_rne_missing_fields_and_signature_are_separate(services):
    corpus,helper,_,_,_=services
    blank=(REPO_ROOT/corpus.records()[F001].file_path).read_bytes()
    template=helper.templates()[F001]
    # Fill exactly three applicant fields with neutral placeholders; leave date, contact and depositor ID empty.
    with fitz.open(stream=blank,filetype='pdf') as doc:
        for f in template.fields:
            if f.label.startswith(('Nom du Déposant /','Nom et Prénom (s) /','N°Identité /')):
                doc[f.page].insert_text((f.region[0]+12,f.region[3]-4),'PLACEHOLDER',fontsize=9)
        result=helper.check(request(corpus,F001,data=doc.tobytes()))
    assert result.recognised and result.form_doc_id == F001
    assert result.manual_verification and any('إمضاء' in x for x in result.manual_verification)
    assert i18n.t('form_not_checked','en') in result.text
    assert not any('إمضاء' in x for x in result.missing)
    assert all(f.status in {'filled','empty','not_found'} for f in result.fields)
    assert len(result.missing) == 4
    assert any('التاريخ' == x for x in result.missing)
    assert any('Identité du Déposant' in x for x in result.missing)
    assert any('E-mail' in x for x in result.missing)
    assert any('GSM' in x for x in result.missing)


@pytest.mark.parametrize('language',['en','fr','ar','derja'])
@pytest.mark.parametrize('intent',['fees','required_documents'])
def test_passport_conflict_all_languages_and_retrieval_languages(services,language,intent):
    corpus,_,builder,_,_=services
    route=RouteDecision(language=language,intent=intent,procedure_category='passport',next_agent='checklist',method='rules')
    for doc in ['interior-passport-guide-fr','interior-passport-guide-ar']:
        result=builder.build(ComposeRequest(query='passport',route=route,passages=[passage(corpus,doc)]))
        assert result.warnings and '20/60' in result.text and '25/80' in result.text
        assert {c.doc_id for c in result.citations} == {'interior-passport-guide-fr','interior-passport-guide-ar'}


@pytest.mark.parametrize('language',['fr','ar'])
def test_freeform_passport_fee_fallback_also_warns(services,language):
    corpus,_,_,_,prompts=services
    route=RouteDecision(language=language,intent='fees',procedure_category='passport',next_agent='answer',method='rules')
    result=GroundedAnswerer(None,prompts,corpus=corpus).answer(ComposeRequest(query='passport fee',route=route,
              passages=[passage(corpus,'interior-passport-guide-fr')]))
    assert result.found and '20/60' in result.text and '25/80' in result.text
    assert len(result.citations)==2


def test_model_timing_logs_only_metadata(monkeypatch, caplog):
    import httpx
    import logging
    from agents.llm import OllamaChatClient
    from agents.prompts import PromptSpec
    original_client = httpx.Client
    def handler(req):
        return httpx.Response(200,json={'message':{'content':'PRIVATE_REPLY'},'load_duration':1000000,
                                       'prompt_eval_duration':2000000,'eval_duration':3000000,'eval_count':7})
    monkeypatch.setattr('agents.llm.httpx.Client',lambda **kw:original_client(transport=httpx.MockTransport(handler),**kw))
    with caplog.at_level(logging.INFO):
        result=OllamaChatClient('http://model.test','test-model').run(
            PromptSpec(name='neutral',version='v1',user_template='{question}'),question='PRIVATE_QUESTION')
    fields=next(r.fields for r in caplog.records if r.getMessage()=='llm_timing')
    assert fields['load_duration_ms']==1 and fields['prompt_eval_duration_ms']==2 and fields['eval_duration_ms']==3
    assert fields['eval_tokens']==7 and fields['ms']>=0
    assert 'PRIVATE_' not in str(fields)
    assert result.text=='PRIVATE_REPLY'


def test_embedding_timing_does_not_log_text(monkeypatch,caplog):
    import httpx
    import logging
    from rag.embeddings import OllamaEmbeddingClient
    original_client=httpx.Client
    def handler(req):
        return httpx.Response(200,json={'embeddings':[[0.1,0.2]]})
    monkeypatch.setattr('rag.embeddings.httpx.Client',lambda **kw:original_client(transport=httpx.MockTransport(handler),**kw))
    with caplog.at_level(logging.INFO):
        assert OllamaEmbeddingClient('http://model.test','test-model',2).embed(['PRIVATE_INPUT'])==[[0.1,0.2]]
    fields=next(r.fields for r in caplog.records if r.getMessage()=='embedding_timing')
    assert fields['items']==1 and fields['ms']>=0 and 'PRIVATE_' not in str(fields)


def test_bridge_webhook_timing_and_start_no_real_telegram(caplog):
    import httpx
    import json
    import logging
    from telegram_bridge.bridge import TelegramBridge
    def handler(req):
        if str(req.url)=='http://assistant.test/webhook/assistant':
            return httpx.Response(200,json={'text':'neutral reply','agent':'checklist_builder'})
        return httpx.Response(200,json={'ok':True,'result':{}})
    bridge=TelegramBridge('123:TEST','http://assistant.test/webhook/assistant',1024,
                          client=httpx.Client(transport=httpx.MockTransport(handler)))
    with caplog.at_level(logging.INFO):
        bridge.handle_message({'chat':{'id':1},'text':'/start'})
        bridge.handle_message({'chat':{'id':1},'text':'PRIVATE_QUESTION'})
    fields=next(r.fields for r in caplog.records if r.getMessage()=='telegram_message_answered')
    assert fields['webhook_ms']>=0 and fields['webhook_attempts']==1
    assert 'PRIVATE_' not in str(fields)
