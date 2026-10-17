"""Critical release/rollback checks with in-memory API state, never production."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

import scripts.n8n_controlled_sync as sync
from scripts.n8n_workflow_review import dump, read


def neutral(active=False):
    w={'id':'TnaaRetrieveApi1' if active else 'TnaaIngestIndex1','name':'Neutral fixture','active':active,
       'versionId':'original','activeVersionId':'original' if active else None,
       'nodes':[{'id':'neutral','name':'Neutral trigger','type':'n8n-nodes-base.manualTrigger',
                 'typeVersion':1,'position':[0,0],'parameters':{}}],
       'connections':{},'settings':{'executionOrder':'v1'}}
    if active:w['activeVersion']={'versionId':'original','nodes':deepcopy(w['nodes']),'connections':{}}
    return w


@pytest.mark.parametrize('active',[False,True])
@pytest.mark.parametrize('rollback_invalid',[False,True])
def test_failure_restores_only_target_and_verifies_rollback(tmp_path,monkeypatch,active,rollback_invalid):
    before=neutral(active);wid=before['id'];approved=deepcopy(before);approved['nodes'][0]['position']=[500,200]
    calls=[]
    class FakeAPI:
        def __init__(self):self.state=deepcopy(before);self.puts=0;self.publishes=0
        def get(self,_wid):assert _wid==wid;return deepcopy(self.state)
        def put(self,_wid,body):
            assert _wid==wid;calls.append('PUT');self.puts+=1
            self.state.update(deepcopy(body));self.state['versionId']='saved-'+str(self.puts)
            if not active and self.puts==1:self.state['name']='Neutral verification mismatch'
            if rollback_invalid and self.puts==2:self.state['settings']={'executionOrder':'neutral-invalid'}
            return deepcopy(self.state)
        def publish(self,_wid,version):
            assert _wid==wid;calls.append('POST');self.publishes+=1
            if self.publishes==1:raise sync.SyncError('fixture_publish_failure')
            self.state['activeVersionId']=version
            self.state['activeVersion']={'versionId':version,'nodes':deepcopy(self.state['nodes']),'connections':deepcopy(self.state['connections'])}
            return deepcopy(self.state)
    api=FakeAPI()
    dump(tmp_path/('before-'+wid+'.json'),before)
    dump(tmp_path/'release.json',{'release_code_commit':sync.APPROVED_COMMIT,'workflows':[{'id':wid,'status':'pending'}],'modifying_requests':0})
    monkeypatch.setattr(sync,'IDS',(wid,))
    monkeypatch.setattr(sync,'command',lambda a:'codex/final-n8n-workflows' if 'branch' in a else sync.APPROVED_COMMIT)
    monkeypatch.setattr(sync,'API',lambda:api)
    monkeypatch.setattr(sync,'candidate',lambda _wid:approved)
    monkeypatch.setattr(sync,'wait_publication',lambda a,i,e:(a.get(i),{'fixture':True}))
    monkeypatch.setattr(sync,'export_one',lambda i,p:api.get(i))
    result=sync.main(SimpleNamespace(action='apply-one',release=tmp_path,workflow=wid))
    journal=read(tmp_path/'release.json')
    assert result==1
    if rollback_invalid:
        assert journal['workflows'][0]['status']=='rollback_failed'
        assert 'rollback_version_id' not in journal['workflows'][0]
        assert calls==(['PUT','POST','PUT'] if active else ['PUT','PUT'])
        return
    assert journal['workflows'][0]['status']=='rolled_back_verified'
    assert api.state['nodes']==before['nodes'] and api.state['name']==before['name']
    assert api.state['active']==active
    assert calls==(['PUT','POST','PUT','POST'] if active else ['PUT','PUT'])


def test_runtime_normalization_only_ignores_empty_optional_state():
    w=neutral();other=deepcopy(w);other['nodeGroups']=[];other['pinData']=None
    assert sync.runtime_equal(w,other)
    other['nodes'][0]['parameters']={'neutral':True}
    assert not sync.runtime_equal(w,other)


def test_core_drift_detects_version_and_connections():
    w=neutral();other=deepcopy(w);other['versionId']='unexpected'
    assert not sync.core_equal(w,other)
