"""Offline reproduction of the captured CLI export failure and strict regressions."""
from copy import deepcopy
from pathlib import Path
import hashlib
from types import SimpleNamespace

import pytest

from scripts import n8n_controlled_sync as sync
from scripts.n8n_api_plan import verify_published, verify_saved
from scripts.n8n_workflow_review import ROOT, SERVER_METADATA, STICKY, dump, normalize_export_metadata, read, semantic

CAPTURE = ROOT/'tmp/n8n-live-release/20261017T225152Z'
CANDIDATE = ROOT/'deploy/n8n_review/candidates/01_ingest_and_index.json'


def old_runtime_equal(a,b):
    """Frozen pre-fix projection from the failed comparison, including layout omission."""
    def old_semantic(w):
        result={k:deepcopy(w[k]) for k in ('id','name','active','connections','settings','pinData','staticData') if k in w}
        result['nodes']=sorted([{k:deepcopy(v) for k,v in n.items() if k not in {'position','notes','notesInFlow'}}
                                for n in w['nodes'] if n['type']!=STICKY],key=lambda n:n['id'])
        result.update({k:deepcopy(v) for k,v in w.items() if k not in SERVER_METADATA})
        for field in ('nodeGroups','pinData','staticData'):
            if result.get(field) in (None,{},[]):result.pop(field,None)
        return result
    return old_semantic(a)==old_semantic(b)


def test_exact_captured_candidate_draft_export_and_rollback():
    if not (CAPTURE/'export-after-TnaaIngestIndex1.json').exists():
        pytest.skip('Private captured exports intentionally excluded from Git; portable projection tested separately')
    candidate=read(CANDIDATE)
    draft=read(CAPTURE/'draft-TnaaIngestIndex1.json')
    exported=read(CAPTURE/'export-after-TnaaIngestIndex1.json')
    assert not old_runtime_equal(candidate,exported)
    assert not old_runtime_equal(draft,exported)
    assert sync.runtime_equal(candidate,exported)
    assert sync.runtime_equal(draft,exported)
    verify_saved(candidate,exported)
    assert sync.core_equal(draft,exported)
    assert sync.runtime_equal(read(CAPTURE/'before-TnaaIngestIndex1.json'),read(CAPTURE/'export-rollback-TnaaIngestIndex1.json'))
    evidence=read(ROOT/'deploy/n8n_review/normalization_evidence.json')
    assert hashlib.sha256((CAPTURE/'export-after-TnaaIngestIndex1.json').read_bytes()).hexdigest()==evidence['captured_export_sha256']


def test_portable_projection_uses_actual_captured_metadata():
    evidence=read(ROOT/'deploy/n8n_review/normalization_evidence.json')
    w=read(CANDIDATE);exported=deepcopy(w);exported.update(evidence['captured_metadata_projection'])
    assert not old_runtime_equal(w,exported)
    assert sync.runtime_equal(w,exported)


@pytest.mark.parametrize('extra',[{}, {'sourceWorkflowId':None},{'versionMetadata':None},
    {'versionMetadata':{'name':None,'description':None}},
    {'sourceWorkflowId':None,'versionMetadata':{'name':None,'description':None}}])
def test_only_observed_empty_root_metadata_is_equivalent(extra):
    w=read(CANDIDATE);other=deepcopy(w);other.update(extra)
    assert sync.runtime_equal(w,other)
    assert semantic(w)==semantic(other)
    assert normalize_export_metadata(other)==w
    assert other=={**w,**extra}, 'Normalization mutated its input'


@pytest.mark.parametrize('extra',[
    {'versionMetadata':{'name':'Neutral version','description':None}},
    {'versionMetadata':{'name':None,'description':'Neutral description'}},
    {'versionMetadata':{'name':'','description':None}},
    {'versionMetadata':{'name':None}}, {'versionMetadata':{}},
    {'versionMetadata':{'name':None,'description':None,'unknown':None}},
    {'versionMetadata':False}, {'sourceWorkflowId':'neutral-source'},
    {'unknownExportField':None}, {'unknownExportField':{'neutral':True}},
    {'meta':{'unknown':None}}, {'description':'Neutral workflow description'},
])
def test_meaningful_and_unknown_metadata_remains_significant(extra):
    w=read(CANDIDATE);other=deepcopy(w);other.update(extra)
    assert not sync.runtime_equal(w,other)
    assert sync.runtime_equal(other,deepcopy(other))


@pytest.mark.parametrize('change',['workflow_id','node_id','name','type','parameters','credentials','connections',
                                 'settings','position','missing_note','note_text','active','nested_metadata'])
def test_meaningful_changes_are_not_hidden(change):
    w=read(CANDIDATE);other=deepcopy(w)
    other.update({'versionMetadata':{'name':None,'description':None},'sourceWorkflowId':None})
    node=next(n for n in other['nodes'] if n['type'].endswith('httpRequest'))
    if change=='workflow_id':other['id']='neutral-changed'
    elif change=='node_id':node['id']='neutral-changed'
    elif change=='name':node['name']='Neutral changed'
    elif change=='type':node['type']='n8n-nodes-base.set'
    elif change=='parameters':node['parameters']['options']['timeout']=1
    elif change=='credentials':node['credentials']={'httpHeaderAuth':{'id':'neutral','name':'Neutral fixture'}}
    elif change=='connections':other['connections']['Manual trigger']['main'][0]=[]
    elif change=='settings':other['settings']['executionOrder']='neutral-changed'
    elif change=='position':node['position'][0]+=1
    elif change=='missing_note':other['nodes']=[n for n in other['nodes'] if n['type']!=STICKY]
    elif change=='note_text':next(n for n in other['nodes'] if n['type']==STICKY)['parameters']['content']='Neutral changed'
    elif change=='active':other['active']=True
    elif change=='nested_metadata':node['parameters']['versionMetadata']={'name':None,'description':None}
    assert not sync.runtime_equal(w,other)


def test_real_webhook_path_change_fails():
    w=read(ROOT/'deploy/n8n_review/candidates/02_retrieve_api.json');other=deepcopy(w)
    next(n for n in other['nodes'] if n['type'].endswith('.webhook'))['parameters']['path']='neutral-changed'
    assert not sync.runtime_equal(w,other)


@pytest.mark.parametrize('field',['versionId','activeVersionId'])
def test_version_drift_is_checked_separately_from_content(field):
    w=read(ROOT/'deploy/n8n_review/candidates/02_retrieve_api.json')
    w.update({'versionId':'neutral-version','activeVersionId':'neutral-version',
              'activeVersion':{'versionId':'neutral-version','nodes':deepcopy(w['nodes']),'connections':deepcopy(w['connections'])}})
    other=deepcopy(w);other[field]='neutral-changed'
    assert not sync.core_equal(w,other)
    with pytest.raises(ValueError):verify_published(w,other)


def test_captured_release_path_succeeds_without_rollback_or_publication(tmp_path,monkeypatch):
    if not (CAPTURE/'export-after-TnaaIngestIndex1.json').exists():
        pytest.skip('Private captured snapshots are not committed')
    before=read(CAPTURE/'before-TnaaIngestIndex1.json');approved=read(CANDIDATE)
    saved=read(CAPTURE/'draft-TnaaIngestIndex1.json');exported=read(CAPTURE/'export-after-TnaaIngestIndex1.json')
    wid=before['id'];calls=[]
    class CapturedAPI:
        def __init__(self):self.state=before
        def get(self,i):assert i==wid;return deepcopy(self.state)
        def put(self,i,body):
            assert i==wid and body==sync.writable_payload(approved)
            calls.append('PUT');self.state=saved;return deepcopy(saved)
        def publish(self,*args):raise AssertionError('Inactive workflow must never be published')
    api=CapturedAPI()
    dump(tmp_path/('before-'+wid+'.json'),before)
    dump(tmp_path/'release.json',{'release_code_commit':sync.APPROVED_COMMIT,'workflows':[{'id':wid,'status':'pending'}],'modifying_requests':0})
    monkeypatch.setattr(sync,'IDS',(wid,));monkeypatch.setattr(sync,'API',lambda:api)
    monkeypatch.setattr(sync,'command',lambda args:'codex/final-n8n-workflows' if 'branch' in args else sync.APPROVED_COMMIT)
    monkeypatch.setattr(sync,'candidate',lambda i:approved)
    monkeypatch.setattr(sync,'publication_metadata',lambda:[{'id':wid,'published':None,'outbox':None,'triggers':[]}])
    monkeypatch.setattr(sync,'export_one',lambda i,p:deepcopy(exported))
    assert sync.main(SimpleNamespace(action='apply-one',release=tmp_path,workflow=wid))==0
    entry=read(tmp_path/'release.json')['workflows'][0]
    assert entry['status']=='verified' and entry['normalized_runtime_equal'] and entry['full_nodes_layout_equal']
    assert calls==['PUT'] and entry['published_version_id'] is None


@pytest.mark.parametrize('outbox_state',['pending','wrong_version'])
def test_publication_wait_rejects_incomplete_runtime_state(monkeypatch,outbox_state):
    w=read(ROOT/'deploy/n8n_review/candidates/02_retrieve_api.json')
    w.update({'versionId':'neutral','activeVersionId':'neutral','activeVersion':{'versionId':'neutral','nodes':deepcopy(w['nodes']),'connections':deepcopy(w['connections'])}})
    calls=[]
    api=SimpleNamespace(get=lambda i:(calls.append('GET') or deepcopy(w)))
    meta={'id':w['id'],'published':{'publishedVersionId':'neutral'},'outbox':{'publishedVersionId':'wrong' if outbox_state=='wrong_version' else 'neutral','status':'completed' if outbox_state=='wrong_version' else 'pending'}}
    monkeypatch.setattr(sync,'publication_metadata',lambda:[meta]);monkeypatch.setattr(sync.time,'sleep',lambda _:None)
    with pytest.raises(sync.SyncError,match='convergence_timeout'):sync.wait_publication(api,w['id'],w)
    assert calls==['GET']*25


def test_http_error_is_not_retried_or_treated_as_success():
    import httpx
    requests=[]
    def handler(req):requests.append(req.method);return httpx.Response(403,json={'neutral':'fixture'})
    api=sync.API.__new__(sync.API)
    api.client=httpx.Client(base_url='http://neutral.invalid/api/v1',transport=httpx.MockTransport(handler))
    with pytest.raises(sync.SyncError,match='api_PUT_status_403'):api.put('neutral',{})
    assert requests==['PUT']
    api.client.close()
