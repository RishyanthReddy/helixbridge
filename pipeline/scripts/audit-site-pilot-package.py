"""Independent artifact/CSV/resource checks for the complete paired pilot."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import tempfile
parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--package',type=Path,required=True)
parser.add_argument('--reproduction',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();w=args.workspace.resolve();p=args.package.resolve();q=args.reproduction.resolve()
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def verify(root,entries):
    for name,value in entries.items():
        if sha(root/name)!=value:raise ValueError('Changed artifact: '+name)
m=json.loads((p/'manifest.json').read_text());verify(w,m['source_sha256']);verify(p,m['output_sha256'])
for name in ('review.json','REHEARSAL_ONLY_scores.csv','EMPTY_submission_shortlist.csv'):
    if (p/name).read_bytes()!=(q/name).read_bytes():raise ValueError('Numeric/CSV reproduction differs')
review=json.loads((p/'review.json').read_text())
with (p/'REHEARSAL_ONLY_scores.csv').open(newline='') as stream:rows=list(csv.DictReader(stream))
with (p/'EMPTY_submission_shortlist.csv').open(newline='') as stream:shortlist=list(csv.DictReader(stream))
if len(rows)!=12 or len(review['cases'])!=6 or shortlist or any(r['submission_eligible']!='false' for r in rows):raise ValueError('CSV/count/eligibility guard failed')
if review['budget']['seconds']>5400 or review['budget']['maximum_concurrency']>2:raise ValueError('Resource envelope exceeded')
if any(r['public_overlap_flags'] for r in review['cases']):raise ValueError('Review unexpected public duplicate flag')
negative={}
with tempfile.TemporaryDirectory() as name:
    root=Path(name);path=root/'input';path.write_bytes(b'original');expected={'input':sha(path)}
    verify(root,expected);path.write_bytes(b'changed')
    try:verify(root,expected)
    except ValueError:negative['changed_artifact']='rejected'
    else:raise ValueError('Negative control accepted changed input')
result={'status':'passed','source_hashes_checked':len(m['source_sha256']),'output_hashes_checked':len(m['output_sha256']),
    'numeric_and_csv_reproduction_byte_identical':True,'all_cases':6,'predictor_rows':12,
    'gpu_seconds':review['budget']['seconds'],'maximum_concurrency':review['budget']['maximum_concurrency'],
    'submission_shortlist_count':0,'conditional_followup_case':review['conditional_followup_case'],
    'negative_controls':negative,'script_sha256':sha(Path(__file__))}
with args.output.open('x') as stream:stream.write(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
