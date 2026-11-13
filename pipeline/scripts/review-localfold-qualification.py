"""Independently check LocalFold exports and apply the predeclared native-parity gate."""
import argparse
import json
from pathlib import Path
import sys
parser=argparse.ArgumentParser()
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args();w=args.workspace.resolve()
sys.path.insert(0,str(w/'pipeline'))
import numpy as np
from Bio.PDB import PDBParser,Superimposer
from binder_campaign.runner import digest,write_json
from binder_campaign.structure import AA3
e=w/'outputs/execution-evidence'
output=e/'localfold-qualification-review-v1'
if output.exists():raise ValueError('Use a fresh qualification review')
cases=[]
for folder in ['localfold-il7-control-v1','localfold-seed43-v1','localfold-seed44-v1']:
    p=e/folder;a=json.loads((p/'audit.json').read_text());raw=json.loads((p/'raw.json').read_text())
    request=json.loads((p/'input.json').read_text())
    expected=[request['target']['sequence'],request['partner']['sequence']]
    model=PDBParser(QUIET=True).get_structure('fold',p/'model.pdb')
    models=list(model.get_models());assert len(models)==1
    chains=list(models[0].get_chains())
    sequences=[''.join(AA3[r.resname] for r in chain.get_residues()) for chain in chains]
    assert sequences==expected and all(np.isfinite(atom.coord).all() for atom in models[0].get_atoms())
    assert all('CA' in residue for chain in chains for residue in chain.get_residues())
    n=sum(map(len,expected));pae=np.asarray(raw['pae']).reshape(n,n)
    assert np.isfinite(pae).all() and len(raw['plddt'])==n
    for filename,sha in a['artifacts'].items():assert digest(p/filename)==sha
    sources=[w/'pipeline/scripts/localfold-qualify.mjs',*(e/'localfold-adapters').glob('*.mjs')]
    assert any(digest(path)==a['adapter_sha256'] for path in sources),'Executed adapter source unavailable'
    archive=p/'archive-with-msa-v2'
    full=json.loads((archive/'localfold_qualification_full_data_0.json').read_text())
    assert full['token_chain_ids']==['A']*len(expected[0])+['B']*len(expected[1])
    assert full['token_res_ids']==list(range(1,len(expected[0])+1))+list(range(1,len(expected[1])+1))
    exported=np.asarray(full['pae']);assert exported.shape==pae.shape and np.max(abs(exported-pae))<=.00501
    repair=json.loads((p/'archive-repair-audit.json').read_text())
    assert repair['round_trip_checked'] and digest(p/'complex.a3m')==repair['added_alignment_sha256']
    assert digest(archive/'msas/localfold_qualification_merged_msa.a3m')==digest(p/'complex.a3m')
    cases.append({'case':folder,'iptm':a['iptm'],'ptm':a['ptm'],'encoding':a['encoding'],
        'elapsed_seconds':a['elapsed_seconds'],'mapping_and_archive_checks':'passed',
        'audit_sha256':digest(p/'audit.json')})
native=e/'localfold-native-oracle-v2'
ref=json.loads((native/'reference.json').read_text())
policy=json.loads((native/'comparison-policy.json').read_text())
comparisons=[]
for name in ['localfold-native-f32-comparison-v3','localfold-native-f32-comparison-v4','localfold-native-int5-comparison-v1']:
    path=e/name;raw=json.loads((path/'raw.json').read_text());audit=json.loads((path/'audit.json').read_text())
    assert audit['input_sha256']==digest(native/'inputs.json')
    x=np.asarray(raw['ca']).reshape(-1,3);y=np.asarray(ref['ca']).reshape(-1,3)
    xc=x-x.mean(0);yc=y-y.mean(0);u,_,vt=np.linalg.svd(xc.T@yc)
    u[:,-1]*=np.linalg.det(u@vt)
    rmsd=float(np.sqrt(np.sum((xc@(u@vt)-yc)**2,axis=-1).mean()))
    pair=np.asarray(raw['pair']);target=np.asarray(ref['pair'])
    relative=float(np.linalg.norm(pair-target)/np.linalg.norm(target))
    checks=policy['float32_numerical_checks']
    passed=(relative<=checks['pair_representation_relative_rms_max'] and rmsd<=checks['aligned_ca_rmsd_angstrom_max'])
    comparisons.append({'case':name,'encoding':audit['encoding'],'compute_precision':audit['settings'].get('compute_precision','auto'),
        'pair_relative_rms':relative,'aligned_ca_rmsd_angstrom':rmsd,
        'meets_declared_float32_gate':passed if audit['encoding']=='float32-le' else None,
        'raw_sha256':digest(path/'raw.json')})
decision={'status':'assessed','submission_eligible':False,'diagnostic_cases':cases,'native_comparisons':comparisons,
    'decision':'defer_as_ranking_stage; optional inspection only',
    'native_reference_qualified':all(c['meets_declared_float32_gate'] is True for c in comparisons if c['encoding']=='float32-le'),
    'reason':'Export/mapping checks pass, but numerical agreement misses the predeclared native gate; automatic/mixed precision and int5 diverge further. Low natural-control score and a high held-candidate score do not validate binder classification.',
    'limitations':'Synthetic 16-residue reference and three diagnostic complexes; not a binder accuracy benchmark. Source, precision, checkpoint and preprocessing differences require further diagnosis before score-based integration.',
    'policy_sha256':digest(native/'comparison-policy.json'),'native_reference_sha256':digest(native/'reference.json')}
output.mkdir();write_json(output/'decision.json',decision)
print(json.dumps(decision,indent=2))
