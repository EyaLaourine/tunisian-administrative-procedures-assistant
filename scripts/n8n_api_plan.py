"""Offline public-API payload planning. No HTTP mutations or credential handling.

Future execution is intentionally absent: a new explicit approval and usable API
credential are required before any live PUT or POST.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess

from scripts.n8n_workflow_review import IDS, ROOT, executable, read, snapshot_changes, validate

APPROVED_COMMIT = '6021546a1bb16166b919d92aa75a655d1bbead60'
REQUIRED = ('name', 'nodes', 'connections', 'settings')
OPTIONAL = ('description', 'nodeGroups', 'staticData', 'pinData')


def writable_payload(workflow):
    """Explicit allowlist; never forward read-only/server metadata from exports."""
    body = {key: deepcopy(workflow[key]) for key in REQUIRED}
    body.update({key: deepcopy(workflow[key]) for key in OPTIONAL if key in workflow
                 and not (key in {'description', 'nodeGroups'} and workflow[key] is None)})
    # The installed DTO silently strips these settings. Do not approve lossy writes.
    if {'binaryMode', 'credentialResolverId'} & body['settings'].keys():
        raise ValueError('Settings transformed by installed API require separate review')
    if not validate(workflow)['valid']:
        raise ValueError('Invalid workflow graph')
    return body


def credential_refs(workflow):
    return {n['id']: deepcopy(n['credentials']) for n in executable(workflow) if n.get('credentials')}


def webhooks(workflow):
    return {n['id']: {k: deepcopy(n.get('parameters', {}).get(k))
                     for k in ('path', 'httpMethod', 'responseMode', 'authentication', 'options')}
            for n in executable(workflow) if n['type'].endswith('.webhook')}


def assert_preserved(before, candidate):
    if before['id'] != candidate['id'] or before['active'] != candidate['active']:
        raise ValueError('Workflow ID/publication intent changed')
    old_ids = {n['id'] for n in executable(before)}
    new_ids = {n['id'] for n in executable(candidate)}
    if not old_ids <= new_ids:
        raise ValueError('Existing executable node ID lost')
    if credential_refs(before) != credential_refs(candidate):
        raise ValueError('Credential references changed')
    if webhooks(before) != webhooks(candidate):
        raise ValueError('Webhook contract changed')
    if before.get('settings', {}) != candidate.get('settings', {}):
        raise ValueError('Settings change can republish existing version even with publishIfActive=false')


def verify_saved(expected, actual):
    """Check complete graph/layout and writable settings, not just a 200 response."""
    if expected['id'] != actual['id']:
        raise ValueError('Wrong server workflow ID')
    wanted = writable_payload(expected)
    observed = {key: actual.get(key) for key in wanted}
    if wanted != observed:
        raise ValueError('Saved draft differs from approved writable content')


def verify_published(candidate, actual):
    if actual.get('active') != candidate['active']:
        raise ValueError('Wrong active state')
    if not candidate['active']:
        if actual.get('activeVersionId'):
            raise ValueError('Inactive workflow has published version')
        return
    version = actual.get('activeVersion')
    if not version or actual.get('activeVersionId') != version.get('versionId'):
        raise ValueError('Missing/mismatched published snapshot')
    if actual.get('versionId') != actual.get('activeVersionId'):
        raise ValueError('Draft is not the published version')
    for field in ('nodes', 'connections'):
        if candidate[field] != version.get(field):
            raise ValueError('Published graph differs: '+field)


def build_plan(baseline, current, manifest):
    plans = []
    for entry in manifest['workflows']:
        wid = entry['workflow_id']
        old, now = read(baseline/(wid+'.json')), read(current/(wid+'.json'))
        if snapshot_changes(old, now):
            raise ValueError('Live drift: '+wid)
        path = ROOT/entry['candidate']
        approved = subprocess.run(['git', 'show', APPROVED_COMMIT+':'+entry['candidate']],
                                  cwd=ROOT, capture_output=True, check=True).stdout
        if path.read_bytes() != approved:
            raise ValueError('Candidate differs from approved commit')
        candidate = read(path)
        assert_preserved(now, candidate)
        update = writable_payload(candidate)
        # Preserve omitted optional state; never clear pin/static data by accident.
        for key in OPTIONAL:
            if key not in update and key in now:
                update[key] = deepcopy(now[key])
        plans.append({'workflow_id':wid, 'candidate_sha256':hashlib.sha256(approved).hexdigest(),
                      'precondition_version_id':now.get('versionId'),
                      'precondition_active_version_id':now.get('activeVersionId'),
                      'intended_active':now['active'],
                      'draft_update':{'method':'PUT', 'path':f'/api/v1/workflows/{wid}?publishIfActive=false', 'body':update},
                      'publish': {'method':'POST', 'path':f'/api/v1/workflows/{wid}/publish',
                                  'body_rule':{'versionId':'EXACT_VERSION_FROM_VERIFIED_PUT_RESPONSE'}} if now['active'] else None,
                      'rollback_update':{'method':'PUT', 'path':f'/api/v1/workflows/{wid}?publishIfActive=false',
                                         'body':writable_payload(now)},
                      'rollback_publish_version_rule':'verified rollback PUT versionId' if now['active'] else None})
    return {'status':'OFFLINE_PLAN_ONLY_NOT_EXECUTABLE', 'approved_commit':APPROVED_COMMIT,
            'server_side_compare_and_swap':False,
            'note':'Public PUT forceSave=true; an external exclusive edit window is required. GET checks cannot eliminate the race.',
            'workflows':plans}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--current', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('tmp/n8n-api-review/plan.json'))
    args = parser.parse_args()
    plan = build_plan(args.baseline, args.current, read(ROOT/'deploy/n8n_review/review_manifest.json'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'status':plan['status'],'workflows':len(plan['workflows']),'output':str(args.output)}))
