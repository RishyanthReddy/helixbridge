"""Preserve original tasks and shorten only the two unsubmitted seed-2 tasks."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest, write_json

root = Path(os.environ['TASK_ROOT'])
folder = root / 'results/lead101-validation-v1'
plan_path = folder / 'plan.json'
plan = json.loads(plan_path.read_text())
ledger = json.loads((folder / 'gpu-budget.json').read_text())
if len(ledger['jobs']) != 2 or any('prediction-seed-2' in r['task'] for r in ledger['jobs']):
    raise ValueError('Limit amendment applies only before either seed-2 submission')
amendment = folder / 'seed2-limit-amendment.json'
if amendment.exists():
    raise ValueError('Limit amendment already exists')
tasks = []
for row in plan['tasks']:
    if row['seed'] != 2:
        continue
    original = Path(row['task'])
    if digest(original) != row['task_sha256']:
        raise ValueError('Original task changed')
    task = json.loads(original.read_text())
    task['timeout_seconds'] = 220
    shortened = original.with_name(original.stem + '-bounded.json')
    if shortened.exists():
        raise ValueError('Bounded task already exists')
    write_json(shortened, task)
    tasks.append({**row, 'original_task_sha256': row['task_sha256'],
                  'task': str(shortened), 'task_sha256': digest(shortened), 'slurm_minutes': 4})
write_json(amendment, {'plan_sha256': digest(plan_path), 'tasks': tasks,
    'reason': 'Slow cold-node startup consumed allocation time; shorten remaining hard limits to preserve 1200-second total cap',
    'scientific_inputs_changed': False, 'submission_eligible': False})
print(json.dumps({'status': 'shortened_unsubmitted_tasks_only', 'tasks': tasks}, indent=2))
