"""Predeclare two added prediction seeds for the existing seed-43 candidate."""
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import write_json,digest

root=Path(os.environ['TASK_ROOT']); pipeline=root/'src/pipeline'
records=root/'results/rfd4-il7ra-high-s43-v1/candidates.json'
candidate=json.loads(records.read_text())['candidates'][0]
if candidate['candidate_id']!='il7ra-rfd4-2ced05176b85' or candidate['submission_eligible']:
    raise ValueError('Unexpected robustness candidate')
folder=root/'results/robust-localfold-campaign-v1'
plan_path=folder/'robustness-plan.json'
if plan_path.exists(): raise ValueError('Robustness plan already exists')
tasks=[]
for seed in (1,2):
    campaign=f'rfd4-il7ra-high-s43-eval-s{seed}'
    inputs=folder/f'robustness-s{seed}'
    subprocess.run([sys.executable,str(pipeline/'scripts/prepare-candidate-evaluation.py'),
        str(records),str(inputs),campaign,str(seed)],check=True)
    for model in ('esmfold2','boltz'):
        task_path=inputs/f'{model}-task.json'; task=json.loads(task_path.read_text())
        task['timeout_seconds']=280
        write_json(task_path,task)
        tasks.append({'seed':seed,'model':model,'campaign':campaign,'task':str(task_path)})
write_json(plan_path,{'candidate_id':candidate['candidate_id'],'candidate_records_sha256':digest(records),
    'baseline_seed':0,'additional_seeds':[1,2],'tasks':tasks,'submission_eligible':False,
    'policy':'same sequence, target, MSA and model settings; vary prediction seed only; preserve every outcome'})
print(json.dumps({'status':'prepared','tasks':tasks},indent=2))
