"""CPU-only preparation of unchanged ESMFold2 runtime and checkpoint archives."""
import json
import os
from pathlib import Path
import sys
import tarfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest, write_json
from binder_campaign.staging import tree_members

root = Path(os.environ['TASK_ROOT'])
out = root / 'results/esm-startup-recovery-v1'
if out.exists():
    raise ValueError('Use a fresh preparation directory')
out.mkdir()
started = time.monotonic()
env = root / 'env/esmfold2'
site = env / 'lib/python3.12/site-packages'
checkpoints_path = root / 'env/esmfold2-checkpoints.json'
checkpoints = json.loads(checkpoints_path.read_text())
if len(checkpoints) != 1 or checkpoints[0]['revision'] != '69869f737beffec5294845ede23db5fc0b4f509e':
    raise ValueError('Unexpected checkpoint')
for path in site.glob('*.pth'):
    for line in path.read_text().splitlines():
        if line.strip() and not line.startswith(('#', 'import ')) and (site / line).resolve().is_absolute():
            (site / line).resolve().relative_to(site.resolve())
members = tree_members(site)
print('Hashed environment members', len(members), flush=True)
archive = out / 'site-packages.tar'
with tarfile.open(archive, 'w', dereference=False) as package:
    for name in members:
        package.add(site / name, arcname=name, recursive=False)
environment = {'path': str(archive), 'sha256': digest(archive), 'bytes': archive.stat().st_size,
               'members': members, 'source_root': str(site), 'pyvenv_cfg': (env / 'pyvenv.cfg').read_text()}
write_json(out / 'environment-archive.json', environment)
print('Prepared environment archive', archive.stat().st_size, flush=True)
model = checkpoints[0]
members = {}
archive = out / 'checkpoint.tar'
with tarfile.open(archive, 'w', dereference=True) as package:
    for name, expected in model['files'].items():
        path = Path(model['path']) / name
        if path.stat().st_size != expected['bytes'] or digest(path) != expected['sha256']:
            raise ValueError('Pinned model file changed: ' + name)
        members[name] = {'type': 'file', **expected}
        package.add(path, arcname=name, recursive=False)
        print('Archived pinned model file', name, flush=True)
weights = {'path': str(archive), 'sha256': digest(archive), 'bytes': archive.stat().st_size,
           'members': members, 'repo': model['repo'], 'revision': model['revision']}
write_json(out / 'checkpoint-archive.json', weights)
small = ['scripts/esmfold2-predict.py', 'binder_campaign/__init__.py',
         'binder_campaign/runner.py', 'binder_campaign/structure.py',
         'data/targets/il7ra/msa/target.a3m']
sources = {str(root / 'src/pipeline' / name): digest(root / 'src/pipeline' / name) for name in small}
sources.update({str(checkpoints_path): digest(checkpoints_path),
                str(root / 'src/IPSAE/ipsae.py'): digest(root / 'src/IPSAE/ipsae.py'),
                str(root / 'env/esmfold2-freeze.txt'): digest(root / 'env/esmfold2-freeze.txt')})
write_json(out / 'preparation.json', {'status': 'prepared_cpu_only',
    'environment_descriptor_sha256': digest(out / 'environment-archive.json'),
    'checkpoint_descriptor_sha256': digest(out / 'checkpoint-archive.json'),
    'source_sha256': sources, 'python_realpath': str((env / 'bin/python').resolve()),
    'python_sha256': digest((env / 'bin/python').resolve()), 'python_version': sys.version,
    'script_sha256': digest(__file__), 'elapsed_seconds': time.monotonic() - started,
    'submission_eligible': False})
print('CPU archive preparation complete', flush=True)
