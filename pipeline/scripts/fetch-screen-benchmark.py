"""Fetch only pinned public evaluation tables/docs, never generator starting inputs."""
import hashlib
import json
import os
from pathlib import Path

from huggingface_hub import hf_hub_download
import pandas as pd

root=Path(os.environ['TASK_ROOT'])
repo='Anthropic/claude-protein-binder-design'
revision='9e1b81696da46835e9e9cde9a3da976e0abc92ab'
files=['data/tables/design_summary.parquet','data/tables/insilico/cofold_predictions.parquet',
       'data/tables/wetlab/summary.parquet','data/tables/column_dictionary.parquet',
       'data/docs/LOOKUP_TABLES.md','data/docs/WETLAB.md','data/docs/INSILICO.md',
       'data/docs/DATA_NOTES.md','data/LICENSE.md','data/README.md']
out=root/'data/benchmarks/claude-protein-binder-design'/revision
out.mkdir(parents=True,exist_ok=True)
record={'repo':repo,'revision':revision,'purpose':'evaluation_only_not_generator_input',
        'access':'anonymous','files':{}}
for name in files:
    cached=Path(hf_hub_download(repo,filename=name,repo_type='dataset',revision=revision,token=False))
    path=out/name
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists(): path.symlink_to(cached)
    if path.resolve()!=cached.resolve(): raise ValueError('Different benchmark artifact already present')
    h=hashlib.sha256(path.read_bytes()).hexdigest()
    entry={'sha256':h,'bytes':path.stat().st_size}
    if name.endswith('.parquet'):
        frame=pd.read_parquet(path)
        entry['rows']=len(frame);entry['columns']=frame.columns.tolist()
        print(name,len(frame),'rows',frame.columns.tolist(),flush=True)
        if 'target' in frame:
            print('targets',sorted(frame['target'].dropna().unique().tolist()),flush=True)
        if 'predictor' in frame:
            for col in ['predictor','seed','stoich','target_form']:
                if col in frame: print(col,frame[col].dropna().unique().tolist()[:35],flush=True)
    record['files'][name]=entry
(out/'download-audit.json').write_text(json.dumps(record,indent=2)+'\n')
print('Pinned evaluation tables/docs downloaded; no structures/PAE corpus or generator inputs fetched',flush=True)
