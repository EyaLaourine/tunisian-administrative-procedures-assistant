"""Offline note-only presentation candidates from explicitly selected live backups.

No API client, credentials, imports, publication or container commands are used.
Executable nodes (including their positions) and every connection remain exact.
"""
import argparse
from copy import deepcopy
import hashlib
from pathlib import Path

from scripts.n8n_workflow_review import ROOT, IDS, STICKY, read, dump, semantic, sha, validate

OUTPUT = ROOT/'deploy/n8n_presentation'
FILENAMES = ('01_ingest_and_index.json','02_retrieve_api.json','03_assistant_multi_agent.json')
PRESENTATION_PARAMETERS = {'content','width','height','color'}

CONTENTS = {
    IDS[0]: [
        '### 01 · Trigger\nManual or scheduled entry point.\nInactive: do not execute during the demonstration.',
        '### 02 · Official Sources\nDownload approved official documents with provenance checks.\nSource policies and document validation remain enforced.',
        '### 03 · Document Processing\nThe backend extracts text and document structure.\nStructural and recursive chunks prepare the evidence.',
        '### 04 · Embeddings & Qdrant\nBGE-M3 embeds chunks into two Qdrant collections.\nThese stages run inside the indexing service.',
        '### 05 · Run Summary\nReport ingestion, indexing and collection counts.\nNo live run is required to explain the pipeline.',
        '### Pipeline Safety\nBackend stages: extraction → chunking → embeddings → indexing.\nIndexing recreates collections. Keep this workflow inactive.',
    ],
    IDS[1]: [
        '### 01 · Retrieval Request\nPOST /webhook/retrieve accepts a retrieval query.\nThis entry point is independent of the assistant workflow.',
        '### 02 · RAG Retriever\nBGE-M3 embeddings drive filtered, dense Qdrant search.\nThis endpoint returns passages; it does not generate answers.',
        '### 03 · Grounded Evidence\nReturn ranked passages with official-source citations.\nEvidence supports downstream answers and manual review.',
        '### Retrieval Boundary\nWorkflow 03 calls its backend retrieval agent directly.\nThis API uses dense retrieval; it does not orchestrate dialogue.',
    ],
    IDS[2]: [
        '### 01 · Request Entry\nTelegram / HTTP requests enter the assistant webhook.\nFile detection separates document and text requests.',
        '### 02 · Document Processing\nPDF/image uploads → Form Helper or Dossier Validator.\nOnly the competent administration can approve a dossier.',
        '### 03 · Intent Routing\nSelect the procedure and response path.\nReturn clarification directly when needed.',
        '### Direct Response\nGreeting, clarification or supported refusal.',
        '### 04 · Evidence Retrieval\nRetrieve official passages for the selected procedure.\nPass evidence to checklist or grounded-answer services.',
        '### 05 · Specialized Agents\nChecklist Builder extracts source-backed requirements.\nGrounded Answer composes a cited response.',
        '### Scope & Limitations\nAssistance does not certify legal completeness.\nEnhanced legal extraction is not deployed in the running backend.',
        '### 06 · Error Handling\nSix backend error outputs share a sanitized HTTP 503 response.\nAuthentication and validation failures may also appear as 503.',
        '### Backend Services\nn8n orchestrates; FastAPI runs specialized services.\nLocal models and Qdrant support inference and retrieval.',
        '### Reading the Diagram\nColored panels identify stages; wires show execution.\nServices are orchestrated, without autonomous planning.',
    ],
}


def visual_projection(workflow):
    """Erase only allowed note presentation fields; retain every executable field."""
    result=deepcopy(workflow)
    # Server-managed ownership is excluded from publishable artifacts.
    result.pop('shared',None)
    for node in result['nodes']:
        if node['type']==STICKY:
            node.pop('position',None)
            for key in PRESENTATION_PARAMETERS:node['parameters'].pop(key,None)
    return result


def assert_visual_only(before,after):
    if visual_projection(before)!=visual_projection(after):
        raise ValueError('Non-presentation field changed')
    if semantic(before)!=semantic(after):
        raise ValueError('Execution semantics changed')
    if not validate(after,before)['valid']:
        raise ValueError('Invalid candidate graph')


def polish(workflow):
    result=deepcopy(workflow)
    result.pop('shared',None)
    notes=[n for n in result['nodes'] if n['type']==STICKY]
    texts=CONTENTS[result['id']]
    if len(notes)!=len(texts):raise ValueError('Unexpected note set')
    for note,text in zip(notes,texts):note['parameters']['content']=text
    # Shorter explanatory cards reduce the total canvas extent. Main stage
    # frames, all colors and every executable node position remain unchanged.
    if result['id']==IDS[0]:notes[5]['parameters']['height']=180
    elif result['id']==IDS[1]:notes[3]['parameters']['height']=200
    else:
        notes[6]['parameters']['height']=240
        notes[8]['parameters']['height']=240
        notes[9]['position']=[-80,1140]
        notes[9]['parameters']['height']=240
    assert_visual_only(workflow,result)
    return result


def prepare(baseline):
    results=[];changes=[]
    for wid,filename in zip(IDS,FILENAMES):
        path=baseline/(wid+'.json');before=read(path)
        if before['id']!=wid:raise ValueError('Wrong backup ID')
        after=polish(before);target=OUTPUT/'candidates'/filename;dump(target,after)
        old_notes=[n for n in before['nodes'] if n['type']==STICKY]
        new_notes=[n for n in after['nodes'] if n['type']==STICKY]
        for old,new in zip(old_notes,new_notes):
            changes.append({'workflow_id':wid,'note_id':old['id'],'note_name':old['name'],
                            'before':{'position':old['position'],'parameters':old['parameters']},
                            'after':{'position':new['position'],'parameters':new['parameters']}})
        results.append({'id':wid,'baseline_file':path.relative_to(ROOT).as_posix(),
                        'baseline_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                        'candidate_file':target.relative_to(ROOT).as_posix(),
                        'candidate_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                        'executable_nodes':len(after['nodes'])-len(new_notes),'sticky_notes':len(new_notes),
                        'active':after['active'],'baseline_version_id':before.get('versionId'),
                        'baseline_active_version_id':before.get('activeVersionId'),
                        'functional_projection_equal':True,'execution_semantics_equal':True,
                        'functional_projection_sha256':sha(visual_projection(after)),
                        'executable_positions_unchanged':True,'note_ids_preserved':True,'connections_unchanged':True,
                        'settings_credentials_webhooks_publication_unchanged':True,
                        'before_note_words':sum(len(n['parameters']['content'].split()) for n in old_notes),
                        'after_note_words':sum(len(n['parameters']['content'].split()) for n in new_notes)})
    dump(OUTPUT/'annotation_changes.json',changes)
    dump(OUTPUT/'review_manifest.json',{'status':'OFFLINE_VISUAL_CANDIDATES_AWAITING_APPROVAL',
         'live_workflows_modified':False,'executable_nodes_moved':False,
         'authority':'fresh verified synchronized live definitions; note-only changes',
         'workflows':results})
    lines=['# Exact annotation changes — offline proposal','',
           'Only note content and the listed note geometry change. Colors, executable positions and all functional fields remain exact.','']
    for c in changes:
        lines+=['## '+c['workflow_id']+' · '+c['note_name'],'','Node ID: `'+c['note_id']+'`','',
                '```diff']+['- '+s for s in c['before']['parameters']['content'].splitlines()]+['+ '+s for s in c['after']['parameters']['content'].splitlines()]+['```','']
        if c['before']['position']!=c['after']['position'] or c['before']['parameters']['height']!=c['after']['parameters']['height']:
            lines+=['Geometry: `'+str(c['before']['position'])+'`, height `'+str(c['before']['parameters']['height'])+'` → `'+str(c['after']['position'])+'`, height `'+str(c['after']['parameters']['height'])+'`.','']
    (OUTPUT/'ANNOTATION_DIFF.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    return results


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    args=parser.parse_args()
    baseline=args.baseline if args.baseline.is_absolute() else ROOT/args.baseline
    for row in prepare(baseline):print(row['id']+': '+str(row['executable_nodes'])+' executable, '+str(row['sticky_notes'])+' notes; visual-only')
