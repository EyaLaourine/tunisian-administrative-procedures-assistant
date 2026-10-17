"""Offline update/rollback construction: no HTTP or Docker mutations."""
from copy import deepcopy
import pytest

from scripts.n8n_api_plan import assert_preserved, verify_published, verify_saved, writable_payload
from scripts.n8n_workflow_review import ROOT, read


def fixture():
    return {'id':'neutral', 'name':'Neutral fixture', 'active':True, 'versionId':'draft',
            'activeVersionId':'original', 'nodes':[
                {'id':'neutral-webhook','name':'Neutral input','type':'n8n-nodes-base.webhook',
                 'typeVersion':2,'position':[0,0], 'parameters':{'path':'neutral','httpMethod':'POST','responseMode':'responseNode'},
                 'credentials':{'httpHeaderAuth':{'id':'neutral-credential','name':'Neutral reference'}}},
                {'id':'neutral-response','name':'Neutral response','type':'n8n-nodes-base.respondToWebhook',
                 'typeVersion':1,'position':[300,0],'parameters':{}}],
            'connections':{'Neutral input':{'main':[[{'node':'Neutral response','type':'main','index':0}]]}},
            'settings':{'executionOrder':'v1'}, 'pinData':{},'staticData':None,
            'shared':[], 'createdAt':'neutral-server-metadata'}


def test_payload_allowlist_preserves_state_without_server_metadata():
    w=fixture();body=writable_payload(w)
    assert set(body)=={'name','nodes','connections','settings','pinData','staticData'}
    assert body['nodes'][0]['credentials']==w['nodes'][0]['credentials']
    assert body['nodes'] is not w['nodes']
    assert writable_payload({**w,'description':None})==body


@pytest.mark.parametrize('field',['id','active','node_id','credentials','path','responseMode','httpMethod','settings'])
def test_preconditions_reject_lost_identity_or_contract(field):
    a=fixture();b=deepcopy(a)
    if field in {'id','active'}:b[field]='changed'
    elif field=='node_id':b['nodes'][0]['id']='changed'
    elif field=='credentials':b['nodes'][0]['credentials']={}
    elif field=='settings':b['settings']['executionTimeout']=123
    else:b['nodes'][0]['parameters'][field]='changed'
    with pytest.raises(ValueError):assert_preserved(a,b)


def test_saved_verification_checks_full_layout_and_body():
    w=fixture();verify_saved(w,deepcopy(w))
    b=deepcopy(w);b['nodes'][0]['position'][0]+=20
    with pytest.raises(ValueError):verify_saved(w,b)


def test_publication_requires_exact_published_snapshot():
    w=fixture();actual=deepcopy(w)
    with pytest.raises(ValueError):verify_published(w,actual)
    actual['versionId']=actual['activeVersionId']='new-version'
    actual['activeVersion']={'versionId':'new-version','nodes':deepcopy(w['nodes']),'connections':deepcopy(w['connections'])}
    verify_published(w,actual)
    actual['activeVersion']['nodes'][0]['id']='unexpected'
    with pytest.raises(ValueError):verify_published(w,actual)


def test_inactive_must_not_gain_publication():
    w=fixture();w['active']=False;w['activeVersionId']=None
    verify_published(w,w)
    with pytest.raises(ValueError):verify_published(w,{**w,'activeVersionId':'unexpected'})


@pytest.mark.parametrize('field',['binaryMode','credentialResolverId'])
def test_lossy_setting_transform_requires_review(field):
    w=fixture();w['settings'][field]='neutral'
    with pytest.raises(ValueError):writable_payload(w)


@pytest.mark.parametrize('filename',['01_ingest_and_index.json','02_retrieve_api.json','03_assistant_multi_agent.json'])
def test_approved_candidate_payload_is_lossless(filename):
    w=read(ROOT/'deploy/n8n_review/candidates'/filename)
    body=writable_payload(w)
    assert body['nodes']==w['nodes'] and body['connections']==w['connections']
    assert 'active' not in body and 'id' not in body and 'versionId' not in body
