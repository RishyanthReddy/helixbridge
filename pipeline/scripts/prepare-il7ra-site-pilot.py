"""Prepare unexecuted equal-hotspot-count research arms from reviewed patches."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
from Bio.PDB.MMCIF2Dict import MMCIF2Dict

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest,write_json
from binder_campaign.structure import AA3

parser=argparse.ArgumentParser()
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--output-dir',type=Path,required=True)
args=parser.parse_args();w=args.workspace.resolve();out=args.output_dir.resolve()
if out.exists():raise ValueError('Use a fresh proposal directory')
source=w/'outputs/il7ra-diversity-2026-11-02-v2'
diversity=json.loads((source/'diversity.json').read_text())
reference=w/'pipeline/data/targets/il7ra/rfd4-reference'
audit=json.loads((reference/'audit.json').read_text())
data=MMCIF2Dict(str(reference/'target.cif'))
indices=[i for i,n in enumerate(data['_atom_site.label_atom_id']) if n=='CA']
positions=[int(data['_atom_site.label_seq_id'][i]) for i in indices]
sequence=''.join(AA3[data['_atom_site.label_comp_id'][i]] for i in indices)
if positions!=audit['positions'] or sequence!=audit['reference_sequence']:
    raise ValueError('Target reference mapping changed')
coords={p:np.array([float(data[k][i]) for k in ('_atom_site.Cartn_x','_atom_site.Cartn_y','_atom_site.Cartn_z')])
        for p,i in zip(positions,indices)}
out.mkdir(parents=True);arms=[]
for label,center in [('control',None),('patch139',139),('patch72',72)]:
    hotspots=audit['hotspots_uniprot']
    if center:
        patch=next(p for p in diversity['surface']['proposed_patches'] if p['center']==center)
        hotspots=sorted(sorted(patch['positions'],key=lambda p:(float(np.linalg.norm(coords[p]-coords[center])),p))[:10])
    if len(hotspots)!=10 or not set(hotspots)<=set(positions):raise ValueError('Invalid matched hotspot count')
    folder=out/label;folder.mkdir()
    (folder/'target.cif').write_bytes((reference/'target.cif').read_bytes())
    spec=json.loads((reference/'conditions.json').read_text())
    spec['il7ra']['input']='target.cif'
    spec['il7ra']['conditions']['C_HOT']['true'][0]['select']="sel('A/*/["+','.join(map(str,hotspots))+"]')"
    write_json(folder/'conditions.json',spec)
    write_json(folder/'audit.json',{**audit,'hotspots_uniprot':hotspots,
        'files':{'target.cif':digest(folder/'target.cif'),'conditions.json':digest(folder/'conditions.json')},
        'proposal_status':'not_run; current adapter does not enable proposed seeds201/202'})
    arms.append({'arm':label,'hotspots_uniprot':hotspots,'generation_seeds':[201,202],
                 'reference_audit':label+'/audit.json','status':'proposed_not_run'})
write_json(out/'plan.json',{'arms':arms,'design_count':6,'binder_length':60,'recycle_strategy':'thinking_high',
    'model_revision':'621b785abf9d61dd24f4b81ae4dbd1330728f030','gpu_seconds_proposed_cap':5400,
    'max_concurrent_gpus_proposed':2,'pilot_gate_cases':['control/201','patch139/201'],
    'common_evaluation':'Full236-residue target; no binder MSA or template; existing ESMFold2 and Boltz recipes',
    'execution_gate':'Adapter/input and Slurm review required; no execution authorized by this preparation artifact',
    'source_diversity_sha256':digest(source/'diversity.json'),'submission_eligible_count':0})
write_json(out/'manifest.json',{'source_sha256':{str(p.relative_to(w)):digest(p) for p in
    [source/'diversity.json',reference/'target.cif',reference/'audit.json',reference/'conditions.json',Path(__file__).resolve()]},
    'output_sha256':{str(p.relative_to(out)):digest(p) for p in sorted(out.rglob('*')) if p.is_file()}})
print(json.dumps({'status':'prepared_not_run','arms':arms},indent=2))
