"""Regressions derived from unchanged official sources and the original audit."""
import json
from pathlib import Path

import pytest

from agents.checklist_builder import ChecklistBuilder
from agents.corpus import Corpus
from agents.intent_router import IntentRouter, _normalize, _rule_intent
from agents.legal_evidence import articles, legal_reply
from agents.prompts import PromptLibrary
from agents.schemas import ComposeRequest, DialogueContext, RouteRequest
from backend.settings import REPO_ROOT, get_settings
from rag.retrieval import RetrievedPassage

SUITE = json.loads((REPO_ROOT / 'data/evaluation/full_document_coverage.json').read_text(encoding='utf-8'))
ROWS = [c for c in SUITE['tests'] if c['kind'] in {'formalities_row', 'formalities_row_dialogue'}]


@pytest.fixture(scope='module')
def components():
    settings = get_settings()
    corpus = Corpus(settings.raw_dir, settings.processed_dir)
    prompts = PromptLibrary(REPO_ROOT / 'prompts')
    return corpus, IntentRouter(None, prompts, False), ChecklistBuilder(corpus, None, prompts)


@pytest.mark.parametrize('case', ROWS, ids=lambda c: c['id'])
def test_original_rne_rows_with_and_without_context(components, case):
    corpus, router, builder = components
    route = router.route(RouteRequest(text=case['question'], language=case['language'], context=case['conversation_context']))
    # Retrieval can rank an unrelated row first. Exact codes still determine identity.
    passage = RetrievedPassage(score=.7, chunk_id='neutral', text=corpus.blocks('rne-formalities-procedure-table')[0]['text'], citation=corpus.citation('rne-formalities-procedure-table'))
    result = builder.build(ComposeRequest(query=case['question'], route=route, passages=[passage]))
    assert result.found and result.sections
    assert all(span in result.text for span in case['required_verbatim_spans'])
    first_line = case['official_supporting_passage'].splitlines()[0]
    assert first_line in result.text
    assert len([s for s in result.sections if s.kind == 'other']) == 1


def test_existing_rne_context_keeps_code_and_correction_replaces_it(components):
    _, router, _ = components
    first = router.route(RouteRequest(text=ROWS[0]['question'], context={}, language='fr'))
    follow = router.route(RouteRequest(text='Et le délai ?', context=first.context, language='fr'))
    assert first.context.rne_code == follow.context.rne_code
    assert follow.context.rne_code in follow.retrieval_query
    changed = router.route(RouteRequest(text=ROWS[2]['question'], context=first.context, language='fr'))
    assert changed.context.rne_code != first.context.rne_code
    assert first.context.rne_code not in changed.retrieval_query


@pytest.mark.parametrize('case', [c for c in SUITE['tests'] if c['kind'] in {'guide_scenario', 'guide_fee', 'fresh_cin_profile', 'fresh_passport_profile'}], ids=lambda c:c['id'])
def test_original_guide_scenarios(components, case):
    corpus, router, builder = components
    route = router.route(RouteRequest(text=case['question'], language=case['language'], context=case['conversation_context']))
    assert route.intent == case['expected_intent']
    passage = RetrievedPassage(score=.7, chunk_id='neutral', text='neutral', citation=corpus.citation(case['document_id']))
    result = builder.build(ComposeRequest(query=case['question'], route=route, passages=[passage]))
    index = int(case['procedure'].rsplit(':', 1)[-1])
    assert result.scenario == corpus.scenarios(case['document_id'])[index].title
    assert all(span in result.text for span in case['required_verbatim_spans'])


def test_legal_context_has_only_allowlisted_subject_and_isolation(components):
    _, router, _ = components
    first = router.route(RouteRequest(text='Who can access beneficial ownership information?', context={}, language='en'))
    follow = router.route(RouteRequest(text='And under what conditions?', context=first.context, language='en'))
    assert first.context.legal_subject == follow.context.legal_subject == 'rne-arrete-2026-35'
    assert follow.next_agent == 'answer'
    assert '13 janvier 2026' in follow.retrieval_query
    other = router.route(RouteRequest(text='RNE C 012 : frais ?', context={}, language='fr'))
    assert other.context.legal_subject is None
    assert first.context.rne_code is None
    change = router.route(RouteRequest(text='Et la réservation du nom commercial ?', context=follow.context, language='fr'))
    assert change.context.legal_subject == 'rne-decree-name-reservation'
    reset = router.route(RouteRequest(text='Quels documents pour une première CIN ?', context=change.context, language='fr'))
    assert reset.context.legal_subject is None


@pytest.mark.parametrize('doc', ['rne-arrete-2026-35', 'rne-law-2018-52-ar', 'rne-decree-beneficial-owners', 'rne-decree-name-reservation', 'rne-decree-2022-298-fees-fr', 'rne-decree-law-2022-18-fr'])
def test_legal_quotations_are_complete_source_article_bodies(components, doc):
    corpus, router, _ = components
    from agents.legal_evidence import subject_query
    blocks = corpus.blocks(doc)
    sections = articles(blocks)
    assert sections
    # Explicit article identity must not drift to an adjacent provision.
    for section in sections:
        question = subject_query(doc) + ' article ' + str(section['number'])
        route = router.route(RouteRequest(text=question, context=DialogueContext(category='business_registration', legal_subject=doc), language='fr'))
        result = legal_reply(ComposeRequest(query=question, route=route, passages=[]), corpus)
        assert result.found
        assert result.verification['legal']['articles'] == [section['number']]
        assert all(part in result.text for part in section['parts'])
        assert result.citations[0].doc_id == doc
        assert result.verification['legal']['semantic_conclusion_verified'] is False


def test_arabic_purpose_is_not_deadline():
    assert _rule_intent(_normalize('ما الوثائق المطلوبة من أجل ضياع جواز السفر؟')) == 'required_documents'
    assert _rule_intent(_normalize('ما أجل تجديد جواز السفر؟')) == 'processing_time'


def test_bridge_context_round_trip_preserves_public_subject_only():
    from telegram_bridge.contracts import AssistantRequest, AssistantResponse
    state = {'category': 'business_registration', 'rne_code': 'RNE C 010.1',
             'legal_subject': 'rne-arrete-2026-35', 'private_value': 'PRIVATE-VALUE'}
    reply = AssistantResponse(text='neutral', context=state)
    payload = AssistantRequest(text='neutral', context=reply.context).model_dump(exclude_none=True)
    assert payload['context']['rne_code'] == 'RNE C 010.1'
    assert payload['context']['legal_subject'] == 'rne-arrete-2026-35'
    assert 'PRIVATE-VALUE' not in json.dumps(payload)


@pytest.mark.parametrize('case', [c for c in SUITE['tests'] if c['kind'] == 'direct_factual' and c['document_id'] in {
    'rne-arrete-2026-35', 'rne-law-2018-52-ar', 'rne-decree-beneficial-owners',
    'rne-decree-name-reservation', 'rne-decree-2022-298-fees-fr', 'rne-decree-law-2022-18-fr'}], ids=lambda c:c['id'])
def test_original_legal_subjects_route_to_their_source(components, case):
    from agents.legal_evidence import identify_subject
    corpus, router, _ = components
    assert identify_subject(case['question']) == case['document_id']
    route = router.route(RouteRequest(text=case['question'], context=case['conversation_context'], language=case['language']))
    assert route.next_agent == 'answer'
    reply = legal_reply(ComposeRequest(query=case['question'], route=route, passages=[]), corpus)
    assert reply.found and reply.citations[0].doc_id == case['document_id']


@pytest.mark.parametrize('code', ['RNEC012', 'RNE C012', 'RNE C 012', 'rne c 012'])
def test_code_whitespace_does_not_change_identity(components, code):
    corpus, router, builder = components
    question = code + ' : frais ?'
    route = router.route(RouteRequest(text=question, context={}, language='fr'))
    result = builder.build(ComposeRequest(query=question, route=route, passages=[]))
    assert result.found and 'Code procédure: RNE C 012' in result.text


def test_unknown_code_does_not_fall_back_to_another_row(components):
    _, router, builder = components
    question = 'RNE C 999 : frais ?'
    route = router.route(RouteRequest(text=question, context={}, language='fr'))
    result = builder.build(ComposeRequest(query=question, route=route, passages=[]))
    assert not result.found and not result.sections


@pytest.mark.parametrize('question,language', [
    ('Ma CIN a été volée, quelles pièces fournir ?', 'fr'),
    ('My national ID is damaged, what documents are required?', 'en'),
    ('بطاقة التعريف تسرقت شنو الوثائق المطلوبة؟', 'derja'),
    ('Ma CIN est détériorée, quelles pièces fournir ?', 'fr'),
])
def test_loss_theft_damage_share_only_the_official_cin_replacement_scenario(components, question, language):
    corpus, router, builder = components
    route = router.route(RouteRequest(text=question, language=language, context={}))
    assert 'loss' in route.hints
    passage = RetrievedPassage(score=.7, chunk_id='neutral', text='neutral', citation=corpus.citation('interior-national-id-guide-fr'))
    result = builder.build(ComposeRequest(query=question, route=route, passages=[passage]))
    assert result.scenario == corpus.scenarios('interior-national-id-guide-fr')[3].title


@pytest.mark.parametrize('code', ['RNE I 001', 'RNE I 002', 'RNE C 010.1', 'RNE M 004.37'])
def test_exact_retrieval_uses_deployed_point_identity(components, code):
    from types import SimpleNamespace
    from agents.retriever import routed_retrieve
    corpus, router, _ = components
    payloads = [json.loads(line) for line in (REPO_ROOT / 'data/processed/chunks_structure.jsonl').read_text(encoding='utf-8').splitlines()]
    payloads = [p for p in payloads if p['doc_id'] == 'rne-formalities-procedure-table']
    class Client:
        def scroll(self, name, **kwargs):
            assert name.endswith('_structure') and kwargs['with_vectors'] is False
            return [SimpleNamespace(payload=p) for p in payloads], None
    route = router.route(RouteRequest(text=code + ' frais ?', language='fr', context={}))
    result = routed_retrieve(code, route, 8, get_settings(), None, SimpleNamespace(client=Client()))
    assert result.passages
    assert all('Code procédure: ' + code + '\n' in p.text for p in result.passages)


def test_bridge_subject_sessions_are_independent_and_expire():
    import time
    import httpx
    from telegram_bridge.bridge import TelegramBridge
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'ok': True, 'result': {}}))) as client:
        bridge = TelegramBridge('MOCK_ONLY', 'http://neutral.test', 1024, client=client, dialogue_enabled=True)
        bridge.session(1)['dialogue'] = {'category': 'business_registration', 'legal_subject': 'rne-arrete-2026-35'}
        bridge.session(2)['dialogue'] = {'category': 'business_registration', 'rne_code': 'RNE C 010.1'}
        assert 'rne_code' not in bridge.session(1)['dialogue']
        assert 'legal_subject' not in bridge.session(2)['dialogue']
        bridge.sessions[1]['seen'] = time.monotonic() - 1801
        assert 'dialogue' not in bridge.session(1)
        assert bridge.session(2)['dialogue']['rne_code'] == 'RNE C 010.1'
