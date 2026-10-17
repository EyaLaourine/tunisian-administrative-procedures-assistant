"""Offline visual-only checks; no API, Docker, workflow or inference execution."""
from copy import deepcopy
import ast
import hashlib
import json

import pytest

from scripts.n8n_presentation_polish import OUTPUT, polish, assert_visual_only, visual_projection
from scripts.n8n_workflow_review import ROOT, STICKY, read, semantic, validate

CASES=read(OUTPUT/'review_manifest.json')['workflows']


@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_real_fresh_backup_is_functionally_identical(case):
    path=ROOT/case['baseline_file']
    if not path.exists():pytest.skip('Private live backup intentionally excluded from Git')
    before=read(path);after=read(ROOT/case['candidate_file'])
    assert hashlib.sha256(path.read_bytes()).hexdigest()==case['baseline_sha256']
    assert_visual_only(before,after)
    assert after==polish(before)
    assert semantic(before)==semantic(after)
    assert before['connections']==after['connections'] and before['settings']==after['settings']
    assert before['versionId']==after['versionId'] and before.get('activeVersionId')==after.get('activeVersionId')
    assert [n for n in before['nodes'] if n['type']!=STICKY]==[n for n in after['nodes'] if n['type']!=STICKY]


@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_counts_content_schema_and_exact_artifact_hash(case):
    path=ROOT/case['candidate_file'];w=read(path);notes=[n for n in w['nodes'] if n['type']==STICKY]
    assert hashlib.sha256(path.read_bytes()).hexdigest()==case['candidate_sha256']
    assert validate(w)['valid']
    assert len(notes)==case['sticky_notes'] and len(w['nodes'])-len(notes)==case['executable_nodes']
    assert all(n['parameters']['content'].startswith('### ') for n in notes)
    assert all(2<=len(n['parameters']['content'].splitlines())<=3 for n in notes)
    assert all(len(n['parameters']['content'].split())<=40 for n in notes)
    text='\n'.join(n['parameters']['content'] for n in notes)
    assert not any(term in text.lower() for term in ['candidate','draft','live n8n remains unchanged','backend:8000','rollback','600000','16-node'])
    assert w['active']==(case['id']!='TnaaIngestIndex1')
    assert case['after_note_words']<case['before_note_words']


@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_note_frames_do_not_overlap(case):
    notes=[n for n in read(ROOT/case['candidate_file'])['nodes'] if n['type']==STICKY]
    for i,a in enumerate(notes):
        ax,ay=a['position'];aw,ah=a['parameters']['width'],a['parameters']['height']
        for b in notes[i+1:]:
            bx,by=b['position'];bw,bh=b['parameters']['width'],b['parameters']['height']
            assert ax+aw<=bx or bx+bw<=ax or ay+ah<=by or by+bh<=ay


@pytest.mark.parametrize('mutation',['executable_id','executable_name','executable_type','executable_position',
    'executable_parameters','credentials','connections','settings','active','version','note_id','note_type','delete_note','unknown_note_parameter'])
def test_forbidden_change_cannot_be_hidden_as_visual(mutation):
    before=read(ROOT/CASES[2]['candidate_file']);after=deepcopy(before)
    node=next(n for n in after['nodes'] if n['type'].endswith('.httpRequest'))
    note=next(n for n in after['nodes'] if n['type']==STICKY)
    if mutation=='executable_id':node['id']='neutral-changed'
    elif mutation=='executable_name':node['name']='Neutral changed'
    elif mutation=='executable_type':node['type']='n8n-nodes-base.set'
    elif mutation=='executable_position':node['position'][0]+=1
    elif mutation=='executable_parameters':node['parameters']['options']['timeout']=1
    elif mutation=='credentials':node['credentials']={'httpHeaderAuth':{'id':'neutral','name':'Neutral'}}
    elif mutation=='connections':after['connections']['File attached?']['main'].reverse()
    elif mutation=='settings':after['settings']['saveDataSuccessExecution']='all'
    elif mutation=='active':after['active']=False
    elif mutation=='version':after['versionId']='neutral-changed'
    elif mutation=='note_id':note['id']='neutral-changed'
    elif mutation=='note_type':note['type']='n8n-nodes-base.set'
    elif mutation=='delete_note':after['nodes'].remove(note)
    elif mutation=='unknown_note_parameter':note['parameters']['neutral_runtime_flag']=True
    with pytest.raises(ValueError):assert_visual_only(before,after)


def test_exact_annotation_changes_cover_every_existing_note():
    changes=json.loads((OUTPUT/'annotation_changes.json').read_text(encoding='utf-8'))
    assert len(changes)==20 and len({x['note_id'] for x in changes})==20
    assert all(x['before']['parameters']['color']==x['after']['parameters']['color'] for x in changes)
    assert all(x['before']['parameters']['width']==x['after']['parameters']['width'] for x in changes)
    w=read(ROOT/CASES[2]['candidate_file'])
    text='\n'.join(n['parameters']['content'] for n in w['nodes'] if n['type']==STICKY)
    assert 'Enhanced legal extraction is not deployed in the running backend.' in text
    assert 'Authentication and validation failures may also appear as 503.' in text
    assert 'Assistance does not certify legal completeness.' in text


def test_generation_has_no_network_or_apply_interface():
    source=(ROOT/'scripts/n8n_presentation_polish.py').read_text(encoding='utf-8')
    tree=ast.parse(source)
    imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    imports += [a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
    assert not {'httpx','requests','subprocess','socket'} & set(imports)
    assert "'--apply'" not in source and "'--publish'" not in source

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_checkpoint_candidates_are_sanitized_and_match_canonical(case):
    from scripts.n8n_controlled_sync import runtime_equal
    candidate=read(ROOT/case['candidate_file'])
    canonical=read(ROOT/'workflows'/__import__('pathlib').Path(case['candidate_file']).name)
    assert 'shared' not in candidate
    assert runtime_equal(candidate,canonical)
    assert candidate['nodes']==canonical['nodes']
    assert candidate['active']==canonical['active']
