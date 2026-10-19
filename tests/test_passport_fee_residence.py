"""Passport fee conflicts must compare the same residence and applicant categories.

Official facts come from the existing indexed FR/AR snapshot; no live rate validity is claimed.
"""
import pytest

from agents.checklist_builder import AMOUNT, ChecklistBuilder
from agents.corpus import Corpus
from agents.intent_router import IntentRouter
from agents.i18n import t
from agents.prompts import PromptLibrary
from agents.schemas import ComposeRequest, DialogueContext, RouteRequest
from backend.settings import REPO_ROOT, get_settings
from rag.retrieval import RetrievedPassage

FR='interior-passport-guide-fr'
AR='interior-passport-guide-ar'
QUESTION='Quels sont les frais de renouvellement du passeport tunisien ?'
OBSERVED_REPLY='» lêetranger'


@pytest.fixture(scope='module')
def services():
    settings=get_settings()
    corpus=Corpus(settings.raw_dir,settings.processed_dir)
    assert corpus.scenarios(FR) and corpus.scenarios(AR), 'Reconstruct the tracked corpus before testing'
    prompts=PromptLibrary(REPO_ROOT/'prompts')
    return corpus,IntentRouter(None,prompts,False),ChecklistBuilder(corpus,None,prompts)


def fee_lines(scenario):
    return [item for section in scenario.sections if section.kind=='documents'
            for item in section.items if AMOUNT.search(item)]


@pytest.mark.parametrize('language',['fr','ar'])
@pytest.mark.parametrize('retrieved_doc',[FR,AR])
@pytest.mark.parametrize('residence,reply,index,conflict',[
    ('abroad',OBSERVED_REPLY,1,False),
    ('tunisia','Je réside en Tunisie',0,True),
])
def test_exact_fee_clarification_keeps_residence_specific_warning(services,language,retrieved_doc,residence,reply,index,conflict):
    corpus,router,builder=services
    first=router.route(RouteRequest(text=QUESTION,language=language,context=DialogueContext()))
    assert first.next_agent=='reply'
    if language=='fr':
        assert first.reply=='Tu résides en Tunisie ou à l’étranger ?'
    assert first.context.pending_intent=='fees' and first.context.residence is None
    final=router.route(RouteRequest(text=reply,language=language,context=first.context))
    assert final.next_agent=='checklist' and final.intent=='fees'
    assert final.context.residence==residence
    assert ('abroad' in final.hints)==(residence=='abroad')
    assert 'renewal' in final.hints and 'loss' not in final.hints
    scenario=corpus.scenarios(retrieved_doc)[index]
    passage=RetrievedPassage(score=.9,text='\n'.join(fee_lines(scenario)),chunk_id='residence-fee-regression',
                             citation=corpus.citation(retrieved_doc,scenario.path))
    result=builder.build(ComposeRequest(query=reply,route=final,passages=[passage]))
    assert result.found and [section.kind for section in result.sections]==['fees']
    assert bool(result.fee_discrepancy)==conflict
    assert bool(result.warnings)==conflict
    assert {c.doc_id for c in result.citations}=={FR,AR}
    if conflict:
        assert '20/60' in result.text and '25/80' in result.text
    else:
        assert '20/60' not in result.text and '25/80' not in result.text
        assert t('passport_abroad_fee_categories',language,reduced='25',standard='80') in result.text
        assert {match.group(1) for section in result.sections for item in section.items
                for match in AMOUNT.finditer(item)}=={'25','80'}


def test_abroad_sources_agree_within_the_same_applicant_categories(services):
    corpus,_,_=services
    fr,ar=(fee_lines(corpus.scenarios(doc)[1]) for doc in [FR,AR])
    assert len(fr)==len(ar)==2
    # Compare the student/young-child group separately from all other applicants.
    assert 'élèves' in fr[0] and 'étudiants' in fr[0] and '6' in fr[0]
    assert 'للتلاميذ' in ar[0] and 'الطلبة' in ar[0] and '6' in ar[0]
    assert 'autres' in fr[1] and 'للبقية' in ar[1]
    for left,right in zip(fr,ar):
        assert [m.group(1) for m in AMOUNT.finditer(left)]==[m.group(1) for m in AMOUNT.finditer(right)]
    assert '25' in fr[0] and '80' in fr[1]
    # Arabic specifies the equivalent in foreign currency: retain that source nuance.
    assert all('بالعملة الأجنبية' in line for line in ar)
