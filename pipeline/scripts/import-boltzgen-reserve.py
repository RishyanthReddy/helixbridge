"""Import one native reserve output, removing unmodeled inverse-fold sidechains."""
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
from biotite.structure.io.pdbx import CIFFile, get_structure, set_structure

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest, write_json
from binder_campaign.structure import AA3
from binder_campaign.candidates import ALPHABET

root = Path(os.environ['TASK_ROOT'])
pipeline = root / 'src/pipeline'
folder = root / 'results/boltzgen-reserve-v1'
out = root / 'results/boltzgen-il7ra-p139-v1'
if out.exists():
    raise ValueError('Use a fresh import; retain every previous attempt')
state = json.loads((folder / 'qualification-state.json').read_text())
if state['status'] != 'success' or state['exit_code'] != 0:
    raise ValueError('Native qualification must finish before import')
for phase in ('design', 'inverse_fold_solublempnn'):
    phase_audit = json.loads((folder / f'native-v1/{phase}-audit.json').read_text())
    for name, expected in phase_audit['artifacts'].items():
        if digest(folder / name) != expected:
            raise ValueError('Native artifact changed')
source = next((folder / 'native-v1/intermediate_designs_inverse_folded').glob('*.cif'))
atoms = get_structure(CIFFile.read(source), model=1, use_author_fields=False)
ca = atoms[atoms.atom_name == 'CA']
sequences = {c: ''.join(AA3[n] for n in ca[ca.chain_id == c].res_name)
             for c in dict.fromkeys(ca.chain_id.tolist())}
input_audit = json.loads((folder / 'input-v1/input-audit.json').read_text())
target_chains = [c for c, seq in sequences.items() if seq == input_audit['target_sequence']]
binder_chains = [c for c, seq in sequences.items() if len(seq) == 60]
if len(sequences) != 2 or len(target_chains) != 1 or len(binder_chains) != 1:
    raise ValueError('Ambiguous native chains')
tc, bc = target_chains[0], binder_chains[0]
sequence = sequences[bc]
if set(sequence) - ALPHABET or not np.isfinite(atoms.coord).all():
    raise ValueError('Noncanonical or invalid native output')
duplicates = []
for path in (root / 'results').glob('*-v1/candidates.json'):
    duplicates.extend(r['candidate_id'] for r in json.loads(path.read_text())['candidates'] if r['sequence'] == sequence)
if duplicates:
    raise ValueError('Exact existing-sequence duplicate: ' + repr(duplicates))
# SolubleMPNN supplies sequence, not sidechain packing. Retain only the binder
# backbone; fabricated/zero placeholder sidechains must not enter geometry.
keep = (atoms.chain_id == tc) | ((atoms.chain_id == bc) & np.isin(atoms.atom_name, ['N', 'CA', 'C', 'O']))
normalized = atoms[keep].copy()
for chain, positions in [(tc, input_audit['target_positions_uniprot']), (bc, list(range(1, 61)))]:
    res_ids = ca[ca.chain_id == chain].res_id.tolist()
    if len(set(res_ids)) != len(positions):
        raise ValueError('Incomplete native residue numbering')
    mapping = dict(zip(res_ids, positions))
    mask = normalized.chain_id == chain
    normalized.res_id[mask] = [mapping[int(n)] for n in normalized.res_id[mask]]
if len(normalized[(normalized.chain_id == bc) & (normalized.atom_name == 'CA')]) != 60:
    raise ValueError('Missing designed CA coordinates')
out.mkdir(parents=True)
cif = CIFFile()
set_structure(cif, normalized)
structure = out / 'generator-backbone-only.cif'
cif.write(structure)
assets = json.loads((folder / 'assets.json').read_text())
reference = dict(input_audit['source_reference_audit'])
reference['hotspots_uniprot'] = input_audit['hotspots_uniprot']
reference['active_conditioning'] = 'BoltzGen input-v1/design.yaml; source_reference_audit is provenance only'
audit = {'code_revision': assets['source_revision'],
         'model': {'revision': next(r['revision'] for r in assets['files'] if r['name'].endswith('.ckpt'))},
         'seed': 301, 'binder_sequence': sequence, 'target_chain': tc, 'binder_chain': bc,
         'reference_audit': reference, 'generated_structure': str(structure), 'generated_sha256': digest(structure),
         'native_structure': str(source), 'native_structure_sha256': digest(source),
         'input_audit_sha256': digest(folder / 'input-v1/input-audit.json'),
         'assets_sha256': digest(folder / 'assets.json'), 'qualification_state_sha256': digest(folder / 'qualification-state.json'),
         'removed_binder_sidechain_atom_count': int((~keep).sum()),
         'geometry_scope': 'Fixed target plus designed binder backbone only; native inverse-fold sidechains are not packed',
         'script_sha256': digest(__file__), 'submission_eligible': False}
write_json(out / 'import-audit.json', audit)
identity = digest(out / 'import-audit.json')[:12]
record = {'candidate_id': 'il7ra-boltzgen-' + identity, 'target_id': 'il7ra', 'sequence': sequence,
          'format': 'minibinder', 'generator': 'BoltzGen+SolubleMPNN', 'generator_revision': assets['source_revision'],
          'campaign_kind': 'reference_rehearsal', 'generator_audit': audit,
          'generator_structure': str(structure), 'generator_structure_sha256': digest(structure),
          'generator_target_chain': tc, 'generator_binder_chain': bc,
          'backbone_family_id': 'il7ra-boltzgen-s301-' + identity,
          'source_audit': str(out / 'import-audit.json'), 'source_sha256': digest(out / 'import-audit.json'),
          'qc_reasons': [], 'screen_status': 'not_run', 'independent_prediction_status': 'not_run',
          'novelty_review': 'pending', 'submission_eligible': False}
write_json(out / 'candidates.json', {'candidates': [record], 'count': 1,
                                      'note': 'Adaptive reserve, separate from paired six-design RFD4 cohort'})
subprocess.run([str(root / 'env/rfd4/bin/python'), 'scripts/prepare-candidate-evaluation.py',
                str(out / 'candidates.json'), str(out / 'evaluation-input'), 'boltzgen-il7ra-p139', '0'], check=True)
task_path = out / 'evaluation-input/boltz-task.json'
task = json.loads(task_path.read_text())
task['timeout_seconds'] = 220
write_json(task_path, task)
print(record['candidate_id'], sequence, flush=True)
