"""CPU review after staged predictions; copy verified ESM artifacts to common layout."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest,write_json
root=Path(os.environ['TASK_ROOT']);pipeline=root/'src/pipeline';folder=root/'results/site-diversity-pilot-v1'
batch=sys.argv[1];stage=folder/'staging'/batch
plan=json.loads((stage/'batch-plan.json').read_text());state=json.loads((stage/'task-state.json').read_text())
if state['status']!='success' or state['exit_code']!=0:raise ValueError('ESM batch did not complete')
for item in plan['cases']:
    case=item['case'];campaign='site-'+case;records=root/f'results/{campaign}-v1/candidates.json'
    source=stage/f'predictions-v1/seed-{case}/prediction'
    target=root/f'results/{campaign}-esmfold2-v1/prediction'
    if target.exists():raise ValueError('Common ESM layout already exists')
    expected=state['outputs'][str(source/'metrics.json')]
    if digest(source/'metrics.json')!=expected:raise ValueError('Staged prediction changed')
    shutil.copytree(source,target)
    write_json(target.parent/'staged-source.json',{'batch_state_sha256':digest(stage/'task-state.json'),
        'source_directory':str(source),'files':{p.name:digest(p) for p in sorted(target.iterdir()) if p.is_file()}})
    review=root/f'results/{campaign}-review-v1'
    subprocess.run([str(root/'env/rfd4/bin/python'),'scripts/review-rehearsal.py',str(review),str(records),campaign],check=True)
    for script in ('audit-pose-fit.py','audit-site-target-context.py'):
        subprocess.run([str(root/'env/boltz/bin/python'),'scripts/'+script,campaign,str(records)],check=True)
    shutil.copyfile(records.parent/'starting-input-audit.json',review/'starting-input-audit.json')
write_json(folder/f'{batch}-review-complete.json',{'status':'complete','cases':plan['cases'],'submission_eligible':False})
