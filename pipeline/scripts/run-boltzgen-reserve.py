"""A single native design and soluble sequence, with separately recorded limits."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import run_task, write_json

root = Path(os.environ['TASK_ROOT'])
pipeline = root / 'src/pipeline'
folder = root / 'results/boltzgen-reserve-v1'
for phase, limit in [('design', 400), ('inverse_fold_solublempnn', 180)]:
    task = {'cwd': str(pipeline), 'revision': 'Pinned native BoltzGen reserve, one IL7Ra patch139 case',
            'command': [str(root / 'env/boltzgen/bin/python'), 'scripts/boltzgen-reserve-native.py', phase],
            'timeout_seconds': limit,
            'inputs': [str(folder / 'assets.json'), str(folder / 'input-v1/input-audit.json'),
                       str(pipeline / 'scripts/boltzgen-reserve-native.py'), str(root / 'env/boltzgen-freeze.txt')],
            'outputs': [{'path': str(folder / f'native-v1/{phase}-audit.json'), 'kind': 'json'}],
            'state': str(folder / f'{phase}-state.json'), 'log': str(folder / f'{phase}.log')}
    path = folder / f'{phase}-task.json'
    write_json(path, task)
    run_task(path)
print('Native design and inverse folding completed', flush=True)
