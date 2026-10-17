"""Apply explicitly approved note-only candidates through the validated API release engine."""
import argparse
import hashlib
from pathlib import Path
from scripts import n8n_controlled_sync as sync
from scripts.n8n_presentation_polish import assert_visual_only
from scripts.n8n_workflow_review import ROOT, IDS, read

HASHES = {
 'TnaaIngestIndex1': ('01_ingest_and_index.json','e7ce4f3e1ef58bb65c163798f9ed24e2a84ae6f051824c3e23642d8f2d097ca6'),
 'TnaaRetrieveApi1': ('02_retrieve_api.json','e21e877f5bb40703c4167a48058d49f144480c39f1706f760b528a4db85c4b39'),
 'TnaaAssistant01': ('03_assistant_multi_agent.json','e5448181b6bb3db955bbf050713e8bd0ddecbba7d0bf06173e8268d4f329024e'),
}
def approved_candidate(wid):
    filename, digest = HASHES[wid]
    path = ROOT/'deploy/n8n_presentation/candidates'/filename
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise sync.SyncError('presentation_candidate_hash_changed')
    baseline = read(ROOT/'tmp/n8n-review/20261017T232316167115Z'/(wid+'.json'))
    candidate = read(path)
    assert_visual_only(baseline, candidate)
    return candidate

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['preflight','apply-one'])
    parser.add_argument('--release',type=Path,required=True)
    parser.add_argument('--cli-backup',type=Path)
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--workflow',choices=IDS)
    args=parser.parse_args()
    sync.candidate=approved_candidate
    try:
        for wid in IDS: approved_candidate(wid)
        raise SystemExit(sync.main(args))
    except (sync.SyncError,ValueError) as error:
        print(__import__('json').dumps({'status':'stopped','reason':str(error)}))
        raise SystemExit(1)
