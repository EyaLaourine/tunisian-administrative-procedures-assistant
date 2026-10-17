"""Explicitly approved, one-workflow-at-a-time n8n synchronization with verified rollback.

Credentials arrive only in a temporary process environment from the Windows DPAPI
wrapper. Headers, raw errors and credential values are never written to reports.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import time

import httpx
from scripts.n8n_api_plan import APPROVED_COMMIT, assert_preserved, verify_saved, verify_published, writable_payload
from scripts.n8n_workflow_review import ROOT, IDS, STICKY, read, dump, validate, semantic, normalize_export_metadata


class SyncError(Exception):
    pass


def command(args):
    result=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=False)
    if result.returncode:raise SyncError('local_command_failed')
    return result.stdout


def core_equal(a,b):
    a,b=normalize_export_metadata(a),normalize_export_metadata(b)
    fields=('id','name','nodes','connections','settings','active','versionId','activeVersionId','pinData','staticData',
            'versionMetadata','sourceWorkflowId')
    return all(a.get(f)==b.get(f) for f in fields)


def runtime_equal(a,b):
    x,y=semantic(a),semantic(b)
    # The execution-only review projection omits visuals. The release gate must
    # additionally compare every node, including notes, positions and annotations.
    x['nodes']=sorted(deepcopy(a['nodes']),key=lambda n:n['id'])
    y['nodes']=sorted(deepcopy(b['nodes']),key=lambda n:n['id'])
    for source,projection in ((a,x),(b,y)):
        # Review-only server bookkeeping must not mask meaningful release metadata.
        for field in ('meta','description'):
            if source.get(field) is not None:projection[field]=deepcopy(source[field])
    for w in (x,y):
        for field in ('nodeGroups','pinData','staticData'):
            if w.get(field) in (None,{},[]):w.pop(field,None)
    return x==y


def publication_metadata():
    code="""const {DatabaseSync}=require('node:sqlite');const d=new DatabaseSync('/home/node/.n8n/database.sqlite',{readOnly:true});
const ids=['TnaaIngestIndex1','TnaaRetrieveApi1','TnaaAssistant01'];
console.log(JSON.stringify(ids.map(id=>({id,published:d.prepare('SELECT publishedVersionId FROM workflow_published_version WHERE workflowId=?').get(id)||null,
outbox:d.prepare('SELECT publishedVersionId,status FROM workflow_publication_outbox WHERE workflowId=? ORDER BY createdAt DESC LIMIT 1').get(id)||null,
triggers:d.prepare('SELECT nodeId,versionId,status,triggerKind FROM workflow_publication_trigger_status WHERE workflowId=?').all(id)}))));d.close();"""
    return json.loads(command(['docker','compose','exec','-T','n8n','node','-e',code]))


def candidate(wid):
    manifest=read(ROOT/'deploy/n8n_review/review_manifest.json')
    item=next(r for r in manifest['workflows'] if r['workflow_id']==wid)
    path=ROOT/item['candidate']
    approved=subprocess.run(['git','show',APPROVED_COMMIT+':'+item['candidate']],cwd=ROOT,capture_output=True,check=True).stdout
    if path.read_bytes()!=approved:raise SyncError('candidate_commit_mismatch')
    result=read(path)
    if not validate(result)['valid']:raise SyncError('candidate_graph_invalid')
    return result


def export_one(wid,path):
    remote='/tmp/tnaa-approved-sync-'+wid+'.json'
    command(['docker','compose','exec','-T','n8n','n8n','export:workflow','--id',wid,'--output='+remote])
    command(['docker','compose','cp','n8n:'+remote,str(path)])
    result=read(path)
    if not validate(result)['valid']:raise SyncError('export_graph_invalid')
    return result


class API:
    def __init__(self):
        key=os.environ.pop('N8N_REVIEW_API_KEY',None)
        if not key:raise SyncError('private_api_key_missing')
        logging.getLogger('httpx').setLevel(logging.CRITICAL)
        self.client=httpx.Client(base_url='http://127.0.0.1:5678/api/v1',headers={'X-N8N-API-KEY':key},
                                 timeout=30,follow_redirects=False,trust_env=False)
    def call(self,method,path,body=None):
        try:r=self.client.request(method,path,json=body) if body is not None else self.client.request(method,path)
        except httpx.HTTPError:raise SyncError('api_transport_failure_no_retry') from None
        if r.status_code!=200:raise SyncError('api_'+method+'_status_'+str(r.status_code))
        try:return r.json()
        except ValueError:raise SyncError('api_non_json_response') from None
    def get(self,wid):return self.call('GET','/workflows/'+wid)
    def put(self,wid,body):return self.call('PUT','/workflows/'+wid+'?publishIfActive=false',body)
    def publish(self,wid,version):return self.call('POST','/workflows/'+wid+'/publish',{'versionId':version})


def wait_publication(api,wid,expected):
    for _ in range(25):
        live=api.get(wid)
        verify_published(expected,live)
        meta=next(r for r in publication_metadata() if r['id']==wid)
        if not expected['active']:
            if meta['published'] is None:return live,meta
        elif meta['published'] and meta['published']['publishedVersionId']==live['activeVersionId']:
            if meta['outbox'] and meta['outbox']['publishedVersionId']==live['activeVersionId'] and meta['outbox']['status']=='completed':
                return live,meta
        time.sleep(1)
    raise SyncError('publication_runtime_convergence_timeout')


def main(args):
    if command(['git','branch','--show-current']).strip()!='codex/final-n8n-workflows':raise SyncError('wrong_branch')
    code_head=command(['git','rev-parse','HEAD']).strip()
    command(['git','merge-base','--is-ancestor',APPROVED_COMMIT,'HEAD'])
    api=API()
    release=args.release
    if args.action=='preflight':
        if not args.baseline:raise SyncError('explicit_reviewed_baseline_required')
        release.mkdir(parents=True,exist_ok=False)
        results=[]
        for wid in IDS:
            backup=read(args.cli_backup/(wid+'.json'))
            old=read(args.baseline/(wid+'.json'))
            if not core_equal(backup,old):raise SyncError('preflight_cli_drift_'+wid)
            now=api.get(wid)
            if not core_equal(backup,now):raise SyncError('preflight_api_cli_drift_'+wid)
            approved=candidate(wid);assert_preserved(now,approved)
            writable_payload(now)
            dump(release/('before-'+wid+'.json'),now)
            results.append({'id':wid,'status':'pending','backup_sha256':hashlib.sha256((args.cli_backup/(wid+'.json')).read_bytes()).hexdigest()})
        dump(release/'release.json',{'created_at':datetime.now(timezone.utc).isoformat(),'approved_commit':APPROVED_COMMIT,
             'release_code_commit':code_head,'reviewed_baseline':str(args.baseline),
             'cli_backup':str(args.cli_backup),'workflows':results,'publication_before':publication_metadata(),
             'modifying_requests':0,'concurrency':'no competing editor observed; immediate per-write drift guards; public API has no compare-and-swap'})
        print(json.dumps({'status':'preflight_passed','fresh_backups':str(args.cli_backup),'api_backups':str(release),'workflows':3}))
        return
    journal=read(release/'release.json')
    if journal.get('release_code_commit')!=code_head:raise SyncError('release_code_changed_since_preflight')
    wid=args.workflow
    index=IDS.index(wid)
    if any(r['status']!='verified' for r in journal['workflows'][:index]):raise SyncError('previous_workflow_not_verified')
    entry=journal['workflows'][index]
    if entry['status']!='pending':raise SyncError('workflow_already_attempted')
    before=read(release/('before-'+wid+'.json'))
    approved=candidate(wid)
    if not core_equal(before,api.get(wid)):raise SyncError('immediate_prewrite_drift_'+wid)
    # Refuse changing any other workflow while applying this one.
    for other in IDS:
        if other==wid:continue
        other_entry=journal['workflows'][IDS.index(other)]
        reference=read(release/(('after-' if other_entry['status']=='verified' else 'before-')+other+'.json'))
        if not core_equal(reference,api.get(other)):raise SyncError('other_workflow_drift_'+other)
    try:
        entry['status']='write_attempted';dump(release/'release.json',journal)
        journal['modifying_requests']+=1
        saved=api.put(wid,writable_payload(approved))
        now=api.get(wid);verify_saved(approved,now)
        if now['versionId']!=saved['versionId'] or now['active']!=before['active'] or now.get('activeVersionId')!=before.get('activeVersionId'):
            raise SyncError('draft_publication_or_version_changed')
        entry['draft_version_id']=now['versionId']
        dump(release/('draft-'+wid+'.json'),now)
        if approved['active']:
            if not core_equal(now,api.get(wid)):raise SyncError('prepublish_drift')
            journal['modifying_requests']+=1
            api.publish(wid,now['versionId'])
        after,meta=wait_publication(api,wid,approved)
        verify_saved(approved,after)
        exported=export_one(wid,release/('export-after-'+wid+'.json'))
        verify_saved(approved,exported);verify_published(approved,after)
        if not core_equal(after,exported):raise SyncError('api_export_state_or_version_difference')
        if not runtime_equal(approved,exported):raise SyncError('normalized_export_runtime_difference')
        dump(release/('after-'+wid+'.json'),after)
        entry.update({'status':'verified','published_version_id':after.get('activeVersionId'),
                      'runtime_publication':meta,'normalized_runtime_equal':True,'full_nodes_layout_equal':approved['nodes']==exported['nodes'],
                      'executable_nodes':len([n for n in after['nodes'] if n['type']!=STICKY]),
                      'sticky_notes':len([n for n in after['nodes'] if n['type']==STICKY])})
    except Exception as error:
        entry['failure']=str(error) if isinstance(error,SyncError) else type(error).__name__
        entry['status']='rollback_attempted'
        try:
            journal['modifying_requests']+=1
            restored=api.put(wid,writable_payload(before))
            current=api.get(wid);verify_saved(before,current)
            if current['versionId']!=restored['versionId']:raise SyncError('rollback_draft_version_mismatch')
            if before['active']:
                journal['modifying_requests']+=1;api.publish(wid,current['versionId'])
            restored,meta=wait_publication(api,wid,before);verify_saved(before,restored)
            exported=export_one(wid,release/('export-rollback-'+wid+'.json'));verify_saved(before,exported)
            if not core_equal(restored,exported):raise SyncError('rollback_api_export_state_or_version_difference')
            dump(release/('rollback-'+wid+'.json'),restored)
            entry.update({'status':'rolled_back_verified','rollback_version_id':restored['versionId'],'rollback_publication':meta})
        except Exception as rollback_error:
            entry['status']='rollback_failed';entry['rollback_error']=str(rollback_error) if isinstance(rollback_error,SyncError) else type(rollback_error).__name__
        dump(release/'release.json',journal)
        print(json.dumps({'workflow':wid,**entry}));return 1
    dump(release/'release.json',journal)
    print(json.dumps({'workflow':wid,**entry}));return 0


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['preflight','apply-one'])
    parser.add_argument('--release',type=Path,required=True)
    parser.add_argument('--cli-backup',type=Path)
    parser.add_argument('--baseline',type=Path,help='Explicitly reviewed export baseline, including any verified rollback version changes')
    parser.add_argument('--workflow',choices=IDS)
    args=parser.parse_args()
    try:raise SystemExit(main(args))
    except (SyncError,ValueError) as e:
        print(json.dumps({'status':'stopped','reason':str(e)}));raise SystemExit(1)
