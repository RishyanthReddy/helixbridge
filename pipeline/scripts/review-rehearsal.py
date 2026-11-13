"""Audit two predictions, compare target-aligned poses, and export a diagnostic review."""
import csv
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from biotite.structure.io.pdbx import CIFFile, get_structure
from binder_campaign.runner import digest, write_json
from binder_campaign.structure import AA3

root = Path(os.environ['TASK_ROOT'])
campaign = sys.argv[3] if len(sys.argv)>3 else 'rfd4-il7ra'
if not re.fullmatch(r'[a-z0-9-]+',campaign): raise ValueError('Invalid campaign stem')
source = Path(sys.argv[2]) if len(sys.argv)>2 else root/'results/rfd4-il7ra-v1/candidates.json'
record = json.loads(source.read_text())['candidates'][0]
sequence = record['sequence']
reference = record['generator_audit']['reference_audit']
target = json.loads((root/'src/pipeline/data/targets/il7ra/manifest.json').read_text())
out = Path(sys.argv[1])
if out.exists():
    raise ValueError('Use a fresh review directory')

def read_pose(path, target_sequence):
    atoms = get_structure(CIFFile.read(path),model=1,use_author_fields=False)
    ca = atoms[atoms.atom_name=='CA']
    identities = {c:''.join(AA3[x] for x in ca[ca.chain_id==c].res_name)
                  for c in dict.fromkeys(ca.chain_id.tolist())}
    tc = [c for c,s in identities.items() if s==target_sequence]
    bc = [c for c,s in identities.items() if s==sequence]
    if len(identities)!=2 or len(tc)!=1 or len(bc)!=1 or tc==bc or not np.isfinite(atoms.coord).all():
        raise ValueError('Ambiguous/missing target or binder identity, or invalid coordinates')
    return atoms, atoms[atoms.chain_id==tc[0]], atoms[atoms.chain_id==bc[0]]

def contacts(target_atoms,binder_atoms):
    ta=target_atoms[(target_atoms.element!='H') & (target_atoms.element!='D')]
    ba=binder_atoms[(binder_atoms.element!='H') & (binder_atoms.element!='D')]
    distances=np.linalg.norm(ta.coord[:,None,:]-ba.coord[None,:,:],axis=-1)
    near=distances<5.0
    return {'contact_distance_angstrom':5.0,'atom_pairs_lt_5A':int(near.sum()),
            'target_residues_with_contacts':int(len(set(ta.res_id[np.any(near,axis=1)].tolist()))),
            'binder_residues_with_contacts':int(len(set(ba.res_id[np.any(near,axis=0)].tolist()))),
            'heavy_atom_pairs_lt_2A':int((distances<2.0).sum()),
            'min_interchain_heavy_atom_distance_angstrom':float(distances.min()),
            'interpretation':'Geometric flags only; not a calibrated energy or binding filter'}

generator=Path(record['generator_structure'])
if digest(generator)!=record['generator_structure_sha256']:
    raise ValueError('Generator pose changed')
_,gt,gb=read_pose(generator,reference['reference_sequence'])
gtca=gt[gt.atom_name=='CA'].coord
gbca=gb[gb.atom_name=='CA'].coord
alignment_positions=reference.get('alignment_positions',reference['positions'])
if not set(alignment_positions)<=set(reference['positions']):
    raise ValueError('Alignment positions are absent from generator target')
gtca=gtca[[reference['positions'].index(position) for position in alignment_positions]]
predictions={}
for model in ['esmfold2','boltz']:
    result=root/f'results/{campaign}-{model}-v1/prediction'
    metrics=json.loads((result/'metrics.json').read_text())
    for name,sha in metrics['artifacts'].items():
        if digest(result/name)!=sha:
            raise ValueError(f'{model} artifact changed: {name}')
    _,pt,pb=read_pose(result/'model.cif',target['sequence'])
    ptca=pt[pt.atom_name=='CA'].coord
    anchor=ptca[np.asarray(alignment_positions)-target['start']]
    pc=gtca.mean(axis=0); qc=anchor.mean(axis=0)
    u,_,vt=np.linalg.svd((gtca-pc).T@(anchor-qc))
    if np.linalg.det(u@vt)<0: u[:,-1]*=-1
    rotation=u@vt
    target_rmsd=float(np.sqrt(np.mean(np.sum(((gtca-pc)@rotation+qc-anchor)**2,axis=-1))))
    binder_rmsd=float(np.sqrt(np.mean(np.sum(((gbca-pc)@rotation+qc-pb[pb.atom_name=='CA'].coord)**2,axis=-1))))
    directional=[row['ipsae'] for row in metrics['ipsae']['pairwise'] if row['type']=='asym']
    if len(directional)!=2:
        raise ValueError('Two directional interface scores required')
    predictions[model]={'metrics_sha256':digest(result/'metrics.json'),
                        'model_cif_sha256':digest(result/'model.cif'), 'iptm':metrics['iptm'],
                        'ipsae_directional':directional,'ipsae_directional_min':min(directional),
                        'ipsae_directional_max':max(directional),
                        'target_anchor_residues':len(alignment_positions),
                        'target_ca_fit_rmsd_angstrom':target_rmsd,
                        'target_aligned_binder_ca_rmsd_angstrom':binder_rmsd,
                        'contacts':contacts(pt,pb)}
fractions={aa:sequence.count(aa)/len(sequence) for aa in sorted(set(sequence))}
sequence_review={'length':len(sequence),'composition':fractions,
                 'DE_fraction':sum(sequence.count(a) for a in 'DE')/len(sequence),
                 'KR_fraction':sum(sequence.count(a) for a in 'KR')/len(sequence),
                 'KR_minus_DE_count':sum(sequence.count(a) for a in 'KR')-sum(sequence.count(a) for a in 'DE'),
                 'longest_identical_run':max(len(m.group()) for m in re.finditer(r'(.)\1*',sequence)),
                 'N_glycosylation_sequons':[m.start()+1 for m in re.finditer(r'(?=N[^P][ST])',sequence)],
                 'interpretation':'Composition/motif flags only; not a predicted pI, expression or aggregation measurement'}
out.mkdir(parents=True)
report={'candidate_id':record['candidate_id'],'sequence':sequence,
        'status':'diagnostic_reference_rehearsal_only; no shortlisted or submission-eligible candidate claimed',
        'candidate_records_sha256':digest(source),'submission_eligible':False,
        'generation':{'model':record['generator'],'code_revision':record['generator_revision'],
                      'model_revision':record['generator_audit']['model']['revision'],
                      'generator_pose_sha256':digest(generator),'reference_missing_positions':reference['missing_official_positions']},
        'sequence_review':sequence_review,'predictions':predictions,
        'generator_contacts':contacts(gt,gb),
        'interpretation':'Uncalibrated model evidence retained separately. No KD or binding/agonism/selectivity claim. Official screen configuration and assay processing remain unresolved.'}
write_json(out/'review.json',report)
with (out/'REHEARSAL_ONLY.csv').open('w',newline='') as stream:
    fields=['candidate_id','target_id','sequence','role','submission_eligible','esmfold2_iptm','boltz_iptm']
    writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
    writer.writerow({'candidate_id':record['candidate_id'],'target_id':'il7ra','sequence':sequence,
                     'role':'diagnostic_reference_rehearsal_only','submission_eligible':False,
                     'esmfold2_iptm':predictions['esmfold2']['iptm'],'boltz_iptm':predictions['boltz']['iptm']})
with (out/'REHEARSAL_ONLY.csv').open(newline='') as stream:
    rows=list(csv.DictReader(stream))
if len(rows)!=1 or rows[0]['sequence']!=sequence or rows[0]['submission_eligible']!='False':
    raise ValueError('Diagnostic CSV round trip failed')
write_json(out/'export-audit.json',{'csv_sha256':digest(out/'REHEARSAL_ONLY.csv'),
                                 'round_trip_checked':True,'official_submission_schema':False})
print(json.dumps(report,indent=2),flush=True)
