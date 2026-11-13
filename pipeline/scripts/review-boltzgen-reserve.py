"""Verify staged outputs and run the existing common and independent reviews."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest, write_json

root = Path(os.environ['TASK_ROOT'])
folder = root / 'results/boltzgen-reserve-v1'
stage = folder / 'staging/reserve'
state_path = stage / 'task-state.json'
state = json.loads(state_path.read_text())
if state['status'] != 'success' or state['exit_code'] != 0:
    raise ValueError('ESM must complete before review')
source = stage / 'predictions-v1/seed-p139-s301/prediction'
target = root / 'results/boltzgen-il7ra-p139-esmfold2-v1/prediction'
if target.exists():
    raise ValueError('Common ESM layout already exists')
for path in source.iterdir():
    expected = state['outputs'].get(str(path))
    if expected and digest(path) != expected:
        raise ValueError('Staged artifact changed')
metrics = json.loads((source / 'metrics.json').read_text())
for name, expected in metrics['artifacts'].items():
    if digest(source / name) != expected:
        raise ValueError('Model artifact changed')
shutil.copytree(source, target)
write_json(target.parent / 'staged-source.json', {'batch_state_sha256': digest(state_path),
           'source_directory': str(source), 'files': {p.name: digest(p) for p in sorted(target.iterdir()) if p.is_file()}})
records = root / 'results/boltzgen-il7ra-p139-v1/candidates.json'
review = root / 'results/boltzgen-il7ra-p139-review-v1'
subprocess.run([str(root / 'env/rfd4/bin/python'), 'scripts/review-rehearsal.py', str(review),
                str(records), 'boltzgen-il7ra-p139'], check=True)
for script in ('audit-pose-fit.py', 'audit-boltzgen-target-context.py'):
    subprocess.run([str(root / 'env/boltz/bin/python'), 'scripts/' + script, 'boltzgen-il7ra-p139', str(records)], check=True)
write_json(folder / 'review-complete.json', {'status': 'complete', 'review': str(review),
           'related_model_warning': 'Boltz refold and BoltzGen generator share model lineage; retain ESM evidence separately',
           'generator_geometry_scope': 'Binder backbone only; no packed generator sidechains',
           'submission_eligible': False})
