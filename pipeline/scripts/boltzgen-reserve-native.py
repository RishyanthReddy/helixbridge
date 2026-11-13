"""Run one pinned, native BoltzGen task without the full CLI pipeline's downloads."""
import json
import os
from pathlib import Path
import random
import resource
import sys
import time

import numpy as np
import torch
from omegaconf import OmegaConf
from boltzgen.resources.main import main

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest, write_json

root = Path(os.environ['TASK_ROOT'])
folder = root / 'results/boltzgen-reserve-v1'
source = root / 'src/BoltzGen'
phase = sys.argv[1]
if phase not in ('design', 'inverse_fold_solublempnn'):
    raise ValueError('Only the two reviewed native tasks are allowed')
audit = json.loads((folder / 'input-v1/input-audit.json').read_text())
assets = json.loads((folder / 'assets.json').read_text())
asset_paths = {item['name']: item['path'] for item in assets['files']}
if audit['status'] != 'passed_cpu_parser':
    raise ValueError('CPU input gate did not pass')
for name, expected in [('target.pdb', audit['target_pdb_sha256']), ('design.yaml', audit['design_yaml_sha256'])]:
    if digest(folder / 'input-v1' / name) != expected:
        raise ValueError('Input changed after parser check')
if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
    raise ValueError('Exactly one allocated GPU is required')
if 'L40S' not in torch.cuda.get_device_name(0):
    raise ValueError('This qualification is bounded to the allocated L40S')
random.seed(301)
np.random.seed(301)
torch.manual_seed(301)
torch.cuda.manual_seed_all(301)
config = source / f'src/boltzgen/resources/config/{phase}.yaml'
design = folder / 'native-v1/intermediate_designs'
output = design if phase == 'design' else folder / 'native-v1/intermediate_designs_inverse_folded'
if output.exists():
    raise ValueError('Use fresh native output; do not overwrite a failed attempt')
common = [f'output={output}', 'trainer.devices=1', f'data.cfg.moldir={asset_paths["mols.zip"]}',
          'data.cfg.multiplicity=1']
if phase == 'design':
    args = common + [f'data.cfg.yaml_path=[{folder / "input-v1/design.yaml"}]', 'data.num_workers=0',
                     'data.cfg.skip_existing=false', 'diffusion_samples=1', 'override.use_kernels=false',
                     f'checkpoint={asset_paths["boltzgen1_adherence.ckpt"]}']
else:
    if len(list(design.glob('*.cif'))) != 1:
        raise ValueError('One generated backbone is required')
    args = common + [f'data.design_dir={design}', 'data.cfg.num_workers=0', 'data.skip_existing=false',
                     f'checkpoint={asset_paths["solublempnn_v_48_020.pt"]}']
resolved = OmegaConf.merge(OmegaConf.load(config), OmegaConf.from_dotlist(args))
metadata = folder / f'native-v1/{phase}-resolved.yaml'
metadata.parent.mkdir(parents=True, exist_ok=True)
OmegaConf.save(resolved, metadata, resolve=True)
started = time.time()
torch.cuda.reset_peak_memory_stats()
main(str(config), args)
torch.cuda.synchronize()
cifs = list(output.glob('*.cif'))
if len(cifs) != 1 or len(list(output.glob('*.npz'))) != 1:
    raise ValueError('Expected exactly one native CIF and metadata NPZ')
write_json(folder / f'native-v1/{phase}-audit.json', {
    'phase': phase, 'seed': 301, 'device': torch.cuda.get_device_name(0), 'torch': torch.__version__,
    'source_revision': assets['source_revision'], 'assets_sha256': digest(folder / 'assets.json'),
    'input_audit_sha256': digest(folder / 'input-v1/input-audit.json'),
    'config_source_sha256': digest(config), 'resolved_config_sha256': digest(metadata),
    'script_sha256': digest(__file__), 'elapsed_seconds': time.time() - started,
    'peak_reserved_mib': torch.cuda.max_memory_reserved() / 2**20,
    'host_peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    'artifacts': {str(p.relative_to(folder)): digest(p) for p in output.iterdir() if p.is_file()},
    'submission_eligible': False,
})
