"""Independent Bio.PDB alignment audit of the initial rehearsal's pose discrepancy."""
import json
import os
from pathlib import Path
import sys
import re

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from Bio.PDB import Superimposer
from Bio.PDB.Atom import Atom
from Bio.PDB.MMCIF2Dict import MMCIF2Dict
from binder_campaign.runner import write_json, digest
from binder_campaign.structure import AA3

root=Path(os.environ['TASK_ROOT'])
campaign=sys.argv[1] if len(sys.argv)>1 else 'rfd4-il7ra'
if not re.fullmatch(r'[a-z0-9-]+',campaign): raise ValueError('Invalid campaign stem')
records_path=Path(sys.argv[2]) if len(sys.argv)>2 else root/f'results/{campaign}-v1/candidates.json'
record=json.loads(records_path.read_text())['candidates'][0]
review_path=root/f'results/{campaign}-review-v1/review.json'
review=json.loads(review_path.read_text())
if review['candidate_id']!=record['candidate_id'] or review['candidate_records_sha256']!=digest(records_path):
    raise ValueError('Candidate and review records disagree')
if digest(record['generator_structure'])!=record['generator_structure_sha256']:
    raise ValueError('Generator structure changed')
for model in ['esmfold2','boltz']:
    if digest(root/f'results/{campaign}-{model}-v1/prediction/model.cif')!=review['predictions'][model]['model_cif_sha256']:
        raise ValueError('Prediction structure changed: '+model)
reference=record['generator_audit']['reference_audit']
alignment_positions=reference.get('alignment_positions',reference['positions'])
target=json.loads((root/'src/pipeline/data/targets/il7ra/manifest.json').read_text())

def chains(path, tsequence, mapping):
    # Native generated CIFs omit B factors, which MMCIFParser requires. Read
    # raw fields independently and give CA objects a dummy B factor solely for
    # Superimposer's coordinate API; no confidence is inferred or file repaired.
    data=MMCIF2Dict(path)
    xyz=np.array([data['_atom_site.Cartn_x'],data['_atom_site.Cartn_y'],data['_atom_site.Cartn_z']],dtype=float).T
    atom_names=np.array(data['_atom_site.label_atom_id'])
    chain_ids=np.array(data['_atom_site.label_asym_id'])
    res_ids=np.array(data['_atom_site.label_seq_id'])
    names=np.array(data['_atom_site.label_comp_id'])
    elements=np.array(data['_atom_site.type_symbol'])
    ca=atom_names=='CA'
    sequences={c:''.join(AA3[n] for n in names[ca & (chain_ids==c)]) for c in dict.fromkeys(chain_ids.tolist())}
    tc=[c for c,seq in sequences.items() if seq==tsequence]
    bc=[c for c,seq in sequences.items() if seq==record['sequence']]
    if len(tc)!=1 or len(bc)!=1: raise ValueError('Ambiguous sequence mapping')
    tmask=chain_ids==tc[0];bmask=chain_ids==bc[0]
    td=dict(zip(res_ids[ca & tmask],mapping))
    bd={res:i+1 for i,res in enumerate(res_ids[ca & bmask])}
    heavy=(elements!='H') & (elements!='D')
    ti=np.where(tmask & heavy)[0];bi=np.where(bmask & heavy)[0]
    d=np.linalg.norm(xyz[ti][:,None,:]-xyz[bi][None,:,:],axis=-1)
    contacts={(td[res_ids[ti[i]]],bd[res_ids[bi[j]]]) for i,j in zip(*np.where(d<5.0))}
    def ca_atoms(mask):
        return [Atom('CA',coord,0.0,1.0,' ',' CA ',i,element='C') for i,coord in enumerate(xyz[ca & mask])]
    return {'target':ca_atoms(tmask),'binder':ca_atoms(bmask),'contacts':contacts}

generator=chains(record['generator_structure'],reference['reference_sequence'],reference['positions'])
predicted={m:chains(root/f'results/{campaign}-{m}-v1/prediction/model.cif',target['sequence'],list(range(1,237)))
           for m in ['esmfold2','boltz']}
results={}
for name,pose in predicted.items():
    fixed=[pose['target'][i-1] for i in alignment_positions]
    moving=[generator['target'][reference['positions'].index(i)] for i in alignment_positions]
    fit=Superimposer();fit.set_atoms(fixed,moving)
    rot,tran=fit.rotran
    transformed=np.array([a.coord for a in generator['binder']])@rot+tran
    rmsd=float(np.sqrt(np.mean(np.sum((transformed-np.array([a.coord for a in pose['binder']]))**2,axis=-1))))
    union=generator['contacts']|pose['contacts']
    results[name]={'target_fit_rmsd':float(fit.rms),'target_aligned_binder_ca_rmsd':rmsd,
                   'generator_contact_pair_jaccard':len(generator['contacts']&pose['contacts'])/len(union) if union else None}
fit=Superimposer();fit.set_atoms(predicted['esmfold2']['target'],predicted['boltz']['target'])
rot,tran=fit.rotran
transformed=np.array([a.coord for a in predicted['boltz']['binder']])@rot+tran
cross=float(np.sqrt(np.mean(np.sum((transformed-np.array([a.coord for a in predicted['esmfold2']['binder']]))**2,axis=-1))))
full_target_fit=float(fit.rms)
fit=Superimposer()
fit.set_atoms([predicted['esmfold2']['target'][i-1] for i in alignment_positions],
              [predicted['boltz']['target'][i-1] for i in alignment_positions])
rot,tran=fit.rotran
transformed=np.array([a.coord for a in predicted['boltz']['binder']])@rot+tran
core_cross=float(np.sqrt(np.mean(np.sum((transformed-np.array([a.coord for a in predicted['esmfold2']['binder']]))**2,axis=-1))))
result={'method':f'independent Bio.PDB.Superimposer; fixed shared {len(alignment_positions)}-residue reference anchors, complete-target comparison retained separately',
        'generator_comparisons':results,'predictor_to_predictor_core_target_fit_rmsd':float(fit.rms),
        'predictor_to_predictor_core_aligned_binder_ca_rmsd':core_cross,
        'complete_target_alignment':{'target_fit_rmsd':full_target_fit,'binder_ca_rmsd':cross,
                                    'limitation':'Includes positions outside the selected core; flexible terminal processing is unresolved'},
        'candidate_id':record['candidate_id'],
        'source_review_sha256':digest(root/f'results/{campaign}-review-v1/review.json')}
write_json(root/f'results/{campaign}-review-v1/independent-pose-audit.json',result)
print(json.dumps(result,indent=2))
