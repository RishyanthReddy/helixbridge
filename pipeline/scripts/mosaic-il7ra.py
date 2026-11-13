"""One smoke test or one bounded full-target Mosaic IL-7Rα rehearsal."""
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest, write_json

parser = argparse.ArgumentParser()
parser.add_argument('--mode', choices=['smoke', 'design'], required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root = Path(os.environ['TASK_ROOT'])
out = args.output
if out.exists():
    raise ValueError('Use a fresh result directory')
out.mkdir(parents=True)
started = time.monotonic()
revisions = {
    'mosaic-runtime': '5937f37164bcb28bc6f1000f10134145438e5971',
    'joltz': 'ed0f04257dac85bd4b7bf45521cc280f86d38ded',
    'mosaic-boltz': '7ea718a1440ecbe8e2418317192b501544147edd',
}
for name, expected in revisions.items():
    source = root / 'src' / name
    actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=no'], text=True)
    if actual != expected or dirty:
        raise ValueError('Unreviewed source revision or modifications: ' + name)

import equinox as eqx
import jax
import jax.numpy as jnp
import numpy as np
from mosaic.common import TOKENS
from mosaic.models.boltz2 import Boltz2
from mosaic.losses.boltz2 import load_features_and_structure_writer
import mosaic.losses.structure_prediction as sp
from mosaic.losses.protein_mpnn import InverseFoldingSequenceRecovery
from mosaic.proteinmpnn.mpnn import load_mpnn_sol
from mosaic.optimizers import simplex_APGM

if len(jax.devices()) != 1 or jax.devices()[0].platform != 'gpu':
    raise RuntimeError('Exactly one allocated GPU is required')
target_path = root / 'src/pipeline/data/targets/il7ra/manifest.json'
target = json.loads(target_path.read_text())
msa_path = root / 'src/pipeline/data/targets/il7ra/msa/target.a3m'
# First 128 target-only A3M records, preserving insertion notation and order.
entries = []
for line in msa_path.read_text().splitlines():
    if line.startswith('>'):
        entries.append([line, ''])
    elif entries:
        entries[-1][1] += line.strip()
entries = entries[:128]
if not entries or ''.join(c for c in entries[0][1] if not c.islower() and c != '.') != target['sequence']:
    raise ValueError('MSA query does not match the full target')
local_msa = out / 'target-128.a3m'
local_msa.write_text('\n'.join(line for entry in entries for line in entry) + '\n')
checkpoints = json.loads((root / 'env/boltz-checkpoints.json').read_text())
checkpoint = Path(checkpoints['cache']) / 'boltz2_conf.ckpt'
if digest(checkpoint) != checkpoints['files']['boltz2_conf.ckpt']['sha256']:
    raise ValueError('Boltz checkpoint hash mismatch')
model = Boltz2(cache_path=checkpoint)
mpnn = load_mpnn_sol()
cache = root / 'data/weights/boltz2'

def features(binder):
    native = json.dumps({'version': 1, 'sequences': [
        {'protein': {'id': 'A', 'sequence': binder, 'msa': 'empty'}},
        {'protein': {'id': 'B', 'sequence': target['sequence'], 'msa': str(local_msa)}},
    ]})
    return load_features_and_structure_writer(native, cache=cache)

design_features, _ = features('X' * 60)
epitope = [position - 1 for position in [100,101,102,158,159,161,211,212,213,214]]
loss = model.build_loss(
    loss=2 * sp.BinderTargetContact(epitope_idx=epitope)
    + sp.WithinBinderContact()
    + 5 * InverseFoldingSequenceRecovery(mpnn, temp=jnp.array(.01), num_samples=4),
    features=design_features, recycling_steps=1, sampler=model.design_sampler(25),
)
key = jax.random.key(42)
initial = jax.nn.softmax(.5 * jax.random.gumbel(key, (60, 20)), axis=-1)
@eqx.filter_jit
def raw_loss_gradient(objective, probabilities, random_key):
    return eqx.filter_value_and_grad(objective, has_aux=True)(probabilities, key=random_key)

if args.mode == 'smoke':
    (value, _), gradient = raw_loss_gradient(loss, initial, key)
    jax.block_until_ready(gradient)
    if not np.isfinite(float(value)) or not np.isfinite(np.asarray(gradient)).all():
        raise ValueError('Nonfinite smoke objective or gradient')
    extra = {'loss': float(value), 'gradient_norm': float(jnp.linalg.norm(gradient))}
else:
    soft, _ = simplex_APGM(loss_function=loss, x=initial, n_steps=75,
                          stepsize=.1, momentum=0., key=jax.random.key(43))
    sharp, _ = simplex_APGM(loss_function=loss, x=soft, n_steps=50,
                           stepsize=.5, momentum=0., scale=1.5, key=jax.random.key(44))
    sequence = ''.join(TOKENS[int(index)] for index in np.asarray(sharp.argmax(-1)))
    if len(sequence) != 60 or set(sequence) - set('ACDEFGHIKLMNPQRSTVWY'):
        raise ValueError('Invalid designed sequence')
    # Fresh discrete all-atom features; design features use unknown side chains.
    discrete_features, writer = features(sequence)
    prediction = model.predict(features=discrete_features, writer=writer, key=jax.random.key(0))
    jax.block_until_ready(prediction.pae)
    pae = np.asarray(prediction.pae)
    if pae.shape != (296,296) or not np.isfinite(pae).all():
        raise ValueError('Invalid sequence-to-PAE mapping')
    prediction.st.make_mmcif_document().write_file(str(out / 'model.cif'))
    np.savez_compressed(out / 'raw.npz', pae=pae, plddt=np.asarray(prediction.plddt))
    extra = {'binder_sequence': sequence, 'generator_model_iptm': float(prediction.iptm),
             'model_sha256': digest(out / 'model.cif'), 'raw_sha256': digest(out / 'raw.npz')}
write_json(out / 'audit.json', {
    'status': 'reference_rehearsal_only', 'submission_eligible': False,
    'mode': args.mode, 'mosaic_revision': '5937f37164bcb28bc6f1000f10134145438e5971',
    'adapter_sha256': digest(__file__),
    'environment_freeze_sha256': digest(root / 'env/mosaic-boltz2-freeze.txt'),
    'mpnn_checkpoint_sha256': digest(root / 'src/mosaic-runtime/src/mosaic/proteinmpnn/weights/soluble_v_48_020.pt'),
    'joltz_revision': 'ed0f04257dac85bd4b7bf45521cc280f86d38ded',
    'boltz_fork_revision': '7ea718a1440ecbe8e2418317192b501544147edd',
    'target_manifest_sha256': digest(target_path), 'target_msa_source_sha256': digest(msa_path),
    'target_msa_used_sha256': digest(local_msa), 'checkpoint_sha256': digest(checkpoint),
    'settings': {'seed':42, 'length':60, 'design_steps':[75,50], 'design_recycles':1,
                 'design_diffusion_steps':25, 'mpnn_samples':4, 'target_msa_rows':len(entries),
                 'epitope_positions_uniprot':[p+1 for p in epitope], 'templates':False,
                 'starting_binder':'random simplex probabilities; no known-positive input',
                 'target_interval':[1,236]},
    'memory_stats': jax.devices()[0].memory_stats(),
    'host_peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
    'elapsed_seconds': time.monotonic()-started,
    'evidence_note':'Boltz is in the design objective. Its refold is related evidence; ESMFold2 is the independent screen.',
    **extra,
})
print('Mosaic stage completed:', args.mode, flush=True)
