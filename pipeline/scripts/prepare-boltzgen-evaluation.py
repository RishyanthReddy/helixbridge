"""Prepare a one-case staged ESM refold using the qualified immutable runtime."""
import json
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest, write_json

root = Path(os.environ['TASK_ROOT'])
pipeline = root / 'src/pipeline'
folder = root / 'results/boltzgen-reserve-v1'
records = root / 'results/boltzgen-il7ra-p139-v1/candidates.json'
row = json.loads(records.read_text())['candidates'][0]
request = records.parent / 'evaluation-input/input.json'
if row['generator'] != 'BoltzGen+SolubleMPNN' or row['qc_reasons']:
    raise ValueError('Require the single, format-valid reserve import')
stage = folder / 'staging/reserve'
if stage.exists():
    raise ValueError('One fresh staged evaluation only')
stage.mkdir(parents=True)
original = root / 'results/esm-startup-recovery-v1'
inputs = [str(records), str(request)]
for name in ('preparation.json', 'environment-archive.json', 'checkpoint-archive.json'):
    shutil.copyfile(original / name, stage / name)
    inputs.append(str(stage / name))
(stage / 'cpu-qualification-v1').mkdir()
shutil.copyfile(original / 'cpu-qualification-v1/staging-state.json', stage / 'cpu-qualification-v1/staging-state.json')
inputs.append(str(stage / 'cpu-qualification-v1/staging-state.json'))
write_json(stage / 'batch-plan.json', {'cases': [{'case': 'p139-s301', 'candidate_id': row['candidate_id'],
           'input': str(request), 'input_sha256': digest(request), 'records_sha256': digest(records)}],
           'prediction_seed': 0, 'submission_eligible': False})
inputs.append(str(stage / 'batch-plan.json'))
inputs.extend(str(pipeline / n) for n in ('scripts/boltzgen-stage-esm.py', 'scripts/esmfold2-predict.py',
              'scripts/probe-esm-runtime.py', 'binder_campaign/staging.py', 'slurm/run-stage.sbatch'))
prediction = stage / 'predictions-v1/seed-p139-s301/prediction'
task = {'cwd': str(pipeline), 'revision': 'One reserve refold; unchanged pinned ESM adapter and staged runtime',
        'command': [str(root / 'env/rfd4/bin/python'), 'scripts/boltzgen-stage-esm.py', 'predict', 'reserve'],
        'timeout_seconds': 340, 'inputs': inputs,
        'outputs': [{'path': str(stage / 'predictions-v1/staging-state.json'), 'kind': 'json'},
                    {'path': str(prediction / 'metrics.json'), 'kind': 'metrics_json', 'finite_keys': ['iptm', 'ptm']}] +
                   [{'path': str(prediction / n), 'kind': 'file'} for n in ('model.cif', 'pae.json', 'raw.npz', 'model_10_10.txt')],
        'state': str(stage / 'task-state.json'), 'log': str(stage / 'task.log')}
write_json(folder / 'esm-task.json', task)
print('Prepared one ESM reserve refold', flush=True)
