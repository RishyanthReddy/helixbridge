"""Freeze the 12-seed rehearsal recipe only after the preceding review gates."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest,write_json

root=Path(os.environ['TASK_ROOT']); pipeline=root/'src/pipeline'
folder=root/'results/robust-localfold-campaign-v1'
plan_path=folder/'campaign-plan.json'
if plan_path.exists():raise ValueError('Campaign was already predeclared')
qualification_path=folder/'localfold-qualification-decision.json'
qualification=json.loads(qualification_path.read_text())
if qualification['status']!='assessed' or qualification['submission_eligible'] is not False:
    raise ValueError('LocalFold diagnostic review must precede the campaign')
reviews=[]
for seed in (1,2):
    path=root/f'results/rfd4-il7ra-high-s43-eval-s{seed}-review-v1/review.json'
    row=json.loads(path.read_text())
    if row['candidate_id']!='il7ra-rfd4-2ced05176b85' or row['submission_eligible']:
        raise ValueError('Wrong robustness review')
    reviews.append({'path':str(path),'sha256':digest(path)})
reference=pipeline/'data/targets/il7ra/rfd4-reference'
plan={'status':'predeclared_rehearsal_only','design_seeds':list(range(101,113)),
    'prediction_seed':0,'length':60,'recycle_strategy':'thinking_high',
    'reference_files_sha256':{name:digest(reference/name) for name in ['audit.json','target.cif','conditions.json']},
    'robustness_reviews':reviews,'localfold_decision_sha256':digest(qualification_path),
    'gpu_seconds_cap_for_whole_goal':5400,'max_concurrent_gpus':2,'submission_eligible':False,
    'selection_policy':'Retain all outcomes; review raw directional confidence, pose agreement, close contacts, sequence and contact-site diversity; no calibrated binding cutoff or weighted consensus.',
    'scope':'Twelve seed-diverse designs on the same reviewed reference/hotspots. No new epitope recipe, known-positive binder, or experimental binding claim.'}
write_json(plan_path,plan)
for seed in plan['design_seeds']:
    campaign=f'rfd4-il7ra-campaign-s{seed}'; result=root/f'results/{campaign}-v1'; review=root/f'results/{campaign}-review-v1'
    task={'cwd':str(pipeline),'revision':'bounded RFD4 generation→ESMFold2→Boltz→independent geometry/context review',
        'command':[str(root/'env/rfd4/bin/python'),'scripts/run-controlled-design.py',str(seed)],'timeout_seconds':400,
        'inputs':[str(plan_path),str(qualification_path)]+
          [str(pipeline/'scripts'/name) for name in ['run-controlled-design.py','rfd4-il7ra-seed.py',
            'prepare-candidate-evaluation.py','esmfold2-predict.py','boltz-predict.py','review-rehearsal.py',
            'audit-pose-fit.py','audit-il7ra-target-context.py']]+[str(pipeline/'slurm/run-stage.sbatch')],
        'outputs':[{'path':str(review/name),'kind':'file'} for name in
          ['review.json','independent-pose-audit.json','target-context-audit.json','starting-input-audit.json','REHEARSAL_ONLY.csv','export-audit.json']],
        'state':str(result/'campaign-task-state.json'),'log':str(result/'campaign.log')}
    write_json(folder/f'campaign-tasks/s{seed}.json',task)
print('Predeclared seeds 101–112 and twelve bounded generation-to-review tasks')
