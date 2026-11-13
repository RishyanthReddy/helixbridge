"""Verify staged recovery and assemble the six-seed predictor review without promotion."""
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest, write_json
from binder_campaign.pose_review import read_pair, align_pair, target_region_differences

parser = argparse.ArgumentParser()
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--output-dir', type=Path, required=True)
args = parser.parse_args()
w = args.workspace.resolve()
out = args.output_dir.resolve()
if out.exists():
    raise ValueError('Use a fresh recovery review directory')
evidence = w / 'outputs/execution-evidence'
folder = evidence / 'esm-startup-recovery-v1'
sources = {}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def keep(path, expected=None):
    actual = digest(path)
    require(expected is None or actual == expected, 'Artifact changed: ' + str(path))
    sources[str(path.relative_to(w))] = actual
    return path


def read(path):
    return json.loads(keep(path).read_text())


previous_dir = w / 'outputs/lead101-checkpoint-2026-11-02-v2'
previous_manifest = read(previous_dir / 'manifest.json')
for name, sha in previous_manifest['source_sha256'].items():
    keep(w / name, sha)
for name, sha in previous_manifest['output_sha256'].items():
    keep(previous_dir / name, sha)
previous = read(previous_dir / 'checkpoint.json')
prep = read(folder / 'preparation.json')
environment = read(folder / 'environment-archive.json')
weights = read(folder / 'checkpoint-archive.json')
require(digest(folder / 'environment-archive.json') == prep['environment_descriptor_sha256']
        and digest(folder / 'checkpoint-archive.json') == prep['checkpoint_descriptor_sha256'],
        'CPU-prepared archive descriptors differ')
qualification = read(folder / 'cpu-qualification-v1/staging-state.json')
runtime = read(folder / 'predictions-v1/staging-state.json')
for record in (qualification, runtime):
    require(record['status'] == 'success' and record['preparation_sha256'] == digest(folder / 'preparation.json'),
            'CPU qualification or staged prediction stage did not succeed')
    require(record['environment_extraction']['archive_sha256'] == environment['sha256']
            and record['checkpoint_extraction']['archive_sha256'] == weights['sha256'],
            'CPU/GPU did not verify the same immutable archive bytes')
    require(record['environment_extraction']['verified_members'] == len(environment['members'])
            and record['checkpoint_extraction']['verified_members'] == len(weights['members']),
            'Runtime verification did not cover all archived members')
    prefix = record['probe_result']['prefix']
    require(prefix.startswith(record['stage_root'] + '/')
            and all(path.startswith(prefix + '/') for path in record['probe_result']['module_paths'].values())
            and record['probe_result']['nn_parameters_loaded'] is False,
            'Probe import paths or CPU-safe qualification differ')
task = read(folder / 'task-state.json')
require(task['status'] == 'success' and task['exit_code'] == 0, 'Recovery task did not finish successfully')
helper = runpy.run_path(str(w / 'pipeline/scripts/assemble-controlled-campaign.py'))
for remote, expected in task['inputs'].items():
    if '/results/esm-startup-recovery-v1/' in remote:
        local = folder / remote.split('/results/esm-startup-recovery-v1/', 1)[1]
        keep(local, expected)
    else:
        helper['verify_recorded_inputs']({'inputs': {remote: expected}}, w, sources)
helper['verify_recorded_outputs'](task, w, sources)
original = read(folder / 'predictions-v1/original-checkpoints.json')
effective = read(folder / 'predictions-v1/runtime-checkpoints.json')
for before, after in zip(original, effective):
    require({k:v for k,v in before.items() if k != 'path'} == {k:v for k,v in after.items() if k != 'path'},
            'Staging changed more than checkpoint paths')
    require(Path(after['path']).is_relative_to(Path(runtime['stage_root'])), 'Effective model path is not node-local')
require(len(original) == len(effective) == 1 and original[0]['revision'] == weights['revision'], 'Unexpected model set')
require({k: {f:v for f,v in entry.items() if f != 'type'} for k,entry in weights['members'].items()} == original[0]['files'],
        'Archived weight-file identities differ from the pinned model manifest')
ledger = read(folder / 'gpu-budget.json')
require(ledger['gpu_seconds_cap'] == 900 and ledger['max_concurrent_gpus'] == 1
        and not ledger.get('unresolved_submission') and len(ledger['jobs']) == 1, 'Unexpected recovery resource envelope')
lines = [r for r in keep(folder / 'gpu-allocations.txt').read_text().splitlines() if r.strip()]
require(len(lines) == 1, 'Unexpected scheduler records')
job, name, status, exit_code, start, end, elapsed, tres = lines[0].split('|')
require(job == ledger['jobs'][0]['job_id'] == runtime['slurm_job_id'] and status == 'COMPLETED'
        and exit_code == '0:0' and 'gres/gpu=1' in tres and int(elapsed) <= 900,
        'GPU accounting, allocation identity or completion differs')
guard = read(folder / 'budget-guard.json')
require(guard['status'] == 'success' and guard['job_id'] == job, 'GPU budget guard did not complete')
records_path = evidence / 'rfd4-il7ra-campaign-s101-v1/candidates.json'
candidate = read(records_path)['candidates'][0]
baseline_request = read(records_path.parent / 'evaluation-input/input.json')
target = read(w / 'pipeline/data/targets/il7ra/manifest.json')
reference = candidate['generator_audit']['reference_audit']
anchors = reference.get('alignment_positions', reference['positions'])
generated = read_pair(keep(records_path.parent / 'prediction/model.cif', candidate['generator_structure_sha256']),
                      reference['reference_sequence'], candidate['sequence'], reference['positions'])
cases = []
poses = {}
for seed in (0, 1, 2):
    for model in ('esmfold2', 'boltz'):
        if seed == 0:
            pred = evidence / f'rfd4-il7ra-campaign-s101-{model}-v1/prediction'
            request_path = records_path.parent / 'evaluation-input/input.json'
        else:
            request_path = evidence / f'lead101-validation-v1/prediction-seed-{seed}/input.json'
            pred = (folder / f'predictions-v1/seed-{seed}/prediction' if model == 'esmfold2' else
                    evidence / f'rfd4-il7ra-s101-eval-s{seed}-boltz-v1/prediction')
        request = read(request_path)
        require(request == {**baseline_request, 'settings': {**baseline_request['settings'], 'seed': seed}},
                'A non-seed scientific request field changed')
        metrics = read(pred / 'metrics.json')
        require(metrics['input_sha256'] == digest(request_path), 'Effective scientific input differs')
        actual_seed = metrics['settings']['seed'] if model == 'esmfold2' else metrics['seed']
        require(actual_seed == seed, 'Actual inference seed differs')
        for filename, expected in metrics['artifacts'].items():
            keep(pred / filename, expected)
        if model == 'esmfold2':
            require(metrics['model_revisions'] == {'biohub/ESMFold2': weights['revision']}
                    and metrics['settings'] == request['settings']
                    and metrics['target_msa_sha256'] == digest(w / 'pipeline/data/targets/il7ra/msa/target.a3m'),
                    'ESMFold2 checkpoint, settings or MSA changed')
        pae = np.array(read(pred / 'pae.json')['pae'])
        raw = keep(pred / ('raw.npz' if model == 'esmfold2' else 'boltz_results_input/predictions/input/pae_input_model_0.npz'))
        raw_pae = np.load(raw)['pae']
        require(pae.shape == raw_pae.shape == (296, 296) and np.isfinite(pae).all()
                and np.array_equal(pae, raw_pae), 'PAE tokens, raw data or finite checks differ')
        regional_plddt = None
        if model == 'esmfold2':
            plddt = np.load(raw)['plddt']
            require(plddt.shape == (296,) and np.isfinite(plddt).all(), 'Raw pLDDT mapping differs')
            regional_plddt = [{'input_interval': [lo,hi], 'mean_raw_plddt':float(plddt[lo-1:hi].mean())}
                              for lo,hi in ((1,20),(21,36),(37,231),(232,236),(237,296))]
        directions = [r for r in metrics['ipsae']['pairwise'] if r['type'] == 'asym']
        require([(r['chain1'],r['chain2']) for r in directions] == [('A','B'),('B','A')], 'Directional score mapping differs')
        require(math.isfinite(metrics['iptm']) and all(math.isfinite(r['ipsae']) for r in directions), 'Nonfinite scores')
        pose = read_pair(pred / 'model.cif', target['sequence'], candidate['sequence'], list(range(1, 237)))
        poses[(model, seed)] = pose
        cases.append({'predictor': model, 'prediction_seed': seed, 'status': 'success', 'iptm': metrics['iptm'],
            'ipsae_target_to_binder': directions[0]['ipsae'], 'ipsae_binder_to_target': directions[1]['ipsae'],
            'generator_to_refold': align_pair(pose, generated, anchors),
            'heavy_atom_pairs_lt_2A': pose['heavy_atom_pairs_lt_2A'],
            'target_contacts_lt_5A': pose['target_contacts_lt_5A'],
            'esm_raw_plddt_regions':regional_plddt, 'submission_eligible': False})
require(len(runtime['predictions']) == 2 and {r['seed'] for r in runtime['predictions']} == {1,2},
        'Recovery must account for both missing seeds exactly once')
for row in runtime['predictions']:
    require(row['status'] == 'success' and row['seed'] in (1,2), 'Missing successful recovered seed')
    case = folder / f'predictions-v1/seed-{row["seed"]}'
    for filename, expected in row['persisted_output_sha256'].items():
        keep(case / filename, expected)
pairs = []
for a,b in itertools.combinations(sorted(poses), 2):
    first, second = set(poses[a]['target_contacts_lt_5A']), set(poses[b]['target_contacts_lt_5A'])
    pairs.append({'left': {'model': a[0], 'seed': a[1]}, 'right': {'model': b[0], 'seed': b[1]},
        'core_alignment': align_pair(poses[a], poses[b], anchors),
        'complete_target_alignment': align_pair(poses[a], poses[b], list(range(1,237))),
        'regional_target_differences_after_core_fit': target_region_differences(poses[a], poses[b], anchors),
        'target_contact_jaccard': len(first&second)/len(first|second) if first|second else None})
for directory in ('cpu-qualification-v1', 'predictions-v1', 'slurm'):
    for path in sorted((folder / directory).rglob('*')):
        if path.is_file() and path.suffix in {'.log','.out','.err','.csv','.json'}:
            keep(path)
for name in ('scripts/assemble-esm-recovery-review.py', 'binder_campaign/pose_review.py'):
    keep(w / 'pipeline' / name)
keep(w / 'outputs/esm-startup-recovery-plan-2026-11-02.md')
result = {'candidate_id': candidate['candidate_id'], 'six_prediction_results': cases,
    'pairwise_geometry': pairs, 'previous_failed_attempts': [r for r in previous['prediction_attempts'] if r['status'] == 'failed'],
    'runtime_qualification': {'cpu': qualification, 'gpu': runtime},
    'gpu_budget': {'seconds': int(elapsed), 'cap_seconds': 900, 'maximum_concurrency': 1, 'job_id': job},
    'sequence_context_review_unchanged': previous['sequence_context'],
    'decision': 'Keep seed43 as cleaner research baseline; seed101 has completed robustness checks but retains Cys25/sequon concerns',
    'scope': 'Sampling consistency only; no measured binding, affinity, expression, glycan tolerance or official admission',
    'submission_eligible_count': 0}
out.mkdir(parents=True)
write_json(out / 'review.json', result)
fields = ['predictor','prediction_seed','iptm','ipsae_target_to_binder','ipsae_binder_to_target',
          'generator_to_refold_binder_rmsd_A','heavy_atom_pairs_lt_2A','submission_eligible']
with (out / 'REHEARSAL_ONLY_scores.csv').open('x', newline='') as stream:
    writer = csv.DictWriter(stream, fields)
    writer.writeheader()
    for row in cases:
        writer.writerow({**{k:row[k] for k in fields if k in row}, 'submission_eligible':'false',
                         'generator_to_refold_binder_rmsd_A':row['generator_to_refold']['target_aligned_binder_ca_rmsd_A']})
with (out / 'EMPTY_submission_shortlist.csv').open('x', newline='') as stream:
    csv.writer(stream).writerow(['candidate_id','target_id','sequence','submission_eligible'])
(out / 'REVIEW.md').write_text('''# ESMFold2 recovery and seed101 robustness review

The two missing ESMFold2 seeds completed using staged copies of the existing
runtime and pinned checkpoint. Both original failed attempts remain in the
evidence. Six predictions (three seeds per evaluator) are now available.

Checkpoint and MSA hashes, adapter bytes and scientific request settings were
checked. Only runtime file paths changed. Each seed ran in a fresh Python
process, sequentially in one allocation. CPU and GPU probes confirmed imports
from the local environment and verified every archived file. This establishes
the tested staging route; it is not a general throughput or numerical-equivalence
benchmark across hardware/cache states.

New GPU allocation: {seconds}seconds ({minutes:.2f}minutes), below900seconds,
maximum concurrency one. CPU preparation is accounted separately. Full raw PAE,
structures, directional scores, independent Bio.PDB/direct-SVD pose diagnostics
and timing records are preserved in `review.json`.

Seed101 remains research-only with Cys25 and NLS18/NIS29 context concerns.
Seed43 remains the cleaner repeat-tested baseline;103/105 remain backups.
Read raw geometry/scores before making a later selection decision. No measured
binding, affinity, expression, glycan compatibility or submission eligibility
is established. The submission shortlist is empty.

Next: broaden reviewed binding-region coverage, preserve sequence/context
review, and keep official assay/screen uncertainties explicit before scaling.

Core consistency does not imply whole-target rigidity. Aligning all236 target
residues gives binder differences up to16.55Å. In the worst pair (ESMFold2
seeds0/1), the core fits at0.58Å, while residues1–20 differ by59.4Å RMSD after
core fitting. The ESMFold2 mean raw pLDDT for1–20 is0.286–0.344 and for21–36
0.388–0.429, versus0.924–0.928 for37–231. UniProt annotates a signal peptide
at1–20, but actual competition processing is unconfirmed. The complete target
and both alignment conventions remain preserved; no trimming or assay-readiness
claim follows from choosing a core-alignment diagnostic.
'''.format(seconds=int(elapsed),minutes=int(elapsed)/60))
write_json(out / 'manifest.json', {'source_sha256':dict(sorted(sources.items())),
    'output_sha256':{p.name:digest(p) for p in sorted(out.iterdir()) if p.is_file()},
    'submission_eligible_count':0, 'official_submission_schema':False})
print(json.dumps({'status':'reviewed', 'sources':len(sources), 'six_predictions':len(cases), 'gpu_seconds':int(elapsed)}))
