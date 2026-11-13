"""Freeze a single, sequential two-seed recovery task after CPU qualification."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest, write_json

root = Path(os.environ['TASK_ROOT'])
pipeline = root / 'src/pipeline'
folder = root / 'results/esm-startup-recovery-v1'
qualification = folder / 'cpu-qualification-v1/staging-state.json'
state = json.loads(qualification.read_text())
if state['status'] != 'success' or state['preparation_sha256'] != digest(folder / 'preparation.json'):
    raise ValueError('Require matching successful CPU staging qualification')
if (folder / 'task.json').exists() or (folder / 'gpu-budget.json').exists():
    raise ValueError('Recovery task/budget already exists')
baseline = json.loads((root / 'results/rfd4-il7ra-campaign-s101-v1/evaluation-input/input.json').read_text())
requests = [root / f'results/lead101-validation-v1/prediction-seed-{seed}/input.json' for seed in (1, 2)]
for seed, path in zip((1, 2), requests):
    expected = {**baseline, 'settings': {**baseline['settings'], 'seed': seed}}
    if json.loads(path.read_text()) != expected:
        raise ValueError('A non-seed scientific input differs')
inputs = [folder / name for name in ('preparation.json', 'environment-archive.json', 'checkpoint-archive.json')]
inputs += [qualification, *requests, root / 'results/rfd4-il7ra-campaign-s101-v1/candidates.json',
           root / 'env/esmfold2-checkpoints.json', root / 'env/esmfold2-freeze.txt',
           root / 'src/IPSAE/ipsae.py']
inputs += [pipeline / name for name in ('scripts/stage-esm-runtime.py', 'scripts/guard-esm-recovery.py', 'scripts/probe-esm-runtime.py',
            'scripts/esmfold2-predict.py', 'binder_campaign/staging.py', 'binder_campaign/runner.py',
            'binder_campaign/structure.py', 'slurm/run-stage.sbatch', 'data/targets/il7ra/msa/target.a3m')]
result = folder / 'predictions-v1'
outputs = [{'path': str(result / name), 'kind': 'json'} for name in
           ('staging-state.json', 'original-checkpoints.json', 'runtime-checkpoints.json')]
outputs.append({'path': str(folder / 'budget-guard.json'), 'kind': 'json'})
for seed in (1, 2):
    pred = result / f'seed-{seed}/prediction'
    outputs += [{'path': str(pred / 'metrics.json'), 'kind': 'metrics_json',
                 'finite_keys': ['iptm', 'ptm', 'peak_reserved_mib', 'host_peak_rss_mib']}]
    outputs += [{'path': str(pred / name), 'kind': 'file'} for name in ('model.cif', 'pae.json', 'raw.npz', 'model_10_10.txt')]
task = {'cwd': str(pipeline), 'revision': 'Pinned unchanged ESMFold2 adapter; node-local I/O only; two fresh processes',
        'command': [str(root / 'env/rfd4/bin/python'), 'scripts/guard-esm-recovery.py'],
        'timeout_seconds': 580, 'inputs': [str(p) for p in inputs], 'outputs': outputs,
        'state': str(folder / 'task-state.json'), 'log': str(folder / 'task.log')}
write_json(folder / 'task.json', task)
write_json(folder / 'gpu-budget.json', {'gpu_seconds_cap': 900, 'max_concurrent_gpus': 1,
    'jobs': [], 'scope': 'Recover only seed101 ESMFold2 prediction seeds1/2; no new generation; staged I/O'})
write_json(folder / 'recovery-plan.json', {'task_sha256': digest(folder / 'task.json'),
    'prediction_seeds': [1, 2], 'candidate_id': baseline['candidate_id'],
    'cpu_qualification_sha256': digest(qualification), 'request_sha256': {str(p): digest(p) for p in requests},
    'scientific_changes': False, 'fresh_process_per_seed': True, 'slurm_minutes': 10,
    'submission_eligible': False, 'policy': 'One sequential allocation; do not retry beyond 900 total GPU seconds'})
print(json.dumps({'status': 'prepared', 'task': str(folder / 'task.json'), 'slurm_minutes': 10}))
