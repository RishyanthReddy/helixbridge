"""Export existing pinned public sequences for evaluation-only novelty diagnostics."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest, write_json

parser = argparse.ArgumentParser()
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--output-dir', type=Path, required=True)
args = parser.parse_args()
workspace = args.workspace.resolve()
out = args.output_dir.resolve()
if out.exists():
    raise ValueError('Use a fresh reference export directory')
revision = '9e1b81696da46835e9e9cde9a3da976e0abc92ab'
source = workspace / f'work/validation-data/{revision}/data/tables/design_summary.parquet'
rows = []
sources = {str(source.relative_to(workspace)): digest(source)}
excluded = []
for row in pd.read_parquet(source).to_dict('records'):
    if row['target'] in {'BHRF1', 'Nipah-G', 'Cas9', 'MBP'}:
        excluded.append({'source': 'claude-protein-binder-design', 'id': row['uuid'],
                         'reason': 'outside the previously reviewed benign-target evaluation scope'})
        continue
    rows.append({'source': 'claude-protein-binder-design', 'id': row['uuid'],
                 'target': row['target'], 'sequence': row['sequence']})
references = [{'repo': 'Anthropic/claude-protein-binder-design', 'revision': revision,
               'url': f'https://huggingface.co/datasets/Anthropic/claude-protein-binder-design/tree/{revision}',
               'file': str(source.relative_to(workspace))}]
for number in (1, 2):
    folder = workspace / f'work/review/adaptyvbio__egfr_competition_{number}'
    tree_path = folder / 'tree.json'
    tree = json.loads(tree_path.read_text())
    path = folder / 'results__result_summary.csv'
    data = path.read_bytes()
    expected = [r['sha'] for r in tree['tree'] if r['path'] == 'results/result_summary.csv']
    actual = hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
    if expected != [actual]:
        raise ValueError('Cached public CSV does not match pinned Git tree')
    for index, row in enumerate(csv.DictReader(path.open(newline=''))):
        sequence = ''.join(row['sequence'].split()).upper()
        if not sequence or set(sequence) - set('ACDEFGHIKLMNPQRSTVWY'):
            excluded.append({'source': f'adaptyv-egfr-{number}', 'id': str(index),
                             'reason': 'empty/nonstandard amino-acid sequence'})
            continue
        rows.append({'source': f'adaptyv-egfr-{number}', 'id': str(index),
                     'target': 'EGFR', 'sequence': sequence})
    sources[str(path.relative_to(workspace))] = digest(path)
    sources[str(tree_path.relative_to(workspace))] = digest(tree_path)
    references.append({'repo': f'adaptyvbio/egfr_competition_{number}', 'revision': tree['sha'],
                       'url': f'https://github.com/adaptyvbio/egfr_competition_{number}/blob/{tree["sha"]}/results/result_summary.csv',
                       'file': str(path.relative_to(workspace))})
if any(not r['sequence'] or set(r['sequence']) - set('ACDEFGHIKLMNPQRSTVWY') for r in rows):
    raise ValueError('Invalid exported reference sequence')
rows.sort(key=lambda r: (r['source'], r['id']))
out.mkdir(parents=True)
write_json(out / 'corpus.json', {'rows': rows, 'references': references,
    'excluded': excluded, 'scope': 'Evaluation only; never generator input; limited public corpus, not global novelty'})
write_json(out / 'manifest.json', {'sources': sources, 'outputs': {'corpus.json': digest(out / 'corpus.json')},
    'row_count': len(rows), 'unique_sequences': len({r['sequence'] for r in rows}),
    'excluded_count': len(excluded), 'script_sha256': digest(__file__)})
print(json.dumps({'status': 'exported', 'rows': len(rows),
                  'unique_sequences': len({r['sequence'] for r in rows}), 'excluded': len(excluded)}))
