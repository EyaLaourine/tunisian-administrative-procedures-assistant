"""Opt-in actual API fixture tests in a new disposable container; never edits existing containers."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = 'tunisian-admin-assistant-n8n-1'


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, encoding='utf-8', check=True, **kwargs)


def inspect(name):
    return json.loads(run(['docker','inspect',name]).stdout)[0]


def identity(container):
    return {key:value for key,value in {
        'id':container['Id'],'image':container['Image'],'started_at':container['State']['StartedAt'],
        'restarts':container['RestartCount']}.items()}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-disposable',action='store_true',required=True,
                        help='Explicitly opt into starting and removing only a new isolated fixture container')
    parser.add_argument('--output',type=Path,default=ROOT/'tmp/n8n-api-review/sandbox-result.json')
    args=parser.parse_args()
    before=identity(inspect(PRODUCTION))
    name='tnaa-api-review-'+uuid.uuid4().hex[:12]
    source=(ROOT/'tests/n8n_api_sandbox.cjs').read_text(encoding='utf-8')
    cid=None
    report=None
    try:
        cid=run(['docker','run','-d','--name',name,'--hostname','tnaa-api-review-sandbox',
                 '--label','tnaa.api-review.disposable=true','--network','none','--memory','1g','--cpus','1',
                 '--no-healthcheck','--tmpfs','/home/node/.n8n:rw,size=128m,uid=1000,gid=1000,mode=0700',
                 '-e','N8N_API_REVIEW_SANDBOX=1','-e','N8N_DIAGNOSTICS_ENABLED=false',
                 '-e','N8N_VERSION_NOTIFICATIONS_ENABLED=false','-e','N8N_TEMPLATES_ENABLED=false',
                 '-e','N8N_RUNNERS_ENABLED=false','-e','N8N_ENCRYPTION_KEY=neutral-disposable-test-key-only',
                 '-e','N8N_SECURE_COOKIE=false',before['image']]).stdout.strip()
        sandbox=inspect(cid)
        assert sandbox['Id']!=before['id'] and sandbox['HostConfig']['NetworkMode']=='none'
        assert not sandbox['HostConfig'].get('PortBindings') and not sandbox['HostConfig'].get('Binds')
        assert not sandbox['Mounts'], 'Unexpected external volume mount'
        result=subprocess.run(['docker','exec','-i',cid,'node','-'],input=source,timeout=240,
                              capture_output=True,text=True,encoding='utf-8',check=False)
        report=json.loads(result.stdout.strip().splitlines()[-1])
        report.update({'checked_at':datetime.now(timezone.utc).isoformat(),'image_id':before['image'],
                       'fixture_sha256':hashlib.sha256(source.encode()).hexdigest(),
                       'production_n8n_identity_unchanged':identity(inspect(PRODUCTION))==before,
                       'host_ports':False,'production_mounts':False})
    finally:
        if cid:
            target=inspect(cid)
            assert target['Id']==cid and cid!=before['id']
            assert target['Config']['Labels'].get('tnaa.api-review.disposable')=='true'
            assert target['HostConfig']['NetworkMode']=='none' and not target['HostConfig'].get('Binds')
            run(['docker','rm','-f',cid])
            if report is not None:report['disposable_container_removed']=True
    if report is not None:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(report))
        raise SystemExit(0 if report['status']=='passed' and report['production_n8n_identity_unchanged'] else 1)
