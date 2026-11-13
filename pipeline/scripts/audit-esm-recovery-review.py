"""Check a frozen recovery package using standard-library hash/CSV controls."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root, entries):
    for name, expected in entries.items():
        if sha(root / name) != expected:
            raise ValueError('Changed artifact: ' + name)


parser = argparse.ArgumentParser()
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--package', type=Path, required=True)
parser.add_argument('--reproduction', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
w, package, reproduction = (p.resolve() for p in (args.workspace, args.package, args.reproduction))
manifest = json.loads((package / 'manifest.json').read_text())
verify(w, manifest['source_sha256'])
verify(package, manifest['output_sha256'])
verify(reproduction, manifest['output_sha256'])
if (package / 'manifest.json').read_bytes() != (reproduction / 'manifest.json').read_bytes():
    raise ValueError('Reproduction differs')
review = json.loads((package / 'review.json').read_text())
with (package / 'REHEARSAL_ONLY_scores.csv').open(newline='') as stream:
    rows = list(csv.DictReader(stream))
with (package / 'EMPTY_submission_shortlist.csv').open(newline='') as stream:
    shortlist = list(csv.DictReader(stream))
if len(rows) != 6 or {(r['predictor'],r['prediction_seed']) for r in rows} != {
        (model,str(seed)) for model in ('esmfold2','boltz') for seed in (0,1,2)}:
    raise ValueError('Six unique predictor/seed results required')
if shortlist or any(r['submission_eligible'] != 'false' for r in rows) or review['submission_eligible_count']:
    raise ValueError('Submission eligibility guard failed')
if len(review['previous_failed_attempts']) != 2 or not 0 < review['gpu_budget']['seconds'] <= 900:
    raise ValueError('Failures or resource accounting disappeared')
negative = {}
with tempfile.TemporaryDirectory() as name:
    root = Path(name)
    path = root / 'artifact'
    path.write_bytes(b'input')
    expected = {'artifact':sha(path)}
    verify(root,expected)
    path.write_bytes(b'changed')
    try:
        verify(root,expected)
    except ValueError:
        negative['changed_payload'] = 'rejected'
    else:
        raise ValueError('Tampered artifact accepted')
result = {'status':'passed', 'sources_checked':len(manifest['source_sha256']),
    'payloads_checked':len(manifest['output_sha256']), 'byte_identical_reproduction':True,
    'successful_prediction_rows':len(rows), 'old_failed_attempts_preserved':2,
    'submission_shortlist_count':0, 'gpu_seconds':review['gpu_budget']['seconds'],
    'negative_controls':negative, 'audit_script_sha256':sha(Path(__file__))}
with args.output.open('x') as stream:
    stream.write(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
