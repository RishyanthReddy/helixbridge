"""One seed-diverse RFD4 rehearsal, common refolds and independent audits on one GPU."""
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest,write_json,run_task
from binder_campaign.candidates import import_rfd4

root=Path(os.environ['TASK_ROOT']); pipeline=root/'src/pipeline'
seed=int(sys.argv[1])
plan_path=root/'results/robust-localfold-campaign-v1/campaign-plan.json'
plan=json.loads(plan_path.read_text())
if seed not in plan['design_seeds'] or seed not in range(101,113):raise ValueError('Unplanned design seed')
campaign=f'rfd4-il7ra-campaign-s{seed}'
result=root/f'results/{campaign}-v1'; result.mkdir(parents=True,exist_ok=True)
reference=pipeline/'data/targets/il7ra/rfd4-reference'
for name,expected in plan['reference_files_sha256'].items():
    if digest(reference/name)!=expected:raise ValueError('Campaign reference recipe changed')
task={'cwd':str(pipeline),'revision':'paired pinned RFD4; thinking_high, one new 60-residue binder',
    'command':[str(root/'env/rfd4/bin/python'),'scripts/rfd4-il7ra-seed.py',str(reference/'audit.json'),str(result/'prediction'),str(seed)],
    'timeout_seconds':280,
    'inputs':[str(reference/name) for name in ['audit.json','target.cif','conditions.json']]+
       [str(pipeline/'scripts/rfd4-il7ra-seed.py'),str(root/'env/rfd4-checkpoints.json'),
        str(root/'env/rfd4-freeze.txt'),str(plan_path)],
    'outputs':[{'path':str(result/'prediction/audit.json'),'kind':'metrics_json','finite_keys':['generation_seconds','peak_reserved_mib']},
               {'path':str(result/'prediction/model.cif'),'kind':'file'}],
    'state':str(result/'task-state.json'),'log':str(result/'generation.log')}
write_json(result/'generation-task.json',task)
run_task(result/'generation-task.json')
records_path=result/'candidates.json'
if records_path.exists():raise ValueError('Fresh campaign import required; inspect before any recovery')
records=import_rfd4(result/'prediction/audit.json',pipeline/'data/targets/il7ra/manifest.json',records_path)
record=records[0]
if record['qc_reasons']:raise ValueError('Generator import failed QC')
duplicates=[]
for other in (root/'results').glob('*-v1/candidates.json'):
    if other==records_path:continue
    for row in json.loads(other.read_text())['candidates']:
        if row['sequence']==record['sequence']:duplicates.append(row['candidate_id'])
if duplicates:
    write_json(result/'duplicate-hold.json',{'duplicates':duplicates,'submission_eligible':False})
    raise ValueError('Exact duplicate; no additional prediction GPU time spent')
anchor_path=root/'results/rfd4-il7ra-high-s43-v1/starting-input-audit.json'
anchor=json.loads(anchor_path.read_text())
if (anchor['supplied_starting_binder_sequence_or_coordinates'] is not False
    or anchor['source_conditions_sha256']!=digest(reference/'conditions.json')
    or anchor['source_target_cif_sha256']!=digest(reference/'target.cif')):
    raise ValueError('Reviewed target-only recipe does not match campaign input')
write_json(result/'starting-input-audit.json',{'candidate_id':record['candidate_id'],
    'initialization_review':'same_hashes_as_previously_audited_target_only_recipe',
    'supplied_starting_binder_sequence_or_coordinates':False,
    'source_conditions_sha256':digest(reference/'conditions.json'),'source_target_cif_sha256':digest(reference/'target.cif'),
    'executed_model_state_sha256':digest(result/'task-state.json'),'candidate_records_sha256':digest(records_path),
    'anchor_audit_sha256':digest(anchor_path),'submission_eligible':False,
    'scope':'Target-only recipe and exact duplicates; broad novelty and assay construct unresolved'})
subprocess.run([str(root/'env/rfd4/bin/python'),'scripts/prepare-candidate-evaluation.py',str(records_path),
    str(result/'evaluation-input'),campaign,'0'],check=True)
for model in ('esmfold2','boltz'):
    path=result/f'evaluation-input/{model}-task.json'; spec=json.loads(path.read_text());spec['timeout_seconds']=280
    write_json(path,spec);run_task(path)
review=root/f'results/{campaign}-review-v1'
subprocess.run([str(root/'env/rfd4/bin/python'),'scripts/review-rehearsal.py',str(review),str(records_path),campaign],check=True)
for script in ('audit-pose-fit.py','audit-il7ra-target-context.py'):
    subprocess.run([str(root/'env/boltz/bin/python'),'scripts/'+script,campaign,str(records_path)],check=True)
(review/'starting-input-audit.json').write_bytes((result/'starting-input-audit.json').read_bytes())
print('Complete diagnostic campaign case:',seed,record['candidate_id'],flush=True)
