"""Anonymous pinned generation-only assets; do not download evaluator models."""
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request
from huggingface_hub import hf_hub_download
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest,write_json
root=Path(os.environ['TASK_ROOT']);out=root/'results/boltzgen-reserve-v1';out.mkdir(exist_ok=True)
files=[]
for repo,revision,name,kind in [
    ('boltzgen/boltzgen-1','c1be29e1f82ffcc72264f64b993c43fb4e0d17f0','boltzgen1_adherence.ckpt','model'),
    ('boltzgen/inference-data','c3d36fd276e9caf098c75d4113c6d5eb320b1a4c','mols.zip','dataset')]:
    path=Path(hf_hub_download(repo,name,revision=revision,repo_type=kind,token=False))
    files.append({'repo':repo,'revision':revision,'name':name,'path':str(path),'sha256':digest(path),'bytes':path.stat().st_size})
directory=root/'data/weights/boltzgen';directory.mkdir(exist_ok=True)
path=directory/'solublempnn_v_48_020.pt'
if not path.exists():urllib.request.urlretrieve('https://files.ipd.uw.edu/pub/ligandmpnn/solublempnn_v_48_020.pt',path)
expected='7af52d090172c230c7f0e9d21e02203f6b3a38b16db58d3c7a3960e0a9a6e31a'
if digest(path)!=expected:raise ValueError('SolubleMPNN upstream checksum differs')
files.append({'repo':'upstream SolubleMPNN','name':path.name,'path':str(path),'sha256':expected,'bytes':path.stat().st_size})
write_json(out/'assets.json',{'access':'anonymous','source_revision':'6472b44e8072187e6eaa51271ae6838245206013',
    'scope':'Generation adherence checkpoint, chemical components and SolubleMPNN only','files':files,
    'script_sha256':digest(__file__),'submission_eligible':False})
print(json.dumps({'status':'downloaded_and_hashed','files':[{'name':f['name'],'bytes':f['bytes']} for f in files]}),flush=True)
