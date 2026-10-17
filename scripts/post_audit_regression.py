"""Replay selected original audit cases against the isolated candidate n8n pipeline.

The original suite, original results and scores are never overwritten. No Telegram API
is called. The candidate workflow is a copy, with only backend URLs redirected.
"""
import argparse
import asyncio
import base64
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
from scripts.audit_full_coverage import assess

OUT = ROOT / 'data/evaluation'
SUITE = OUT / 'full_document_coverage.json'
LEGAL = {'rne-arrete-2026-35', 'rne-law-2018-52-ar', 'rne-decree-beneficial-owners',
         'rne-decree-name-reservation', 'rne-decree-2022-298-fees-fr', 'rne-decree-law-2022-18-fr'}


def cases():
    suite = json.loads(SUITE.read_text(encoding='utf-8'))
    always = {'formalities_row', 'formalities_row_dialogue', 'guide_scenario', 'guide_fee',
              'fresh_cin_profile', 'fresh_passport_profile', 'upload', 'upload_error',
              'unsupported_upload', 'dialogue_regression', 'unsupported_birth_certificate'}
    return [c for c in suite['tests'] if c['kind'] in always or
            (c['document_id'] in LEGAL and c['kind'] in {'direct_factual', 'multi_turn', 'multilingual', 'fee_service', 'fee_condition', 'scenario_specific', 'adversarial'})]


async def run(url, label, only=None, backend_url='http://localhost:8001'):
    output = OUT / f'post_audit_{label}_results.jsonl'
    selected = [c for c in cases() if not only or only in c['id']]
    manifest = {r['doc_id']: r for r in json.loads((ROOT / 'data/raw/manifest.json').read_text(encoding='utf-8'))['records']}
    previous = [json.loads(line) for line in output.read_text(encoding='utf-8').splitlines()] if output.exists() else []
    done = {r['id'] for r in previous}
    semaphore = asyncio.Semaphore(2)
    start = time.monotonic()
    async with httpx.AsyncClient(timeout=httpx.Timeout(900, connect=15)) as client:
        async def post(body):
            response = await client.post(url, json=body)
            response.raise_for_status()
            return response.json()

        async def one(case):
            async with semaphore:
                t0 = time.monotonic()
                row = {'id': case['id'], 'kind': case['kind'], 'language': case['language'],
                       'started_at': datetime.now(timezone.utc).isoformat(), 'url': url,
                       'original_suite_sha256': hashlib.sha256(SUITE.read_bytes()).hexdigest(),
                       'setup_responses': []}
                try:
                    context = case['conversation_context']
                    for setup in case['conversation_setup']:
                        response = await post(setup)
                        row['setup_responses'].append(response)
                        context = response.get('context')
                    body = {'text': case['question'], 'language': case['language']}
                    if context is not None:
                        body['context'] = context
                    spec = case.get('upload')
                    if spec:
                        if spec.get('fixture'):
                            pdf = spec['fixture'] == 'corrupt_pdf'
                            data = b'%PDF-1.0\nneutral invalid file' if pdf else b'neutral placeholder'
                            name, mime = ('neutral.pdf', 'application/pdf') if pdf else ('neutral.txt', 'text/plain')
                        else:
                            path = ROOT / spec['raw_file']
                            data = path.read_bytes()
                            name, mime = path.name, 'application/pdf'
                            if spec['media'] == 'image':
                                import fitz
                                with fitz.open(path) as pdf:
                                    data = pdf[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).tobytes('png')
                                name, mime = path.stem + '.png', 'image/png'
                        body = {'file': {'filename': name, 'mime_type': mime, 'data_b64': base64.b64encode(data).decode()}, 'language': case['language']}
                        if spec['mode'] == 'dossier':
                            body['mode'] = 'dossier'
                    response = await post(body)
                    row.update(status='completed', response=response, checks=assess(case, response, manifest))
                    if case['kind'] in {'formalities_row', 'formalities_row_dialogue'}:
                        trace = await client.post(backend_url + '/agents/retrieve', json={'query': case['question'], 'route': response['route'], 'top_k': 8})
                        trace.raise_for_status()
                        row['retrieval_trace'] = trace.json()
                except Exception as exc:
                    row.update(status='error', error_type=type(exc).__name__)
                row['seconds'] = round(time.monotonic() - t0, 3)
                with output.open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(row, ensure_ascii=False) + '\n')
                previous.append(row)
                if len(previous) % 25 == 0 or row['status'] == 'error':
                    print(json.dumps({'finished': len(previous), 'selected': len(selected), 'elapsed_s': round(time.monotonic() - start), 'last_status': row['status']}), flush=True)
        await asyncio.gather(*(one(c) for c in selected if c['id'] not in done))
    summarize(label)


def summarize(label):
    rows = [json.loads(line) for line in (OUT / f'post_audit_{label}_results.jsonl').read_text(encoding='utf-8').splitlines()]
    groups = defaultdict(list)
    for row in rows:
        groups[row['kind']].append(row)
    report = {'executed': len(rows), 'selected_total': len(cases()), 'groups': {}, 'semantic_accuracy': 'Not estimated. Exact source-fact and provenance checks are separate diagnostics.'}
    for kind, group in groups.items():
        checks = [r.get('checks', {}) for r in group]
        assessed = [c['requested_source_fact_correct'] for c in checks if c.get('requested_source_fact_correct') is not None]
        times = sorted(r['seconds'] for r in group)
        report['groups'][kind] = {'executed': len(group), 'http_completed': sum(r['status'] == 'completed' for r in group),
            'exact_facts_assessed': len(assessed), 'exact_facts_correct': sum(assessed),
            'diagnostic_failures': sum(bool(c.get('automatic_failures')) for c in checks),
            'citation_total': sum(c.get('citations_total', 0) for c in checks), 'citation_valid': sum(c.get('citations_valid', 0) for c in checks),
            'intent_assessed': sum(c.get('intent_match') is not None for c in checks), 'intent_correct': sum(c.get('intent_match') is True for c in checks),
            'latency_median_s': times[len(times)//2], 'latency_p95_s': times[min(len(times)-1, int(len(times)*.95))]}
    (OUT / f'post_audit_{label}_summary.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://localhost:5679/webhook/assistant')
    parser.add_argument('--label', default='candidate')
    parser.add_argument('--only')
    parser.add_argument('--summary', action='store_true')
    parser.add_argument('--backend-url', default='http://localhost:8001')
    args = parser.parse_args()
    if args.summary:
        summarize(args.label)
    else:
        asyncio.run(run(args.url, args.label, args.only, args.backend_url))
