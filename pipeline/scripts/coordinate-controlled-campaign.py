"""Fill at most two budget-admitted slots after the first two cases are verified."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from binder_campaign.budget import TERMINAL
from binder_campaign.runner import write_json
root=Path(os.environ['TASK_ROOT']);pipeline=root/'src/pipeline'
folder=root/'results/robust-localfold-campaign-v1'
state_path=folder/'controller-state.json'
if state_path.exists():raise ValueError('Inspect existing coordinator state before restarting')
plan=json.loads((folder/'campaign-plan.json').read_text())
for seed in (101,102):
    state=json.loads((root/f'results/rfd4-il7ra-campaign-s{seed}-v1/campaign-task-state.json').read_text())
    if state['status']!='success' or state['exit_code']!=0:raise ValueError('First-wave implementation gate failed')
while True:
    ledger=json.loads((folder/'gpu-budget.json').read_text())
    ids=','.join(row['job_id'] for row in ledger['jobs'])
    text=subprocess.check_output(['sacct','-X','-n','-P','-j',ids,'--format=JobIDRaw,State,ElapsedRaw'],text=True)
    observed={}
    for line in text.splitlines():
        if line.strip():
            job,state,elapsed=line.split('|');observed[job]={'state':state.split()[0].rstrip('+'),'elapsed_seconds':int(elapsed)}
    if set(observed)!={row['job_id'] for row in ledger['jobs']}:
        write_json(state_path,{'status':'waiting_for_accounting','observed':observed,'updated_unix':time.time()})
        time.sleep(15);continue
    active=[job for job,value in observed.items() if value['state'] not in TERMINAL]
    used=sum(row['elapsed_seconds'] for row in observed.values())
    tasks={int(Path(row['task']).stem[1:]):row for row in ledger['jobs'] if '/campaign-tasks/s' in row['task']}
    pending=[seed for seed in plan['design_seeds'] if seed not in tasks]
    failures=[]
    for seed,row in tasks.items():
        if observed[row['job_id']]['state'] in TERMINAL and observed[row['job_id']]['state']!='COMPLETED':
            failures.append({'seed':seed,'job_id':row['job_id'],'state':observed[row['job_id']]['state']})
    status={'status':'running','used_gpu_seconds':used,'active_job_ids':active,
            'submitted_designs':sorted(tasks),'not_submitted_seeds':pending,'failures':failures,'updated_unix':time.time()}
    if len(failures)>=2:
        status['status']='stopped_for_failure_review';write_json(state_path,status);break
    if not pending and not active:
        status['status']='complete';write_json(state_path,status);break
    write_json(state_path,status)
    if pending and len(active)<2:
        seed=pending[0]
        command=[sys.executable,str(pipeline/'scripts/submit-budgeted.py'),str(folder/f'campaign-tasks/s{seed}.json'),
                 '--minutes','7','--name',f'cj-rfd4-s{seed}']
        attempt=subprocess.run(command,text=True,capture_output=True)
        print(attempt.stdout,flush=True)
        if attempt.returncode:
            if 'GPU budget cannot cover' in attempt.stderr:
                status['status']='budget_exhausted_before_next_hard_limit'
                status['admission_error']=attempt.stderr;write_json(state_path,status);break
            raise RuntimeError('Budgeted submission failed: '+attempt.stderr)
        time.sleep(2)
    else:
        time.sleep(15)
print(json.dumps(json.loads(state_path.read_text()),indent=2),flush=True)
