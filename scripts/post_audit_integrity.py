"""Read-only integrity and deployment-status evidence; never prints environment secrets."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
from qdrant_client import QdrantClient
from backend.settings import get_settings


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = ROOT / 'data/evaluation'
    baseline = json.loads((out / 'post_audit_backup/baseline.json').read_text(encoding='utf-8'))['sha256']
    audit = json.loads((out / 'full_document_coverage_snapshot.json').read_text(encoding='utf-8'))
    changes = [name for name, sha in baseline.items() if not (ROOT / name).exists() or digest(ROOT / name) != sha]
    immutable_prefixes = ('rag/', 'ingestion/', 'config/', 'workflows/', 'prompts/', 'data/raw/', 'data/processed/', 'data/evaluation/full_document_coverage')
    protected_changes = [name for name in changes if name.startswith(immutable_prefixes) or name in {'agents/form_helper.py', 'agents/dossier_validator.py', 'agents/verification.py'}]
    settings = get_settings()
    client = QdrantClient(settings.qdrant_url, api_key=settings.qdrant_api_key or None, timeout=60)
    collections = {}
    for name, original in audit['collections'].items():
        points, offset = [], None
        while True:
            batch, offset = client.scroll(name, limit=256, offset=offset, with_payload=True, with_vectors=False)
            points += [{'id': str(point.id), 'payload': point.payload} for point in batch]
            if offset is None:
                break
        points.sort(key=lambda p:p['id'])
        sha = hashlib.sha256(json.dumps(points, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        collections[name] = {'count': len(points), 'payload_sha256': sha, 'unchanged': sha == original['payload_sha256']}
    command = subprocess.run(['docker', 'compose', '--profile', 'telegram', 'ps', '--format', 'json'], capture_output=True, text=True, check=True)
    services = [{key: row.get(key) for key in ['Service', 'ID', 'Image', 'State', 'Health']} for row in map(json.loads, command.stdout.splitlines())]
    originals = {s['Service']:s for s in audit['services']}
    for service in services:
        service['same_container_as_audit'] = service['ID'] == originals.get(service['Service'], {}).get('ID')
    health = {}
    with httpx.Client(timeout=20) as http:
        for name, url in [('backend', 'http://localhost:8000/health'), ('candidate_backend', 'http://localhost:8001/health'),
                          ('n8n', 'http://localhost:5678/healthz'), ('candidate_n8n', 'http://localhost:5679/healthz')]:
            response = http.get(url)
            health[name] = {'status_code': response.status_code, 'body': response.json()}
    subprocess.run(['docker', 'compose', 'exec', '-T', 'n8n', 'n8n', 'export:workflow', '--id', 'TnaaAssistant01', '--output=/tmp/post-audit-after.json'], capture_output=True, check=True)
    subprocess.run(['docker', 'compose', 'cp', 'n8n:/tmp/post-audit-after.json', str(out / 'post_audit_backup/active_workflow_after.json')], capture_output=True, check=True)
    before = json.loads((out / 'post_audit_backup/active_workflow.json').read_text(encoding='utf-8'))
    after = json.loads((out / 'post_audit_backup/active_workflow_after.json').read_text(encoding='utf-8'))
    result = {'at': datetime.now(timezone.utc).isoformat(), 'modified_existing_files': changes,
              'protected_changes': protected_changes, 'collections': collections, 'services': services,
              'health': health, 'active_workflow_unchanged': before == after,
              'deployment': 'candidate_only_production_unchanged', 'telegram_live_message_test': 'not_performed'}
    (out / 'post_audit_integrity.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'modified_existing_files': changes, 'protected_changes': protected_changes,
                      'qdrant_unchanged': all(v['unchanged'] for v in collections.values()),
                      'active_workflow_unchanged': before == after,
                      'production_containers_unchanged': all(v['same_container_as_audit'] for v in services)}))


if __name__ == '__main__':
    main()
