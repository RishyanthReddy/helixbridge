"""Record intent and admit a single-GPU task only within the authorized budget."""
import argparse
from datetime import datetime
import fcntl
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from binder_campaign.budget import admission, TERMINAL
from binder_campaign.runner import digest,write_json

parser=argparse.ArgumentParser()
parser.add_argument('task',type=Path)
parser.add_argument('--minutes',type=int,default=5)
parser.add_argument('--name',required=True)
parser.add_argument('--ledger',type=Path,
    help='Existing bounded ledger under TASK_ROOT/results; default retains the original campaign')
args=parser.parse_args()
if not 1<=args.minutes<=15 or not re.fullmatch(r'cj-[a-z0-9-]+',args.name):
    raise ValueError('Invalid bounded job limit or name')
root=Path(os.environ['TASK_ROOT']); pipeline=root/'src/pipeline'
ledger_path=(args.ledger.resolve() if args.ledger else root/'results/robust-localfold-campaign-v1/gpu-budget.json')
if args.ledger:
    ledger_path.relative_to((root/'results').resolve())
    if not ledger_path.is_file():
        raise ValueError('An explicit ledger must already exist')
folder=ledger_path.parent; folder.mkdir(exist_ok=True)
with (folder/'gpu-budget.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else {
        'gpu_seconds_cap':5400,'max_concurrent_gpus':2,'jobs':[],
        'scope':'seed43 robustness, LocalFold qualification and up to12 RFD4 designs; rehearsal only'}
    if type(ledger['gpu_seconds_cap']) is not int or not 0<ledger['gpu_seconds_cap']<=5400 \
            or type(ledger['max_concurrent_gpus']) is not int or not 0<ledger['max_concurrent_gpus']<=2:
        raise ValueError('Ledger exceeds the supported bounded resource envelope')
    observed={}
    if ledger['jobs']:
        ids=','.join(row['job_id'] for row in ledger['jobs'])
        output=subprocess.check_output(['sacct','-X','-n','-P','-j',ids,
            '--format=JobIDRaw,State,ElapsedRaw,AllocTRES'],text=True)
        for line in output.splitlines():
            if not line.strip(): continue
            job,state,elapsed,tres=line.split('|')
            if job not in {row['job_id'] for row in ledger['jobs']} or job in observed:
                raise ValueError('Ambiguous scheduler job rows')
            if tres and 'gres/gpu=1' not in tres:
                raise ValueError('Expected a one-GPU allocation')
            observed[job]={'state':state,'elapsed_seconds':int(elapsed)}
        missing={row['job_id'] for row in ledger['jobs']}-set(observed)
        if missing:
            # sacct can lag a newly accepted job. For a job still in squeue,
            # reserve its ENTIRE hard limit until accounting catches up.
            queue=subprocess.check_output(['squeue','-h','-j',','.join(sorted(missing)),
                                           '-o','%i|%T'],text=True)
            for line in queue.splitlines():
                job,state=line.strip().split('|')
                if job in missing:
                    observed[job]={'state':state,'elapsed_seconds':0,
                                   'accounting':'squeue fallback; full hard limit reserved'}
        for row in ledger['jobs']:
            observation=observed.get(row['job_id'])
            if observation and observation['state'].split()[0].rstrip('+') not in TERMINAL:
                details=subprocess.check_output(['scontrol','show','job','-o',row['job_id']],text=True)
                end=re.search(r'(?:^|\s)EndTime=(\S+)',details)
                # Slurm can extend EndTime by time spent configuring the node.
                # SACCT elapsed may include that time, so limit-elapsed alone can
                # under-reserve a running allocation. Keep the larger estimate.
                remaining=row['limit_seconds']
                if end and end.group(1) not in {'Unknown','N/A','None'}:
                    remaining=max(0,math.ceil(datetime.fromisoformat(end.group(1)).timestamp()-time.time()))
                observation['remaining_seconds']=remaining
    budget=admission(ledger,observed,args.minutes*60)
    task=args.task.resolve(); spec=json.loads(task.read_text())
    if spec['timeout_seconds']>args.minutes*60-20:
        raise ValueError('Task timeout must fit inside the job hard limit')
    intent={'task':str(task),'task_sha256':digest(task),'limit_seconds':args.minutes*60,
            'job_name':args.name,'submitted_unix':time.time()}
    ledger['unresolved_submission']=intent
    write_json(ledger_path,ledger)
    job=subprocess.check_output(['sbatch','--parsable',f'--job-name={args.name}',
         f'--time=00:{args.minutes:02d}:00','--signal=B:TERM@15',
         str(pipeline/'slurm/run-stage.sbatch'),str(task)],text=True).strip()
    if not re.fullmatch(r'[0-9]+',job):
        raise ValueError('Unresolved scheduler submission reply: '+job)
    ledger['jobs'].append({**intent,'job_id':job})
    ledger['unresolved_submission']=None
    ledger['last_admission_observations']=observed
    write_json(ledger_path,ledger)
    print(json.dumps({'job_id':job,'budget_before_submission':budget,'hard_limit_seconds':args.minutes*60}))
