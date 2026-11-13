"""Freeze four seed-only refolds and a separate 20-minute GPU ledger."""
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest, write_json

root = Path(os.environ['TASK_ROOT'])
pipeline = root / 'src/pipeline'
records = root / 'results/rfd4-il7ra-campaign-s101-v1/candidates.json'
baseline_path = records.parent / 'evaluation-input/input.json'
candidate = json.loads(records.read_text())['candidates'][0]
baseline = json.loads(baseline_path.read_text())
if candidate['candidate_id'] != 'il7ra-rfd4-6b3ca40a31bb' or candidate['submission_eligible']:
    raise ValueError('Unexpected validation candidate')
if baseline['candidate_records_sha256'] != digest(records) or baseline['settings']['seed'] != 0:
    raise ValueError('Baseline candidate or seed differs')
folder = root / 'results/lead101-validation-v1'
if folder.exists():
    raise ValueError('Use a fresh checkpoint directory')
folder.mkdir()
tasks = []
for seed in (1, 2):
    campaign = f'rfd4-il7ra-s101-eval-s{seed}'
    inputs = folder / f'prediction-seed-{seed}'
    subprocess.run([sys.executable, str(pipeline / 'scripts/prepare-candidate-evaluation.py'),
                    str(records), str(inputs), campaign, str(seed)], check=True)
    request = json.loads((inputs / 'input.json').read_text())
    for key in ('target', 'partner', 'construct_status', 'protocol_status'):
        if request[key] != baseline[key]:
            raise ValueError('Baseline changed: ' + key)
    if {k: v for k, v in request['settings'].items() if k != 'seed'} != \
            {k: v for k, v in baseline['settings'].items() if k != 'seed'}:
        raise ValueError('Non-seed settings differ')
    for model in ('esmfold2', 'boltz'):
        task_path = inputs / f'{model}-task.json'
        task = json.loads(task_path.read_text())
        task['timeout_seconds'] = 280
        write_json(task_path, task)
        tasks.append({'seed': seed, 'model': model, 'campaign': campaign,
                      'task': str(task_path), 'task_sha256': digest(task_path)})
write_json(folder / 'plan.json', {
    'candidate_id': candidate['candidate_id'], 'candidate_records_sha256': digest(records),
    'baseline_input_sha256': digest(baseline_path), 'baseline_seed': 0,
    'additional_seeds': [1, 2], 'tasks': tasks, 'submission_eligible': False,
    'policy': 'Vary prediction seed only; preserve every outcome; no model or generation change'})
write_json(folder / 'gpu-budget.json', {
    'gpu_seconds_cap': 1200, 'max_concurrent_gpus': 2, 'jobs': [],
    'scope': 'Four seed101 robustness predictions only; no generation; research only'})
print(json.dumps({'status': 'prepared', 'tasks': tasks}, indent=2))
