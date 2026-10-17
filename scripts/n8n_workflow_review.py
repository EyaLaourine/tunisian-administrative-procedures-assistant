"""Read-only n8n export, semantic drift review and reproducible visual candidates.

There is deliberately no import, publish, activation or credential-write operation.
Backups stay in ignored tmp/. Candidate definitions never contain secret values.
"""
from __future__ import annotations

import argparse
import ast
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'deploy/n8n_review'
IDS = ('TnaaIngestIndex1', 'TnaaRetrieveApi1', 'TnaaAssistant01')
EXPECTED_HEAD = 'a5aef273e7d7d4d888efbb92645f15c219bbf48a'
STICKY = 'n8n-nodes-base.stickyNote'
COLORS = {'input': 5, 'routing': 6, 'knowledge': 4, 'document': 2, 'answer': 5, 'security': 3, 'infrastructure': 7}
SERVER_METADATA = {'createdAt', 'updatedAt', 'versionId', 'activeVersionId', 'versionCounter',
                   'triggerCount', 'shared', 'tags', 'meta', 'id', 'name', 'active', 'nodes',
                   'connections', 'settings', 'pinData', 'staticData', 'isArchived', 'activeVersion',
                   'homeProject', 'usedCredentials', 'project', 'parentFolder', 'description'}
SUPPORTED = {'manualTrigger', 'scheduleTrigger', 'httpRequest', 'set', 'webhook', 'if', 'respondToWebhook', 'stickyNote'}


def read(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(data, list):
        if len(data) != 1:
            raise ValueError('Expected exactly one workflow per file')
        return data[0]
    return data


def dump(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def sha(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def executable(workflow):
    return [n for n in workflow['nodes'] if n['type'] != STICKY]


def normalize_export_metadata(workflow):
    """Normalize only observed empty root export/history metadata in n8n 2.41.3.

    Version names/descriptions and non-null source lineage remain significant.
    Unknown keys, incomplete objects and nested lookalikes are never discarded.
    """
    result = deepcopy(workflow)
    if 'sourceWorkflowId' in result and result['sourceWorkflowId'] is None:
        del result['sourceWorkflowId']
    if 'versionMetadata' in result and (
        result['versionMetadata'] is None
        or result['versionMetadata'] == {'name': None, 'description': None}
    ):
        del result['versionMetadata']
    return result


def semantic(workflow):
    """Exclude view/server bookkeeping, retain runtime values and ordered branch outputs."""
    workflow = normalize_export_metadata(workflow)
    nodes = []
    for original in executable(workflow):
        node = {k:deepcopy(v) for k,v in original.items() if k not in {'position', 'notes', 'notesInFlow'}}
        nodes.append(node)
    result = {k:deepcopy(workflow[k]) for k in ('id', 'name', 'active', 'connections', 'settings', 'pinData', 'staticData') if k in workflow}
    result['nodes'] = sorted(nodes, key=lambda n:n['id'])
    # Unknown top-level fields are not silently discarded in comparisons.
    result.update({k:deepcopy(v) for k,v in workflow.items() if k not in SERVER_METADATA})
    return result


def difference(before, after):
    a = {n['id']:n for n in executable(before)}
    b = {n['id']:n for n in executable(after)}
    changed = []
    for key in sorted(a.keys() & b.keys()):
        fields = [f for f in sorted(set(a[key]) | set(b[key])) if a[key].get(f) != b[key].get(f)]
        if fields:
            changed.append({'node':a[key]['name'], 'fields':fields})
    return {'added_executable_nodes':[b[k]['name'] for k in sorted(b.keys()-a.keys())],
            'removed_executable_nodes':[a[k]['name'] for k in sorted(a.keys()-b.keys())],
            'changed_node_fields':changed, 'connections_equal':before['connections'] == after['connections'],
            'settings_equal':before.get('settings', {}) == after.get('settings', {}),
            'active_before':before.get('active'), 'active_after':after.get('active'),
            'semantic_equal':semantic(before) == semantic(after),
            'semantic_sha256_before':sha(semantic(before)), 'semantic_sha256_after':sha(semantic(after))}


def discover():
    found = {}
    for path in (ROOT / 'workflows').glob('*.json'):
        workflow = read(path)
        if workflow.get('id') in IDS:
            if workflow['id'] in found:
                raise ValueError('Ambiguous canonical workflow ID')
            found[workflow['id']] = path
    if set(found) != set(IDS):
        raise ValueError('Canonical workflow set is incomplete')
    return found


def export_live(update_latest=True):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target = ROOT / 'tmp/n8n-review' / stamp
    target.mkdir(parents=True)
    for workflow_id in IDS:
        remote = f'/tmp/n8n-review-{stamp}-{workflow_id}.json'
        subprocess.run(['docker', 'compose', 'exec', '-T', 'n8n', 'n8n', 'export:workflow', '--id', workflow_id, '--output='+remote], cwd=ROOT, capture_output=True, check=True)
        subprocess.run(['docker', 'compose', 'cp', 'n8n:'+remote, str(target / (workflow_id+'.json'))], cwd=ROOT, capture_output=True, check=True)
        workflow = read(target / (workflow_id+'.json'))
        if workflow['id'] != workflow_id:
            raise ValueError('Exported ID differs from requested ID')
    if update_latest:
        (target.parent / 'LATEST').write_text(target.relative_to(ROOT).as_posix(), encoding='utf-8')
    return target


def snapshot_changes(before, after):
    """Guard runtime, layout and publication; ignore only export bookkeeping."""
    fields = ('nodes', 'connections', 'settings', 'active', 'versionId', 'activeVersionId',
              'name', 'id', 'pinData', 'staticData')
    changed = [field for field in fields if before.get(field) != after.get(field)]
    if semantic(before) != semantic(after) and 'runtime_semantics' not in changed:
        changed.append('runtime_semantics')
    return changed


def note(workflow_id, label, role, xy, wh, content):
    return {'id':str(uuid.uuid5(uuid.NAMESPACE_URL, workflow_id+'/visual-review/'+label)),
            'name':'Guide: '+label, 'type':STICKY, 'typeVersion':1, 'position':list(xy),
            'parameters':{'content':content, 'width':wh[0], 'height':wh[1], 'color':COLORS[role]}}


LEGEND = ('### Legend · annotations do not execute\n'
          '**Icons + wires:** real n8n execution. **Notes:** explanations only.\n'
          'Blue = input/answer (closest available to teal); purple = routing; green = knowledge; '
          'gold = PDF/processing; red = safety; gray = infrastructure.\n'
          'LLM components and deterministic services run **inside FastAPI**; none plans or negotiates autonomously.')


def design(base, active):
    w = deepcopy(base)
    w['active'] = active
    w['nodes'] = executable(w)
    workflow_id = w['id']
    specs = []
    if workflow_id == IDS[0]:
        positions = {'Manual trigger':[0,180], 'Weekly refresh':[0,380], 'Download official documents':[440,280],
                     'Build chunks and index (both strategies)':[1070,280], 'Run summary':[2020,280]}
        specs = [
            ('01 · Triggers', 'input', [-80,-60], [360,620], '## 01 · Triggers\nManual entry or Monday 03:00 schedule.\n**UNPUBLISHED: schedule is not running.**\nDo not execute during the demonstration.'),
            ('02 · Official acquisition', 'knowledge', [320,-60], [420,620], '## 02 · Official acquisition\n**POST /ingestion/run** → FastAPI.\nRegistry approval, robots/AI opt-outs, TLS, type validation and SHA-256 provenance/deduplication.\nReturns counts/results; no new download in this review.'),
            ('03 · Processing and chunks', 'document', [780,-60], [600,620], '## 03 · Processing + two chunkers\n**POST /index/run** → FastAPI.\nPyMuPDF text layer; HTML/table structure; normalization and metadata.\n**Structure-aware** and **recursive** chunks.\nImage-only corpus PDFs are skipped; this ingestion path does not OCR them.'),
            ('04 · Embeddings and Qdrant', 'knowledge', [1420,-60], [430,620], '## 04 · Inside the indexing request\nOllama **bge-m3**, 1024 dimensions.\n`official_docs_structure` + `official_docs_recursive`.\nVectors + document/page/heading/URL/SHA metadata.\n**Indexing recreates both collections.** No separate executable embedding node.'),
            ('05 · Runtime summary', 'answer', [1890,-60], [430,620], '## 05 · Runtime summary\n`ingestion_counts`, `documents_indexed`, `documents_skipped`, `collection_points`.\nValues come from the run, not historical metrics.\nFailures stop the chain; no dedicated error response node.'),
            ('Safety and legend', 'security', [-80,610], [2400,220], '### Safety gate\nAdmin endpoints require **X-Admin-Key** on the hardened backend; without a configured admin key they fail closed. Credential setup and release require approval. No ingestion, indexing, schedule activation or Qdrant write is authorized by this diagram.\n'+LEGEND),
        ]
    elif workflow_id == IDS[1]:
        positions = {'POST /webhook/retrieve':[0,240], 'RAG Retriever (backend)':[600,240], 'Return passages':[1260,240]}
        specs = [
            ('01 · Retrieval request', 'input', [-80,-40], [460,530], '## 01 · POST /webhook/retrieve\nIndependent retrieval API.\nBody: `query`, `strategy`, `top_k`, `filters`, `min_score`.\nThis webhook does **not** invoke Intent Router or conversation memory.'),
            ('02 · Dense retrieval backend', 'knowledge', [440,-40], [600,530], '## 02 · POST /retrieve\nFastAPI → Ollama **bge-m3** → filtered Qdrant cosine search.\nSelect structure or recursive collection; filter metadata and minimum score.\n**This endpoint is dense retrieval, not workflow 03’s routed hybrid retriever.**\nX-Agent-Key is required only when backend enforcement is enabled.'),
            ('03 · Evidence response', 'answer', [1100,-40], [520,530], '## 03 · Return passages\nList of `RetrievedPassage` items: `score`, `text`, `chunk_id`, `citation`.\nCitation: document, URL/SHA, language, page/heading, applicability metadata.\nNo answer generation. HTTP failures currently stop execution; safe error output is a separate future change.'),
            ('Relationship and legend', 'infrastructure', [-80,540], [1700,280], '### Separate entry points\nWorkflow 03 calls **/agents/retrieve directly**, not this workflow. Both access the same project Qdrant collections; their retrieval contracts and ranking paths differ. No Execute Workflow node or workflow-to-workflow arrow is implemented.\n'+LEGEND),
        ]
    else:
        positions = {'POST /webhook/assistant':[0,380], 'File attached?':[280,380], 'Dossier mode?':[560,120],
                     'Dossier Validator':[920,-40], 'Respond: dossier check':[1320,-40],
                     'Form-Filling Helper':[920,200], 'Respond: form check':[1320,200],
                     'Intent Router':[560,560], 'Direct reply?':[840,560], 'Respond: direct reply':[1160,440],
                     'RAG Retriever':[1160,720], 'Checklist route?':[1480,720],
                     'Checklist Builder':[1800,560], 'Respond: checklist':[2120,560],
                     'Grounded Answer':[1800,840], 'Respond: answer':[2120,840], 'Respond: agent error':[2120,1260]}
        specs = [
            ('01 · User input', 'input', [-80,70], [520,700], '## 01 · Telegram / HTTP\nExternal bridge → **POST /webhook/assistant**.\nText/language/public context OR PDF/image. Chat/user IDs stay in the bridge; not sent as a session ID to n8n.\n**File attached? true → document path; false → Intent Router.**'),
            ('02 · PDF and dossier', 'document', [500,-280], [1040,640], '## 02 · Document assistance · deterministic FastAPI services\n**Dossier mode?** true → `/agents/dossier-check`; false → `/agents/form-check`.\nTyped uploads → PyMuPDF / Tesseract ara+fra, OpenCV alignment and ink checks; official RNE F-001 / F-002 templates. Dossier adds supported requirements and unverifiable items.\nFields are not legal approval; no private upload indexing or field values in logs.'),
            ('03 · Orchestration', 'routing', [500,400], [560,400], '## 03 · Intent routing\n`/agents/route`: rules first; Mistral fallback.\nLanguage, category, public facts → next agent.\n**Direct reply? true → response; false → RAG.**'),
            ('Direct response', 'answer', [1100,370], [460,180], '### Direct response\nClarification, greeting or supported refusal.'),
            ('04 · Routed retrieval', 'knowledge', [1100,570], [620,440], '## 04 · POST /agents/retrieve\nTyped query + route → passages.\nHybrid raw/expanded BGE-M3 + BM25, RRF fusion and per-document cap. No cross-encoder reranker.\n**Reviewed backend candidate adds exact RNE-code lookup; not in the current production image.**\nChecklist route? true → checklist; false → answer.'),
            ('05 · Response composition', 'answer', [1760,380], [650,650], '## 05 · Specialised composition\n`/agents/checklist`: official sections/rows; optional validated FR→EN translation.\n`/agents/answer`: gated Mistral answer + citation/number checks or source fallback. **Reviewed backend candidate adds deterministic legal extraction.**\nComposeRequest → typed result → original response nodes.'),
            ('Legal evidence', 'knowledge', [1100,1060], [620,350], '### Candidate legal service · NOT DEPLOYED\nReviewed source/candidate backend: exact articles/tables, source excerpts and limits handling. Production image has no legal_evidence module yet.\nNo legal-validity or dossier-approval certification. Citation-index and numeric checks do **not** prove semantic entailment. Topic checking is configuration-dependent (default off).'),
            ('06 · Errors and safety', 'security', [1760,1080], [650,360], '## 06 · Shared backend-error response\nSix HTTP error outputs → **503 agent_unavailable** + failed_agent; four-language notice. Retains Claude’s repository candidate.\nThis is a **functional addition versus live 16-node workflow**, not a visual-only change. No raw backend error body is returned. Authentication/validation errors also map to 503; review that limitation.'),
            ('External infrastructure', 'infrastructure', [-80,840], [1110,320], '### External / backend-internal · not additional n8n agents\nTelegram long polling and in-memory 30-minute sessions: private chat or group-member isolation in the **candidate bridge**. Production image must be checked separately.\nFastAPI on `backend:8000`; project Qdrant on `qdrant:6333`; local Ollama through `host.docker.internal:11434`.\nNo n8n session database; no workflow 02 call; successful/error/manual execution payload retention remains disabled.'),
            ('Legend and review boundary', 'infrastructure', [-80,1220], [1110,300], LEGEND+'\n\n**Draft for review only.** Live n8n remains unchanged. API keys are configured via Header Auth credentials in a separately coordinated release; no values are stored here.'),
        ]
    if set(positions) != {n['name'] for n in w['nodes']}:
        raise ValueError('Executable graph changed since layout design; review required')
    for node in w['nodes']:
        node['position'] = positions[node['name']]
    w['nodes'] += [note(workflow_id, *spec) for spec in specs]
    return w


def routes_from_source():
    result = set()
    for file, prefix in [('backend/main.py', ''), ('backend/agents_api.py', '/agents')]:
        tree = ast.parse((ROOT / file).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in {'get','post'} and dec.args and isinstance(dec.args[0], ast.Constant):
                        result.add((dec.func.attr.upper(), prefix+dec.args[0].value))
    return result


def validate(w, base=None):
    errors = []
    ids = [n['id'] for n in w['nodes']]
    names = [n['name'] for n in w['nodes']]
    if len(set(ids)) != len(ids): errors.append('duplicate_node_id')
    if len(set(names)) != len(names): errors.append('duplicate_node_name')
    by_name = {n['name']:n for n in w['nodes']}
    routes = routes_from_source()
    token_pattern = re.compile(r'\b\d{6,14}:[A-Za-z0-9_-]{25,}\b')
    if token_pattern.search(json.dumps(w)): errors.append('token_pattern')
    for n in w['nodes']:
        if n['type'].removeprefix('n8n-nodes-base.') not in SUPPORTED: errors.append('unsupported_type:'+n['name'])
        if len(n.get('position', [])) != 2: errors.append('invalid_position:'+n['name'])
        if n['type'] == STICKY:
            p = n['parameters']
            if n.get('typeVersion') != 1 or p.get('color') not in range(1,8): errors.append('sticky_compatibility:'+n['name'])
            if p.get('width',0)<240 or p.get('height',0)<160: errors.append('sticky_dimensions:'+n['name'])
        if n['type'].endswith('httpRequest'):
            p = n['parameters']
            if not p.get('url','').startswith('http://backend:8000/'): errors.append('unexpected_backend:'+n['name'])
            else:
                path = p['url'].removeprefix('http://backend:8000')
                if (p.get('method','GET'),path) not in routes: errors.append('missing_backend_route:'+n['name'])
            for header in p.get('headerParameters',{}).get('parameters',[]):
                if re.search(r'key|authorization|token',header.get('name',''),re.I) and header.get('value') and not header['value'].startswith('='):
                    errors.append('literal_secret_header:'+n['name'])
        for ref in re.findall(r"\$\(['\"]([^'\"]+)['\"]\)",json.dumps(n.get('parameters',{}))):
            if ref not in by_name: errors.append('invalid_expression_reference:'+n['name'])
    for name, groups in w['connections'].items():
        if name not in by_name or by_name[name]['type'] == STICKY: errors.append('invalid_connection_source:'+name)
        for branches in groups.values():
            for branch in branches:
                for edge in branch:
                    if edge['node'] not in by_name or by_name[edge['node']]['type'] == STICKY: errors.append('invalid_connection_target:'+name)
    if base and semantic(w) != semantic(base): errors.append('executable_semantics_changed')
    # Every executable node must be reachable from a real trigger, including the error responder.
    roots = [n['name'] for n in executable(w) if n['type'].split('.')[-1] in {'manualTrigger','scheduleTrigger','webhook'}]
    reached, pending = set(), list(roots)
    while pending:
        name = pending.pop()
        if name in reached: continue
        reached.add(name)
        pending += [edge['node'] for branches in w['connections'].get(name,{}).values() for branch in branches for edge in branch]
    if reached != {n['name'] for n in executable(w)}: errors.append('disconnected_execution_node')
    return {'workflow_id':w['id'], 'valid':not errors, 'errors':errors, 'executable_nodes':len(executable(w)),
            'sticky_notes':len(w['nodes'])-len(executable(w)), 'normalized_runtime_sha256':sha(semantic(w))}


def security_plan(workflows):
    plan = []
    for w in workflows:
        for node in executable(w):
            if node['type'].endswith('httpRequest'):
                path = node['parameters']['url'].removeprefix('http://backend:8000')
                admin = path in {'/ingestion/run','/index/run'}
                plan.append({'workflow_id':w['id'], 'node_id':node['id'], 'node_name':node['name'], 'endpoint':path,
                             'header_name':'X-Admin-Key' if admin else 'X-Agent-Key',
                             'backend_variable':'ADMIN_API_KEY' if admin else 'AGENT_API_KEY',
                             'enforcement':'disabled without configured admin key; else 401 for missing/invalid header' if admin else '401 when key configured; open when unset',
                             'credential_type':'httpHeaderAuth', 'credential_name':'TNAA Backend Admin' if admin else 'TNAA Backend Agent',
                             'credential_id':None, 'status':'operator_mapping_required_not_enabled',
                             'proposed_http_parameters':{'authentication':'genericCredentialType','genericAuthType':'httpHeaderAuth'}})
    return {'backend_calls':plan, 'webhook_auth':{'workflows':[IDS[1],IDS[2]], 'header_name':'X-Assistant-Key',
             'credential_type':'httpHeaderAuth', 'credential_name':'TNAA Assistant Entry', 'credential_id':None,
             'proposed_webhook_parameters':{'authentication':'headerAuth'},
             'status':'separate_approval_and_all_client_readiness_required',
             'note':'X-Assistant-Key is checked by n8n Header Auth, not by FastAPI. Bridge/web/CLI send ASSISTANT_WEBHOOK_KEY only when configured.'}}


def prepare(baseline):
    canonical = discover()
    results, candidates = [], []
    for workflow_id in IDS:
        repo = read(canonical[workflow_id])
        live = read(baseline / (workflow_id+'.json'))
        base = deepcopy(repo)
        base['active'] = live['active']
        candidate = design(base, live['active'])
        checked = validate(candidate, base)
        if not checked['valid']: raise ValueError(checked['errors'])
        target = OUTPUT / 'candidates' / canonical[workflow_id].name
        dump(target, candidate)
        report = {'workflow_id':workflow_id, 'name':live['name'], 'backup':(baseline/(workflow_id+'.json')).relative_to(ROOT).as_posix(),
                  'canonical':canonical[workflow_id].relative_to(ROOT).as_posix(), 'candidate':target.relative_to(ROOT).as_posix(),
                  'live_version_id':live.get('versionId'), 'live_active_version_id':live.get('activeVersionId'),
                  'live_executable_nodes':len(executable(live)), 'repository_executable_nodes':len(executable(repo)),
                  'live_vs_repository':difference(live,repo), 'live_vs_candidate':difference(live,candidate),
                  'repository_with_live_state_vs_candidate':difference(base,candidate), 'validation':checked}
        dump(OUTPUT / 'comparisons' / (workflow_id+'.json'), report)
        results.append(report);candidates.append(candidate)
    dump(OUTPUT/'security_mapping.json',security_plan(candidates))
    dump(OUTPUT/'review_manifest.json',{'expected_git_baseline':EXPECTED_HEAD, 'created_at':datetime.now(timezone.utc).isoformat(),
         'live_unchanged':True, 'imported_or_executed':False, 'baseline_directory':baseline.relative_to(ROOT).as_posix(),
         'authority':'repository executable definitions + verified live activation states; functional drift remains explicit', 'workflows':results})
    lines = ['# n8n workflow drift and candidate validation', '', 'Generated from read-only CLI exports. No workflow was imported, executed or published.', '',
             '| Workflow ID | Live executable | Repository executable | Candidate executable + notes | Live active | Repository active | Candidate runtime equals repository with live state |',
             '|---|---:|---:|---:|---|---|---|']
    for r in results:
        v=r['validation'];d=r['live_vs_repository']
        lines.append(f"| {r['workflow_id']} | {r['live_executable_nodes']} | {r['repository_executable_nodes']} | {v['executable_nodes']} + {v['sticky_notes']} | {d['active_before']} | {d['active_after']} | {r['repository_with_live_state_vs_candidate']['semantic_equal']} |")
    lines += ['', '## Reviewed authority and drift', '',
              '- Workflow 01: keep live inactive. The two backend writes remain unchanged and are never exercised by review tools.',
              '- Workflow 02: repository says inactive; live is active. Candidate preserves the verified live state. It calls dense `/retrieve`, not hybrid `/agents/retrieve`.',
              '- Workflow 03: retain the 17-node repository definition, including Claude’s six error outputs and shared 503 responder. This is a functional difference from live, not layout-only.',
              '- All three add native Sticky Notes and node positions only relative to their selected executable baseline. No existing executable name, ID, expression, parameter, connection, webhook or setting is changed.',
              '- Authentication is audited and specified in `security_mapping.json`; primary candidates do not turn on keys, change credentials or create unresolved credential references. Secure activation is a separate coordinated release gate.',
              '- Native rendering/import, live failure simulations and authentication against real credentials have not been tested. Static compatibility uses the installed Sticky Note v1 schema and seven palette variants.', '',
              '## Backup paths', '']
    lines += ['- `'+r['backup']+'`' for r in results]
    lines += ['', '## Semantic comparison rules', '', 'Executable nodes exclude Sticky Notes; only node position and descriptive notes are ignored. Ordered IF output arrays, node names/IDs, expressions, parameters, credentials, onError, activation, settings, pin/static data and unknown top-level fields remain significant. Server version/timestamp/sharing metadata is excluded. Hashes accompany structured diffs; they are not the sole equivalence proof.']
    (OUTPUT/'COMPARISON.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    return results


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export',action='store_true',help='Read live workflow definitions via official n8n CLI; never imports or executes')
    parser.add_argument('--baseline',type=Path,help='Previously exported three-workflow directory')
    parser.add_argument('--prepare',action='store_true',help='Write offline candidates and comparison artifacts only')
    parser.add_argument('--verify-live',action='store_true',help='Re-export and abort on runtime, layout or publication drift from baseline; never applies candidates')
    args=parser.parse_args()
    baseline=export_live() if args.export else args.baseline
    if baseline is None:
        baseline=ROOT / (ROOT/'tmp/n8n-review/LATEST').read_text(encoding='utf-8').strip()
    baseline=baseline if baseline.is_absolute() else ROOT/baseline
    if args.verify_live:
        if args.export or args.prepare:
            parser.error('--verify-live must not be combined with --export or --prepare')
        current=export_live(update_latest=False)
        changes={i:snapshot_changes(read(baseline/(i+'.json')),read(current/(i+'.json'))) for i in IDS}
        report={'checked_at':datetime.now(timezone.utc).isoformat(), 'baseline':baseline.relative_to(ROOT).as_posix(),
                'current_export':current.relative_to(ROOT).as_posix(), 'changed_fields':changes,
                'unchanged':not any(changes.values()), 'live_writes':False}
        dump(OUTPUT/'live_integrity.json',report)
        print(json.dumps(report))
        raise SystemExit(0 if report['unchanged'] else 1)
    elif args.prepare:
        results=prepare(baseline)
        print(json.dumps([{'id':r['workflow_id'],**r['validation']} for r in results]))
    else:
        canonical=discover()
        print(json.dumps({i:difference(read(baseline/(i+'.json')),read(canonical[i])) for i in IDS}))
