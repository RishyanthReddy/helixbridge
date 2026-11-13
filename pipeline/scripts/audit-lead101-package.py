"""Independent standard-library artifact/CSV checks for the completed bounded review."""
import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_hashes(root, expected):
    for name, value in expected.items():
        if sha(root / name) != value:
            raise ValueError('Changed artifact: ' + name)


parser = argparse.ArgumentParser()
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--package', type=Path, required=True)
parser.add_argument('--reproduction', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
w, package, reproduction = (p.resolve() for p in (args.workspace, args.package, args.reproduction))
manifest = json.loads((package / 'manifest.json').read_text())
verify_hashes(w, manifest['source_sha256'])
verify_hashes(package, manifest['output_sha256'])
verify_hashes(reproduction, manifest['output_sha256'])
if (package / 'manifest.json').read_bytes() != (reproduction / 'manifest.json').read_bytes():
    raise ValueError('Reproduction manifest differs')
record = json.loads((package / 'checkpoint.json').read_text())
with (package / 'REHEARSAL_ONLY_prediction_attempts.csv').open(newline='') as stream:
    rows = list(csv.DictReader(stream))
with (package / 'EMPTY_submission_shortlist.csv').open(newline='') as stream:
    shortlist = list(csv.DictReader(stream))
if len(rows) != 6 or shortlist or any(r['submission_eligible'] != 'false' for r in rows):
    raise ValueError('Diagnostic CSV or empty-shortlist guard failed')
failed = [r for r in rows if r['status'] == 'failed']
if {(r['predictor'], r['prediction_seed']) for r in failed} != {('esmfold2', '1'), ('esmfold2', '2')}:
    raise ValueError('Unexpected missing-result pattern')
if any(r[field] for r in failed for field in ['iptm', 'ipsae_target_to_binder', 'ipsae_binder_to_target',
                                             'generator_to_refold_binder_ca_rmsd_A', 'heavy_atom_pairs_lt_2A']):
    raise ValueError('A failed prediction was converted to a numeric score')
if record['budget']['gpu_seconds'] != 1139 or record['budget']['maximum_concurrency'] != 2 \
        or record['submission_eligible_count'] != 0:
    raise ValueError('Budget/eligibility changed')
for row in record['sequence_context']['research_followups']:
    public = row['public_reference_comparison']
    if public['rows_compared'] != 1684 or public['exact_duplicates'] or public['over_90pct_contiguous_flags']:
        raise ValueError('Public-reference diagnostic differs')
negative_controls = {}
with tempfile.TemporaryDirectory() as name:
    root = Path(name)
    path = root / 'artifact'
    path.write_bytes(b'original')
    expected = {'artifact': sha(path)}
    verify_hashes(root, expected)
    for label in ['changed_input', 'changed_output']:
        path.write_bytes(label.encode())
        try:
            verify_hashes(root, expected)
        except ValueError:
            negative_controls[label] = 'rejected'
        else:
            raise ValueError('Negative control did not reject a changed artifact')
reference = w / 'work/validation-data/9e1b81696da46835e9e9cde9a3da976e0abc92ab/data/tables/design_summary.parquet'
download = w / 'work/lead101-design-summary-remote-verification.parquet'
if sha(reference) != sha(download):
    raise ValueError('Fresh anonymous pinned public source differs from cached evaluation table')
result = {'status': 'passed_artifact_checks; scientific_advancement_gate_not_met',
    'package': str(package), 'sources_checked': len(manifest['source_sha256']),
    'payloads_checked': len(manifest['output_sha256']), 'byte_identical_reproduction': True,
    'diagnostic_rows': len(rows), 'failed_prediction_rows_preserved_without_numeric_scores': len(failed),
    'submission_shortlist_count': 0, 'gpu_seconds': 1139,
    'negative_controls': negative_controls,
    'fresh_anonymous_pinned_hf_source_sha256': sha(download),
    'verification_script_sha256': sha(Path(__file__))}
with args.output.open('x') as stream:
    stream.write(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
