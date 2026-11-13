"""Include node-configuration time in the recovery's one-job GPU budget."""
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import write_json

root = Path(os.environ['TASK_ROOT'])
folder = root / 'results/esm-startup-recovery-v1'
job = os.environ['SLURM_JOB_ID']
details = subprocess.check_output(['scontrol', 'show', 'job', '-o', job], text=True)
match = re.search(r'(?:^|\s)StartTime=(\S+)', details)
if not match or match.group(1) == 'Unknown':
    raise ValueError('Cannot establish allocated GPU start time')
allocated_start = datetime.fromisoformat(match.group(1)).timestamp()
elapsed_at_start = time.time() - allocated_start
if elapsed_at_start < -5:
    raise ValueError('Scheduler/local time interpretation disagrees')
remaining = 900 - max(0, elapsed_at_start) - 20
state = {'job_id': job, 'allocated_start': match.group(1), 'gpu_seconds_cap': 900,
         'remaining_seconds_at_guard_start': remaining, 'status': 'running'}
write_json(folder / 'budget-guard.json', state)
if remaining < 100:
    state['status'] = 'refused_insufficient_time'
    write_json(folder / 'budget-guard.json', state)
    raise ValueError('Node configuration left insufficient bounded GPU time')
command = [sys.executable, str(Path(__file__).with_name('stage-esm-runtime.py')), 'predict']
process = subprocess.Popen(command)
try:
    code = process.wait(timeout=min(570, remaining))
    state.update(status='success' if code == 0 else 'failed', exit_code=code)
except subprocess.TimeoutExpired:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    state.update(status='stopped_at_budget_guard', exit_code=124)
    code = 124
finally:
    state['allocated_seconds_at_exit'] = time.time() - allocated_start
    write_json(folder / 'budget-guard.json', state)
sys.exit(code)
