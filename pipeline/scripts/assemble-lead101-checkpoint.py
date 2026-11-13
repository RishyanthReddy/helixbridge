"""Assemble a bounded checkpoint, retaining unsuccessful predictions as missing evidence."""
import argparse
import csv
from datetime import datetime
import itertools
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
from binder_campaign.structure import AA3

parser = argparse.ArgumentParser()
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--output-dir', type=Path, required=True)
args = parser.parse_args()
w = args.workspace.resolve()
out = args.output_dir.resolve()
if out.exists():
    raise ValueError('Use a fresh checkpoint package directory')
evidence = w / 'outputs/execution-evidence'
folder = evidence / 'lead101-validation-v1'
sources = {}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keep(path, expected=None):
    actual = digest(path)
    require(expected is None or expected == actual, 'Source changed: ' + str(path))
    sources[str(path.relative_to(w))] = actual
    return path


def read(path):
    return json.loads(keep(path).read_text())


previous_dir = w / 'outputs/controlled-campaign-review-2026-11-02-v4'
previous = read(previous_dir / 'manifest.json')
for name, expected in previous['source_sha256'].items():
    keep(w / name, expected)
for name, expected in previous['output_sha256'].items():
    keep(previous_dir / name, expected)
seq_dir = evidence / 'finalist-sequence-context-v1'
seq_manifest = read(seq_dir / 'manifest.json')
for name, expected in seq_manifest['sources'].items():
    keep(w / name, expected)
for name, expected in seq_manifest['outputs'].items():
    keep(seq_dir / name, expected)
sequence_review = read(seq_dir / 'sequence-context-review.json')
require(sequence_review['submission_eligible_count'] == 0, 'Sequence review cannot set eligibility')

plan = read(folder / 'plan.json')
amendment = read(folder / 'seed2-limit-amendment.json')
require(amendment['plan_sha256'] == digest(folder / 'plan.json')
        and amendment['scientific_inputs_changed'] is False, 'Limit amendment changed science')
ledger = read(folder / 'gpu-budget.json')
require(ledger['gpu_seconds_cap'] == 1200 and ledger['max_concurrent_gpus'] == 2
        and not ledger.get('unresolved_submission'), 'Budget configuration differs')
records_path = evidence / 'rfd4-il7ra-campaign-s101-v1/candidates.json'
candidate = read(records_path)['candidates'][0]
require(candidate['candidate_id'] == plan['candidate_id'] == 'il7ra-rfd4-6b3ca40a31bb'
        and digest(records_path) == plan['candidate_records_sha256'] and not candidate['submission_eligible'],
        'Candidate identity/eligibility changed')
baseline_path = records_path.parent / 'evaluation-input/input.json'
baseline = read(baseline_path)
require(digest(baseline_path) == plan['baseline_input_sha256'], 'Baseline changed')
for task in plan['tasks'] + amendment['tasks']:
    relative = Path(task['task']).relative_to('/cfs/earth/scratch/mekalris/changjiang-2026/results')
    keep(evidence / relative, task['task_sha256'])

helper = runpy.run_path(str(w / 'pipeline/scripts/assemble-controlled-campaign.py'))
jobs = {r['job_id']: r for r in ledger['jobs']}
scheduler_path = keep(folder / 'gpu-allocations.txt')
allocations = {}
events = []
for line in scheduler_path.read_text().splitlines():
    if not line.strip():
        continue
    job, name, state, exit_code, start, end, elapsed, tres = line.split('|')
    require(job in jobs and job not in allocations and 'gres/gpu=1' in tres, 'Scheduler identity/GPU mismatch')
    require(state in {'COMPLETED', 'FAILED', 'TIMEOUT', 'CANCELLED', 'OUT_OF_MEMORY'}, 'Job is not terminal')
    allocations[job] = {'name': name, 'state': state, 'exit_code': exit_code, 'gpu_seconds': int(elapsed)}
    events.extend([(datetime.fromisoformat(start), 1), (datetime.fromisoformat(end), -1)])
require(set(allocations) == set(jobs) and len(jobs) == 4, 'Missing or unexpected GPU allocation')
active = peak = 0
for _, change in sorted(events):
    active += change
    peak = max(peak, active)
seconds = sum(r['gpu_seconds'] for r in allocations.values())
require(seconds <= 1200 and peak <= 2 and active == 0, 'Budget/concurrency exceeded')
for job in jobs.values():
    remote = Path(job['task']).relative_to('/cfs/earth/scratch/mekalris/changjiang-2026/results')
    keep(evidence / remote, job['task_sha256'])
for path in sorted((folder / 'slurm').glob('*')):
    if path.is_file():
        keep(path)


def pose(path, target_sequence, target_positions):
    data = MMCIF2Dict(str(path))
    xyz = np.array([data['_atom_site.Cartn_x'], data['_atom_site.Cartn_y'], data['_atom_site.Cartn_z']], dtype=float).T
    names = np.array(data['_atom_site.label_atom_id'])
    ids = np.array(data['_atom_site.label_asym_id'])
    residues = np.array(data['_atom_site.label_seq_id'])
    components = np.array(data['_atom_site.label_comp_id'])
    elements = np.array(data['_atom_site.type_symbol'])
    ca = names == 'CA'
    sequences = {c: ''.join(AA3[n] for n in components[ca & (ids == c)]) for c in dict.fromkeys(ids.tolist())}
    tc = [c for c, s in sequences.items() if s == target_sequence]
    bc = [c for c, s in sequences.items() if s == candidate['sequence']]
    require(len(sequences) == 2 and len(tc) == len(bc) == 1 and tc != bc and np.isfinite(xyz).all(),
            'Ambiguous chain mapping/nonfinite coordinates')
    tca = xyz[ca & (ids == tc[0])]
    bca = xyz[ca & (ids == bc[0])]
    residue_ids = residues[ca & (ids == tc[0])]
    # Generated CIFs renumber the cropped 195-residue target from one. Its exact
    # sequence and ordered CA list map to the recorded UniProt positions; the
    # full-target refolds must instead retain the complete 1–236 sequence.
    require([int(r) for r in residue_ids] in [target_positions, list(range(1, len(target_positions) + 1))],
            'Target numbering is neither explicit UniProt nor exact sequence order')
    require([int(r) for r in residues[ca & (ids == bc[0])]] == list(range(1, len(candidate['sequence']) + 1)),
            'Binder numbering differs')
    mapping = dict(zip(residue_ids, target_positions))
    heavy = (elements != 'H') & (elements != 'D')
    ti = np.where(heavy & (ids == tc[0]))[0]
    bi = np.where(heavy & (ids == bc[0]))[0]
    distances = np.linalg.norm(xyz[ti, None, :] - xyz[bi][None, :, :], axis=-1)
    contacts = sorted({mapping[residues[ti[i]]] for i in np.where((distances < 5).any(axis=1))[0]})
    return {'target_ca': tca, 'binder_ca': bca,
            'contacts': contacts, 'close_pairs': int((distances < 2).sum()),
            'target_positions': target_positions,
            'min_distance': float(distances.min())}


def align(fixed, moving, positions):
    a = fixed['target_ca'][[fixed['target_positions'].index(p) for p in positions]]
    b = moving['target_ca'][[moving['target_positions'].index(p) for p in positions]]
    atoms = lambda xs: [Atom('CA', x, 0., 1., ' ', ' CA ', i, element='C') for i, x in enumerate(xs)]
    fit = Superimposer()
    fit.set_atoms(atoms(a), atoms(b))
    rot, trans = fit.rotran
    rmsd = float(np.sqrt(np.mean(np.sum((moving['binder_ca'] @ rot + trans - fixed['binder_ca']) ** 2, axis=1))))
    # Independent direct SVD implementation checks the alignment convention.
    bm, am = b.mean(0), a.mean(0)
    u, _, vt = np.linalg.svd((b - bm).T @ (a - am))
    if np.linalg.det(u @ vt) < 0:
        u[:, -1] *= -1
    transformed = (moving['binder_ca'] - bm) @ (u @ vt) + am
    independent = float(np.sqrt(np.mean(np.sum((transformed - fixed['binder_ca']) ** 2, axis=1))))
    require(math.isclose(rmsd, independent, abs_tol=1e-6), 'Alignment convention disagrees')
    return {'target_fit_rmsd_A': float(fit.rms), 'target_aligned_binder_ca_rmsd_A': rmsd}


reference = candidate['generator_audit']['reference_audit']
positions = reference['positions']
anchors = reference.get('alignment_positions', positions)
gen_path = evidence / 'rfd4-il7ra-campaign-s101-v1/prediction/model.cif'
keep(gen_path, candidate['generator_structure_sha256'])
generated = pose(gen_path, reference['reference_sequence'], positions)
target = read(w / 'pipeline/data/targets/il7ra/manifest.json')
rows = []
poses = {}
for seed in (0, 1, 2):
    campaign = 'rfd4-il7ra-campaign-s101' if seed == 0 else f'rfd4-il7ra-s101-eval-s{seed}'
    input_path = baseline_path if seed == 0 else folder / f'prediction-seed-{seed}/input.json'
    request = read(input_path)
    expected = {**baseline, 'settings': {**baseline['settings'], 'seed': seed}}
    require(request == expected, 'A non-seed request field differs from the baseline')
    for model in ('esmfold2', 'boltz'):
        directory = evidence / f'{campaign}-{model}-v1'
        state = read(directory / 'task-state.json')
        helper['verify_recorded_inputs'](state, w, sources)
        summary = {'prediction_seed': seed, 'predictor': model, 'status': state['status'], 'submission_eligible': False}
        if state['status'] != 'success':
            require(seed != 0 and state['status'] == 'failed', 'Unexpected unfinished baseline/task')
            require(all(v is None for v in state.get('partial_outputs', {}).values()), 'Unexpected partial model output')
            require(not (directory / 'prediction/model.cif').exists(), 'Failed task has an unreviewed structure')
            summary.update({'error': state['error'], 'task_elapsed_seconds': state['elapsed_seconds'],
                            'interpretation': 'Missing prediction; not an adverse binding label or a zero confidence score'})
            keep(directory / 'model.log')
            rows.append(summary)
            continue
        require(state['exit_code'] == 0, 'Successful task has nonzero exit')
        helper['verify_recorded_outputs'](state, w, sources)
        prediction = directory / 'prediction'
        metrics = read(prediction / 'metrics.json')
        require(metrics['input_sha256'] == digest(input_path), 'Prediction input hash differs')
        actual_seed = metrics['settings']['seed'] if model == 'esmfold2' else metrics['seed']
        require(actual_seed == seed, 'Actual prediction seed differs')
        for name, expected_hash in metrics['artifacts'].items():
            keep(prediction / name, expected_hash)
        raw = prediction / ('raw.npz' if model == 'esmfold2' else 'boltz_results_input/predictions/input/pae_input_model_0.npz')
        raw_pae = np.load(keep(raw))['pae']
        json_pae = np.array(read(prediction / 'pae.json')['pae'])
        n = len(target['sequence']) + len(candidate['sequence'])
        require(json_pae.shape == raw_pae.shape == (n, n) and np.isfinite(json_pae).all()
                and np.array_equal(raw_pae, json_pae), 'Raw/JSON PAE or residue-token size differs')
        directions = [r for r in metrics['ipsae']['pairwise'] if r['type'] == 'asym']
        require([(r['chain1'], r['chain2']) for r in directions] == [('A', 'B'), ('B', 'A')], 'Directional mapping differs')
        values = [r['ipsae'] for r in directions]
        require(len(values) == 2 and all(math.isfinite(v) for v in values) and math.isfinite(metrics['iptm']), 'Nonfinite metrics')
        native_pose = pose(prediction / 'model.cif', target['sequence'], list(range(1, 237)))
        poses[(model, seed)] = native_pose
        geometry = align(native_pose, generated, anchors)
        summary.update({'iptm': metrics['iptm'], 'ipsae_target_to_binder': values[0], 'ipsae_binder_to_target': values[1],
                        'generator_to_refold': geometry, 'heavy_atom_pairs_lt_2A': native_pose['close_pairs'],
                        'minimum_interchain_heavy_distance_A': native_pose['min_distance'],
                        'target_contact_positions_lt_5A': native_pose['contacts']})
        if seed == 0:
            prior = read(evidence / 'rfd4-il7ra-campaign-s101-review-v1/review.json')['predictions'][model]
            require(math.isclose(geometry['target_aligned_binder_ca_rmsd_A'],
                                prior['target_aligned_binder_ca_rmsd_angstrom'], abs_tol=1e-4), 'Baseline geometry changed')
            require(native_pose['close_pairs'] == prior['contacts']['heavy_atom_pairs_lt_2A'], 'Baseline clash count changed')
        elif model == 'boltz':
            prior_metrics = read(evidence / f'rfd4-il7ra-campaign-s101-{model}-v1/prediction/metrics.json')
            require(metrics['model'] == prior_metrics['model'] and metrics['samples'] == prior_metrics['samples'] == 1
                    and metrics['target_only_precomputed_msa'] and not metrics['templates_or_pocket_constraints'],
                    'Boltz checkpoint or protocol changed')
            left = list(metrics['native_argv'])
            right = list(prior_metrics['native_argv'])
            for argv in (left, right):
                argv[argv.index('--seed') + 1] = 'SEED'
                argv[argv.index('--out_dir') + 1] = 'OUTPUT'
                argv[0] = 'INPUT'
            require(left == right, 'Boltz non-seed inference arguments changed')
        else:
            prior_metrics = read(evidence / 'rfd4-il7ra-campaign-s101-esmfold2-v1/prediction/metrics.json')
            require(metrics['model_revisions'] == prior_metrics['model_revisions']
                    and metrics['target_msa_sha256'] == prior_metrics['target_msa_sha256']
                    and {k:v for k,v in metrics['settings'].items() if k != 'seed'} ==
                        {k:v for k,v in prior_metrics['settings'].items() if k != 'seed'},
                    'ESMFold2 checkpoint or non-seed settings changed')
        rows.append(summary)

pairwise = []
for a, b in itertools.combinations(sorted(poses), 2):
    pa, pb = poses[a], poses[b]
    first, second = set(pa['contacts']), set(pb['contacts'])
    pairwise.append({'left': {'predictor': a[0], 'seed': a[1]}, 'right': {'predictor': b[0], 'seed': b[1]},
        'shared_reference_core_alignment': align(pa, pb, anchors),
        'complete_target_alignment': align(pa, pb, list(range(1, 237))),
        'target_contact_jaccard': len(first & second) / len(first | second) if first | second else None})
for name in ('home', 'details'):
    read(w / f'outputs/official-refresh-2026-11-02-{name}.json')
keep(w / 'outputs/lead101-validation-plan-2026-11-02.md')
keep(w / 'pipeline/scripts/assemble-lead101-checkpoint.py')
keep(w / 'pipeline/scripts/review-finalist-sequences.py', seq_manifest['script_sha256'])
for name in ('binder_campaign/sequence_review.py', 'binder_campaign/budget.py',
             'scripts/submit-budgeted.py', 'scripts/prepare-lead101-validation.py',
             'scripts/tighten-lead101-limits.py', 'scripts/export-finalist-reference-corpus.py'):
    keep(w / 'pipeline' / name)
result = {'candidate_id': candidate['candidate_id'], 'prediction_attempts': rows, 'pairwise_geometry': pairwise,
    'budget': {'gpu_seconds': seconds, 'gpu_minutes': seconds / 60, 'cap_gpu_seconds': 1200,
               'maximum_concurrency': peak, 'allocations': allocations},
    'decision': 'Do not promote seed101 beyond research follow-up; retain43 as the cleaner repeat-tested baseline',
    'checkpoint_status': 'assessed; advancement_gate_not_met',
    'robustness_limit': 'Boltz has three completed seeds; ESMFold2 has baseline only. Both added ESMFold2 attempts timed out before a structure. Full two-model robustness remains incomplete.',
    'sequence_context': sequence_review, 'submission_eligible_count': 0, 'official_submission_schema': False}
out.mkdir(parents=True)
write_json(out / 'checkpoint.json', result)
fields = ['prediction_seed', 'predictor', 'status', 'iptm', 'ipsae_target_to_binder',
          'ipsae_binder_to_target', 'generator_to_refold_binder_ca_rmsd_A', 'heavy_atom_pairs_lt_2A',
          'error', 'submission_eligible']
with (out / 'REHEARSAL_ONLY_prediction_attempts.csv').open('x', newline='') as stream:
    writer = csv.DictWriter(stream, fields)
    writer.writeheader()
    for row in rows:
        exported = {k: row[k] for k in fields if k in row}
        exported['submission_eligible'] = 'false'
        exported['generator_to_refold_binder_ca_rmsd_A'] = row.get('generator_to_refold', {}).get('target_aligned_binder_ca_rmsd_A', '')
        writer.writerow(exported)
with (out / 'EMPTY_submission_shortlist.csv').open('x', newline='') as stream:
    csv.writer(stream).writerow(['candidate_id', 'target_id', 'sequence', 'submission_eligible'])
report = '''# Lead101 checkpoint — advancement gate remains open

Retain seed43 as the cleaner repeat-tested research baseline. Seed101 remains a
research follow-up: its two Boltz repeats agree with the initial prediction, but
the two added ESMFold2 attempts ended before producing structures. They supply
no new interface score. Do not treat timeouts as nonbinding predictions.

The four new allocations consumed {minutes:.2f} GPU-minutes, including failed
jobs and configuration time, with maximum concurrency {peak}. No retry was
launched from the approximately one minute remaining in the 20-minute budget.
Both successful Boltz outputs have verified inputs, raw PAE, chain mapping and
independently calculated pose/contact diagnostics. The original campaign package
remains unchanged. `checkpoint.json` retains all six baseline/attempt records.

All four research follow-ups were compared locally with 1,684 public sequence
rows (1,683 unique; 90 IL7Rα designs included) and the 17-design internal pool.
No exact or strict >90% contiguous-overlap flag was found. These checks establish
neither global novelty nor cross-team eligibility; LCS diagnostics are not
homology or alignment identity. No candidate sequence was uploaded for searching.

Seed101 alone has Cys25 and sequons Asn18-Leu19-Ser20 and Asn29-Ile30-Ser31.
In both baseline refolds, Cys25 is at the interface (~3.7–3.8 Å to target heavy
atoms); Asn18 is close to the interface and both Asn side chains are solvent
exposed in the unmodified complex. This warrants expression-dependent review.
Motifs and SASA do not prove glycosylation, oxidation or experimental failure.
Seeds43/103/105 lack these particular motifs; that does not establish general
developability. No glycan conformations were modeled for binder or target.

Public [target](https://aiprotein.sjtu.edu.cn/targets) and
[rules](https://aiprotein.sjtu.edu.cn/rules) pages were refreshed November2.
IL7Rα remains P16871-1 residues1–236, minibinder40–100aa. Exact organizer model,
seed value, ipSAE aggregation, assay construct/processing/glycans and CSV columns
remain unspecified in the inspected public pages. Login/confirmation wording
still needs care. No registration, login, message or submission was performed.

Next: diagnose and reduce shared-filesystem startup I/O, then retry only the two
missing ESMFold2 seeds under a fresh explicit budget. Keep predicted confidence
separate from sequence/context risks. Broader epitope coverage and truly external
ranking validation remain later TODO gates. No binding, affinity, expression,
glycan compatibility or competition eligibility is established.
'''.format(minutes=seconds / 60, peak=peak)
(out / 'REVIEW.md').write_text(report)
outputs = {p.name: digest(p) for p in sorted(out.iterdir()) if p.is_file()}
write_json(out / 'manifest.json', {'source_sha256': dict(sorted(sources.items())), 'output_sha256': outputs,
    'submission_eligible_count': 0, 'official_submission_schema': False})
print(json.dumps({'status': result['checkpoint_status'], 'sources': len(sources), 'outputs': len(outputs),
                  'successful_new_predictions': sum(r['status'] == 'success' and r['prediction_seed'] != 0 for r in rows),
                  'failed_new_predictions': sum(r['status'] == 'failed' for r in rows), 'gpu_seconds': seconds}))
