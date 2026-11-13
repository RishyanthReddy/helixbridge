"""One predeclared hotspot/seed case, retaining native output and Boltz refold."""
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest,write_json,run_task
from binder_campaign.candidates import import_rfd4
root=Path(os.environ['TASK_ROOT']);pipeline=root/'src/pipeline';folder=root/'results/site-diversity-pilot-v1'
arm=sys.argv[1];seed=int(sys.argv[2]);case=f'{arm}-s{seed}'
plan=json.loads((folder/'execution-plan.json').read_text())
if case not in plan['case_stems']:raise ValueError('Unplanned arm/seed')
campaign='site-'+case;result=root/f'results/{campaign}-v1';reference=folder/'inputs'/arm
task={'cwd':str(pipeline),'revision':'Pinned RFD4 thinking_high; target-only; new60aa segment',
    'command':[str(root/'env/rfd4/bin/python'),'scripts/rfd4-site-pilot.py',str(reference/'audit.json'),str(result/'prediction'),str(seed)],
    'timeout_seconds':230,'inputs':[str(reference/n) for n in ('target.cif','conditions.json','audit.json')]+
        [str(pipeline/'scripts/rfd4-site-pilot.py'),str(root/'env/rfd4-checkpoints.json'),str(root/'env/rfd4-freeze.txt')],
    'outputs':[{'path':str(result/'prediction/audit.json'),'kind':'json'},{'path':str(result/'prediction/model.cif'),'kind':'file'}],
    'state':str(result/'task-state.json'),'log':str(result/'generation.log')}
write_json(result/'generation-task.json',task);run_task(result/'generation-task.json')
records_path=result/'candidates.json'
if records_path.exists():raise ValueError('Fresh import required')
record=import_rfd4(result/'prediction/audit.json',pipeline/'data/targets/il7ra/manifest.json',records_path)[0]
if record['qc_reasons']:raise ValueError('Format QC failed')
duplicates=[]
for path in (root/'results').glob('*-v1/candidates.json'):
    if path==records_path:continue
    for row in json.loads(path.read_text())['candidates']:
        if row['sequence']==record['sequence']:duplicates.append(row['candidate_id'])
if duplicates:
    write_json(result/'duplicate-hold.json',{'duplicates':duplicates});raise ValueError('Exact duplicate')
subprocess.run([str(root/'env/rfd4/bin/python'),'scripts/prepare-candidate-evaluation.py',str(records_path),
                str(result/'evaluation-input'),campaign,'0'],check=True)
path=result/'evaluation-input/boltz-task.json';spec=json.loads(path.read_text());spec['timeout_seconds']=150
write_json(path,spec);run_task(path)
write_json(result/'starting-input-audit.json',{'candidate_id':record['candidate_id'],'arm':arm,'seed':seed,
    'initialization_review':'target_only_hotspot_variation_reviewed','supplied_starting_binder_sequence_or_coordinates':False,
    'source_conditions_sha256':digest(reference/'conditions.json'),'source_target_cif_sha256':digest(reference/'target.cif'),
    'executed_model_state_sha256':digest(result/'task-state.json'),'candidate_records_sha256':digest(records_path),
    'input_review_sha256':digest(folder/'input-review.json'),'submission_eligible':False})
print('Completed generation and Boltz:',case,record['candidate_id'],flush=True)
