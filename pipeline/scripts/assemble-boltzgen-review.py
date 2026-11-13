"""Independently audit one adaptive reserve case, keeping related models explicit."""
import argparse
import csv
import json
import math
from pathlib import Path
import runpy
import sys

import numpy as np
from Bio.PDB import Superimposer
from Bio.PDB.Atom import Atom
from Bio.PDB.MMCIF2Dict import MMCIF2Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest, write_json
from binder_campaign.pose_review import read_pair, align_pair
from binder_campaign.sequence_review import sequence_diagnostic, overlap_diagnostic

parser = argparse.ArgumentParser()
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--output-dir', type=Path, required=True)
args = parser.parse_args()
w = args.workspace.resolve()
out = args.output_dir.resolve()
if out.exists():
    raise ValueError('Use a fresh package directory')
e = w / 'outputs/execution-evidence'
f = e / 'boltzgen-reserve-v1'
sources = {}
remote = Path('/cfs/earth/scratch/mekalris/changjiang-2026')


def keep(path, expected=None):
    actual = digest(path)
    if expected is not None and actual != expected:
        raise ValueError('Changed artifact: ' + str(path))
    sources[str(path.relative_to(w))] = actual
    return path


def read(path):
    return json.loads(keep(path).read_text())


def local_path(name):
    relative = Path(name).relative_to(remote)
    prefix = relative.parts[0]
    if prefix == 'results':
        return e / relative.relative_to('results')
    if str(relative).startswith('src/pipeline/'):
        return w / 'pipeline' / relative.relative_to('src/pipeline')
    if prefix == 'env' and len(relative.parts) == 2:
        return f / 'env-records' / relative.name
    if str(relative) == 'src/IPSAE/ipsae.py':
        return w / 'work/vendor/IPSAE/ipsae.py'
    raise ValueError('Unmapped execution path: ' + name)


def verify_state(path):
    state = read(path)
    if state['status'] != 'success' or state['exit_code'] != 0:
        raise ValueError('Incomplete task: ' + str(path))
    for field in ('inputs', 'outputs'):
        for name, expected in state[field].items():
            keep(local_path(name), expected)
    return state


verify_state(f / 'qualification-state.json')
assets = read(f / 'assets.json')
if assets['source_revision'] != '6472b44e8072187e6eaa51271ae6838245206013':
    raise ValueError('Unexpected reserve code revision')
for phase in ('design', 'inverse_fold_solublempnn'):
    verify_state(f / f'{phase}-state.json')
    audit = read(f / f'native-v1/{phase}-audit.json')
    keep(w / f'work/vendor/BoltzGen/src/boltzgen/resources/config/{phase}.yaml', audit['config_source_sha256'])
    keep(f / f'native-v1/{phase}-resolved.yaml', audit['resolved_config_sha256'])
    keep(w / 'pipeline/scripts/boltzgen-reserve-native.py', audit['script_sha256'])
    for name, expected in audit['artifacts'].items():
        keep(f / name, expected)
    if audit['seed'] != 301 or 'L40S' not in audit['device']:
        raise ValueError('Generation seed/device changed')
directory = e / 'boltzgen-il7ra-p139-v1'
record_path = directory / 'candidates.json'
record = read(record_path)['candidates'][0]
reference = record['generator_audit']['reference_audit']
if record['generator'] != 'BoltzGen+SolubleMPNN' or record['submission_eligible'] or record['qc_reasons']:
    raise ValueError('Incorrect import identity/eligibility')
input_audit = read(f / 'input-v1/input-audit.json')
keep(f / 'input-v1/target.pdb', input_audit['target_pdb_sha256'])
keep(f / 'input-v1/design.yaml', input_audit['design_yaml_sha256'])
keep(w / 'pipeline/data/targets/il7ra/rfd4-reference/target.cif', input_audit['source_target_sha256'])
if input_audit['parsed_binding_indices'] != input_audit['hotspots_local'] or input_audit['supplied_starting_binder_sequence_or_coordinates']:
    raise ValueError('Input mapping/initialization differs')
gen_path = keep(directory / 'generator-backbone-only.cif', record['generator_structure_sha256'])
gen = read_pair(gen_path, reference['reference_sequence'], record['sequence'], reference['positions'])
original_data = MMCIF2Dict(str(w / 'pipeline/data/targets/il7ra/rfd4-reference/target.cif'))
original_xyz = np.asarray([original_data['_atom_site.Cartn_x'], original_data['_atom_site.Cartn_y'],
                           original_data['_atom_site.Cartn_z']], float).T
original_ca = original_xyz[np.asarray(original_data['_atom_site.label_atom_id']) == 'CA']
ca_atoms = lambda xs: [Atom('CA', x, 0., 1., ' ', ' CA ', i, element='C') for i, x in enumerate(xs)]
target_fit = Superimposer()
target_fit.set_atoms(ca_atoms(original_ca), ca_atoms(gen['target_ca']))
data = MMCIF2Dict(str(gen_path))
xyz = np.array([data['_atom_site.Cartn_x'], data['_atom_site.Cartn_y'], data['_atom_site.Cartn_z']], float).T
if np.any(np.linalg.norm(xyz, axis=1) < .01):
    raise ValueError('Unmodeled origin-coordinate placeholder remained')
review_dir = e / 'boltzgen-il7ra-p139-review-v1'
review = read(review_dir / 'review.json')
independent = read(review_dir / 'independent-pose-audit.json')
context = read(review_dir / 'target-context-audit.json')
if review['candidate_records_sha256'] != digest(record_path) or independent['source_review_sha256'] != digest(review_dir / 'review.json') or context['review_sha256'] != digest(review_dir / 'review.json'):
    raise ValueError('Review provenance mismatch')
request_path = directory / 'evaluation-input/input.json'
request = read(request_path)
target = read(w / 'pipeline/data/targets/il7ra/manifest.json')['sequence']
if request['target']['sequence'] != target or request['partner']['sequence'] != record['sequence'] or request['partner']['msa'] is not None or request['settings']['seed'] != 0:
    raise ValueError('Common scientific request changed')
verify_state(e / 'boltzgen-il7ra-p139-boltz-v1/task-state.json')
stage = f / 'staging/reserve'
verify_state(stage / 'task-state.json')
stage_audit = read(stage / 'predictions-v1/staging-state.json')
for kind in ('environment', 'checkpoint'):
    descriptor = read(stage / f'{kind}-archive.json')
    if stage_audit[f'{kind}_extraction']['archive_sha256'] != descriptor['sha256']:
        raise ValueError('Staged archive identity mismatch')
prior = read(w / 'outputs/esm-recovery-review-2026-11-02-v2/review.json')['sequence_context_review_unchanged']['research_followups']
poses = {}
models = {}
for model in ('esmfold2', 'boltz'):
    prediction = e / f'boltzgen-il7ra-p139-{model}-v1/prediction'
    metrics = read(prediction / 'metrics.json')
    if metrics['input_sha256'] != digest(request_path) or digest(prediction / 'metrics.json') != review['predictions'][model]['metrics_sha256']:
        raise ValueError('Prediction request/metrics mismatch')
    for name, expected in metrics['artifacts'].items():
        keep(prediction / name, expected)
    if model == 'esmfold2':
        copied = read(prediction.parent / 'staged-source.json')
        for name, expected in copied['files'].items():
            keep(prediction / name, expected)
            keep(stage / 'predictions-v1/seed-p139-s301/prediction' / name, expected)
        if metrics['model_revisions'] != {'biohub/ESMFold2': '69869f737beffec5294845ede23db5fc0b4f509e'} or metrics['settings'] != request['settings']:
            raise ValueError('ESM model/settings changed')
        raw = prediction / 'raw.npz'
    else:
        if metrics['seed'] != 0 or metrics['samples'] != 1 or not metrics['target_only_precomputed_msa'] or metrics['templates_or_pocket_constraints']:
            raise ValueError('Boltz settings changed')
        raw = prediction / 'boltz_results_input/predictions/input/pae_input_model_0.npz'
    pae = np.asarray(read(prediction / 'pae.json')['pae'])
    keep(raw)
    if pae.shape != (296, 296) or not np.isfinite(pae).all() or not np.array_equal(pae, np.load(raw)['pae']):
        raise ValueError('Raw PAE mismatch')
    pose = read_pair(prediction / 'model.cif', target, record['sequence'], list(range(1, 237)))
    poses[model] = pose
    fit = align_pair(pose, gen, reference['positions'])
    if not math.isclose(fit['target_aligned_binder_ca_rmsd_A'], review['predictions'][model]['target_aligned_binder_ca_rmsd_angstrom'], abs_tol=1e-4):
        raise ValueError('Independent pose calculation disagrees')
    atoms = lambda xs: [Atom('CA', x, 0., 1., ' ', ' CA ', i, element='C') for i, x in enumerate(xs)]
    shape = Superimposer()
    shape.set_atoms(atoms(gen['binder_ca']), atoms(pose['binder_ca']))
    sites = set(pose['target_contacts_lt_5A'])
    overlaps = {}
    for lead in prior:
        original = set(lead['poses'][model]['target_contact_positions_lt_5A'])
        overlaps[lead['candidate_id']] = len(sites & original) / len(sites | original) if sites | original else None
    models[model] = {'iptm': metrics['iptm'], 'minimum_directional_ipsae': review['predictions'][model]['ipsae_directional_min'],
                     'generator_to_refold': fit, 'binder_only_CA_rmsd_A': float(shape.rms),
                     'hotspots_contacted': sorted(sites & set(input_audit['hotspots_uniprot'])),
                     'target_contacts': sorted(sites), 'heavy_atom_pairs_lt_2A': pose['heavy_atom_pairs_lt_2A'],
                     'lead_contact_jaccard': overlaps, 'peak_reserved_mib': metrics['peak_reserved_mib']}
corpus_dir = e / 'finalist-reference-corpus-v1'
corpus_manifest = read(corpus_dir / 'manifest.json')
for name, expected in corpus_manifest['outputs'].items():
    keep(corpus_dir / name, expected)
corpus = read(corpus_dir / 'corpus.json')['rows']
flags = []
for row in corpus:
    diagnostic = overlap_diagnostic(record['sequence'], row['sequence'])
    if diagnostic['exact_duplicate'] or diagnostic['over_90pct_contiguous_in_either_direction']:
        flags.append({'id': row['id'], 'source': row['source'], **diagnostic})
helper = runpy.run_path(str(w / 'pipeline/scripts/assemble-controlled-campaign.py'))
budget = helper['budget_audit'](w, read(f / 'gpu-budget-final.json'), keep(f / 'gpu-allocations-final.txt'))
reserve_seconds = sum(row['gpu_seconds'] for job, row in budget['allocations'].items() if job in ('1104819', '1104821', '1104822'))
if reserve_seconds > 1800:
    raise ValueError('Adaptive reserve cap exceeded')
report = {'status': 'one_adaptive_reserve_case_reviewed_research_only', 'candidate_id': record['candidate_id'],
          'sequence': record['sequence'], 'generator': record['generator'], 'sequence_diagnostics': sequence_diagnostic(record['sequence']),
          'generator_target_CA_self_fit_to_input_A': float(target_fit.rms),
          'generator_hotspots_backbone_contacts': sorted(set(gen['target_contacts_lt_5A']) & set(input_audit['hotspots_uniprot'])),
          'models': models, 'cross_refold': align_pair(poses['esmfold2'], poses['boltz'], reference['positions']),
          'target_context': context, 'limited_public_rows': len(corpus), 'public_overlap_flags': flags,
          'reserve_gpu_seconds': reserve_seconds, 'combined_budget': budget, 'submission_eligible': False,
          'interpretation': 'One case establishes operational compatibility only. Boltz-family generation/refolding are related evidence. No experimental binding or comparative accuracy established.'}
out.mkdir(parents=True)
write_json(out / 'review.json', report)
fields = ['candidate_id', 'model', 'iptm', 'minimum_directional_ipsae', 'heavy_atom_pairs_lt_2A', 'submission_eligible']
with (out / 'REHEARSAL_ONLY_scores.csv').open('x', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for model, row in models.items():
        writer.writerow({'candidate_id': record['candidate_id'], 'model': model, 'iptm': row['iptm'],
                         'minimum_directional_ipsae': row['minimum_directional_ipsae'],
                         'heavy_atom_pairs_lt_2A': row['heavy_atom_pairs_lt_2A'], 'submission_eligible': False})
keep(Path(__file__).resolve())
write_json(out / 'manifest.json', {'source_sha256': sources,
           'output_sha256': {p.name: digest(p) for p in out.iterdir() if p.is_file()}, 'submission_eligible': False})
print(json.dumps({'candidate_id': record['candidate_id'], 'models': models, 'budget': budget}, indent=2))
