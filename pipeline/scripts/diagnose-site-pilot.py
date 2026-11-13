"""Separate binder intrinsic-shape changes from target-relative pose changes."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
from Bio.PDB import Superimposer
from Bio.PDB.Atom import Atom
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest,write_json
from binder_campaign.pose_review import read_pair
parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();w=args.workspace.resolve();e=w/'outputs/execution-evidence'
package=w/'outputs/site-pilot-review-2026-11-02-v1';data=json.loads((package/'review.json').read_text())
target=json.loads((w/'pipeline/data/targets/il7ra/manifest.json').read_text())['sequence'];rows=[];sources={}
for case in data['cases']:
    directory=e/f'site-{case["case"]}-v1';record=json.loads((directory/'candidates.json').read_text())['candidates'][0]
    reference=record['generator_audit']['reference_audit'];path=directory/'prediction/model.cif'
    gen=read_pair(path,reference['reference_sequence'],record['sequence'],reference['positions'])['binder_ca']
    sources[str(path.relative_to(w))]=digest(path)
    for model in ('esmfold2','boltz'):
        path=e/f'site-{case["case"]}-{model}-v1/prediction/model.cif'
        predicted=read_pair(path,target,record['sequence'],list(range(1,237)))['binder_ca']
        sources[str(path.relative_to(w))]=digest(path)
        atoms=lambda xs:[Atom('CA',x,0.,1.,' ',' CA ',i,element='C') for i,x in enumerate(xs)]
        fit=Superimposer();fit.set_atoms(atoms(gen),atoms(predicted))
        a=gen-gen.mean(0);b=predicted-predicted.mean(0);u,_,vt=np.linalg.svd(b.T@a)
        if np.linalg.det(u@vt)<0:u[:,-1]*=-1
        direct=float(np.sqrt(np.mean(np.sum((b@(u@vt)-a)**2,axis=1))))
        if not np.isclose(direct,fit.rms,atol=1e-6,rtol=0):raise ValueError('Independent shape fits disagree')
        rows.append({'case':case['case'],'model':model,'binder_only_CA_rmsd_A':float(fit.rms),
            'target_aligned_binder_CA_rmsd_A':case['models'][model]['generator_to_refold']['target_aligned_binder_ca_rmsd_A'],
            'native_hotspots_contacted':len(case['generation_hotspots_contacted']),
            'refold_hotspots_contacted':len(case['models'][model]['declared_hotspots_contacted'])})
if args.output.exists():raise ValueError('Use a fresh diagnostic artifact')
write_json(args.output,{'status':'verified','rows':rows,'source_sha256':sources,'script_sha256':digest(__file__),
    'scope':'Same-sequence CA self-fit versus target-relative fit. Shape differences do not establish experimental unfolding or nonbinding.'})
print(json.dumps(rows,indent=2))
