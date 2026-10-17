"""Offline workflow review. No n8n execution, service failure or corpus write."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from scripts.n8n_workflow_review import (
    COLORS, IDS, OUTPUT, ROOT, STICKY, design, difference, discover, executable,
    read, routes_from_source, security_plan, semantic, sha, snapshot_changes, validate,
)

MANIFEST = read(OUTPUT / 'review_manifest.json')
CASES = MANIFEST['workflows']


@pytest.mark.parametrize('field', ['active', 'versionId', 'activeVersionId', 'nodes', 'settings'])
def test_live_guard_rejects_publication_layout_and_runtime_drift(field):
    before = read(ROOT / CASES[2]['candidate'])
    after = deepcopy(before)
    if field == 'nodes':
        after['nodes'][0]['position'][0] += 1
    elif field == 'settings':
        after['settings']['executionOrder'] = 'changed'
    else:
        after[field] = 'changed'
    assert field in snapshot_changes(before, after)
    assert snapshot_changes(before, deepcopy(before)) == []


@pytest.mark.parametrize('case', CASES, ids=lambda r:r['workflow_id'])
def test_candidates_preserve_selected_executable_baseline(case):
    candidate = read(ROOT / case['candidate'])
    base = read(ROOT / case['canonical'])
    base['active'] = candidate['active']
    assert semantic(candidate) == semantic(base)
    assert validate(candidate,base)['valid']
    assert {n['id'] for n in executable(candidate)} == {n['id'] for n in executable(base)}
    assert candidate['connections'] == base['connections']


@pytest.mark.parametrize('case', CASES, ids=lambda r:r['workflow_id'])
def test_layout_is_deterministic_and_has_only_supported_annotations(case):
    candidate = read(ROOT / case['candidate'])
    base = read(ROOT / case['canonical'])
    assert candidate == design(base,candidate['active'])
    notes = [n for n in candidate['nodes'] if n['type']==STICKY]
    assert len(notes) == case['validation']['sticky_notes']
    assert all(n['typeVersion']==1 and n['parameters']['color'] in COLORS.values() for n in notes)
    assert all('Guide:' in n['name'] for n in notes)
    assert all(n['name'] not in candidate['connections'] for n in notes)


@pytest.mark.parametrize('case', CASES, ids=lambda r:r['workflow_id'])
def test_no_overlapping_executable_node_boxes_or_note_frames(case):
    workflow = read(ROOT / case['candidate'])
    nodes = executable(workflow)
    for i,a in enumerate(nodes):
        ax,ay=a['position']
        for b in nodes[i+1:]:
            bx,by=b['position']
            assert abs(ax-bx)>=180 or abs(ay-by)>=150
    notes=[n for n in workflow['nodes'] if n['type']==STICKY]
    for i,a in enumerate(notes):
        ax,ay=a['position'];aw,ah=a['parameters']['width'],a['parameters']['height']
        for b in notes[i+1:]:
            bx,by=b['position'];bw,bh=b['parameters']['width'],b['parameters']['height']
            assert ax+aw<=bx or bx+bw<=ax or ay+ah<=by or by+bh<=ay


@pytest.mark.parametrize('case', CASES, ids=lambda r:r['workflow_id'])
def test_webhooks_and_http_parameters_are_identical(case):
    candidate = read(ROOT / case['candidate'])
    base = read(ROOT / case['canonical'])
    original={n['id']:n for n in executable(base)}
    for n in executable(candidate):
        assert n['parameters']==original[n['id']]['parameters']
        assert n.get('webhookId')==original[n['id']].get('webhookId')
        assert n.get('credentials')==original[n['id']].get('credentials')
    assert candidate['settings']==base['settings']


def test_activation_and_functional_drift_are_explicit():
    rows={r['workflow_id']:r for r in CASES}
    assert read(ROOT/rows[IDS[0]]['candidate'])['active'] is False
    assert read(ROOT/rows[IDS[1]]['candidate'])['active'] is True
    assert read(ROOT/rows[IDS[2]]['candidate'])['active'] is True
    delta=rows[IDS[2]]['live_vs_candidate']
    assert delta['added_executable_nodes']==['Respond: agent error']
    assert not delta['semantic_equal'] and not delta['connections_equal']
    assert all(x['fields']==['onError','position'] or set(x['fields'])<= {'onError','position'} for x in delta['changed_node_fields'])


def test_unknown_runtime_fields_and_branch_order_remain_significant():
    w=read(ROOT/CASES[2]['candidate'])
    view=deepcopy(w);view['nodes'][0]['position']=[99,99]
    assert semantic(w)==semantic(view)
    changed=deepcopy(w);changed['connections']['File attached?']['main'].reverse()
    assert semantic(w)!=semantic(changed)
    changed=deepcopy(w);changed['unrecognised_runtime_option']=True
    assert semantic(w)!=semantic(changed)
    changed=deepcopy(w);changed['settings']['saveDataSuccessExecution']='all'
    assert semantic(w)!=semantic(changed)


@pytest.mark.parametrize('mutation,expected', [
    ('duplicate_id','duplicate_node_id'), ('duplicate_name','duplicate_node_name'),
    ('unknown_target','invalid_connection_target:'), ('wrong_endpoint','unexpected_backend:'),
    ('missing_route','missing_backend_route:'), ('literal_key','literal_secret_header:'),
    ('bad_sticky','sticky_compatibility:'), ('missing_expression','invalid_expression_reference:'),
])
def test_validation_rejects_unsafe_or_broken_candidates(mutation,expected):
    w=read(ROOT/CASES[1]['candidate'])
    if mutation=='duplicate_id': w['nodes'][1]['id']=w['nodes'][0]['id']
    elif mutation=='duplicate_name': w['nodes'][1]['name']=w['nodes'][0]['name']
    elif mutation=='unknown_target': w['connections'][w['nodes'][0]['name']]['main'][0][0]['node']='neutral missing'
    elif mutation=='wrong_endpoint': w['nodes'][1]['parameters']['url']='http://neutral.invalid/retrieve'
    elif mutation=='missing_route': w['nodes'][1]['parameters']['url']='http://backend:8000/neutral-missing'
    elif mutation=='literal_key': w['nodes'][1]['parameters']['headerParameters']={'parameters':[{'name':'X-Agent-Key','value':'neutral-test-fixture'}]}
    elif mutation=='bad_sticky': w['nodes'][-1]['parameters']['color']=99
    elif mutation=='missing_expression': w['nodes'][1]['parameters']['jsonBody']="={{ $('neutral missing').item.json }}"
    assert any(e.startswith(expected) for e in validate(w)['errors'])


def test_all_nine_http_calls_have_precise_header_plans_without_values():
    workflows=[read(ROOT/r['candidate']) for r in CASES]
    plan=security_plan(workflows)
    assert len(plan['backend_calls'])==9
    admin=[r for r in plan['backend_calls'] if r['header_name']=='X-Admin-Key']
    agent=[r for r in plan['backend_calls'] if r['header_name']=='X-Agent-Key']
    assert {r['endpoint'] for r in admin}=={'/ingestion/run','/index/run'}
    assert len(agent)==7 and {r['endpoint'] for r in agent}=={'/retrieve','/agents/route','/agents/retrieve','/agents/checklist','/agents/answer','/agents/form-check','/agents/dossier-check'}
    assert all(r['credential_id'] is None and r['credential_type']=='httpHeaderAuth' for r in plan['backend_calls'])
    assert plan['webhook_auth']['header_name']=='X-Assistant-Key'
    assert '/ingestion/run' in {r[1] for r in routes_from_source()}


def test_claude_error_branch_is_complete_and_not_success():
    w=read(ROOT/CASES[2]['candidate'])
    http=[n for n in w['nodes'] if n['type'].endswith('httpRequest')]
    assert len(http)==6
    for n in http:
        assert n['onError']=='continueErrorOutput'
        assert w['connections'][n['name']]['main'][1]==[{'node':'Respond: agent error','type':'main','index':0}]
        assert not n.get('retryOnFail',False)
    error=next(n for n in w['nodes'] if n['name']=='Respond: agent error')
    assert error['parameters']['options']['responseCode']==503
    assert '$json.error' not in error['parameters']['responseBody']
    assert w['settings']['saveDataSuccessExecution']=='none'
    assert w['settings']['saveDataErrorExecution']=='none'
    assert w['settings']['saveManualExecutions'] is False


@pytest.mark.parametrize('language',['en','fr','ar','derja',None])
def test_error_response_expression_with_neutral_inputs(language):
    node=shutil.which('node')
    if not node:pytest.skip('Node.js unavailable; expression sandbox not executed')
    w=read(ROOT/CASES[2]['candidate'])
    expression=next(n for n in w['nodes'] if n['name']=='Respond: agent error')['parameters']['responseBody'][3:-2].strip()
    code="""const fs=require('fs'),vm=require('vm');const a=JSON.parse(fs.readFileSync(0,'utf8'));
const ctx={JSON,$:()=>({item:{json:{body:{language:a.language}}}}),$prevNode:{name:'neutral'}};
const text=vm.runInNewContext('('+a.expression+')',ctx,{timeout:100});console.log(text);"""
    process=subprocess.run([node,'-e',code],input=json.dumps({'expression':expression,'language':language}),capture_output=True,text=True,encoding='utf-8',check=True)
    result=json.loads(process.stdout)
    assert result['text'] and result['agent']=='orchestrator' and result['error']=='agent_unavailable'
    assert result['failed_agent']=='neutral'
    assert 'detail' not in result


def test_candidate_notes_do_not_claim_deployed_legal_service_or_autonomy():
    w=read(ROOT/CASES[2]['candidate'])
    text='\n'.join(n['parameters']['content'] for n in w['nodes'] if n['type']==STICKY)
    assert 'NOT DEPLOYED' in text and 'Production image has no legal_evidence module yet' in text
    assert 'none plans or negotiates autonomously' in text
    assert 'not currently deployed' not in json.dumps([n['parameters'] for n in executable(w)])
