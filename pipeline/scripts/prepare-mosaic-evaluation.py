"""Verify one Mosaic rehearsal output and import it into the common evaluation."""
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from biotite.structure.io.pdbx import CIFFile,get_structure
from binder_campaign.runner import digest,write_json
from binder_campaign.structure import AA3

root=Path(os.environ['TASK_ROOT'])
pipeline=root/'src/pipeline'
folder=root/'results/mosaic-il7ra-design-v1'
audit_path=folder/'audit.json'
audit=json.loads(audit_path.read_text())
target_path=pipeline/'data/targets/il7ra/manifest.json'
target=json.loads(target_path.read_text())
if (audit['mode']!='design' or audit['submission_eligible'] is not False
        or audit['target_manifest_sha256']!=digest(target_path)):
    raise ValueError('Mosaic audit has wrong role or target')
if audit['adapter_sha256']!=digest(pipeline/'scripts/mosaic-il7ra.py'):
    raise ValueError('Generator adapter changed after execution')
if audit['environment_freeze_sha256']!=digest(root/'env/mosaic-boltz2-freeze.txt'):
    raise ValueError('Mosaic environment record changed after execution')
for filename,key in [('model.cif','model_sha256'),('raw.npz','raw_sha256')]:
    if digest(folder/filename)!=audit[key]: raise ValueError('Mosaic output hash changed')
sequence=audit['binder_sequence']
if not target['min_length']<=len(sequence)<=target['max_length'] or set(sequence)-set('ACDEFGHIKLMNPQRSTVWY'):
    raise ValueError('Sequence alphabet/length violation')
atoms=get_structure(CIFFile.read(folder/'model.cif'),model=1,use_author_fields=False)
ca=atoms[atoms.atom_name=='CA']
chains={str(c):''.join(AA3[x] for x in ca[ca.chain_id==c].res_name) for c in dict.fromkeys(ca.chain_id.tolist())}
tc=[c for c,s in chains.items() if s==target['sequence']]
bc=[c for c,s in chains.items() if s==sequence]
if len(chains)!=2 or len(tc)!=1 or len(bc)!=1 or not np.isfinite(atoms.coord).all():
    raise ValueError('Mosaic chain identity or coordinates invalid')
with np.load(folder/'raw.npz') as raw:
    if raw['pae'].shape!=(296,296) or not np.isfinite(raw['pae']).all():
        raise ValueError('Mosaic PAE mapping invalid')
for path in (root/'results').glob('rfd4-il7ra*-v1/candidates.json'):
    if any(row['sequence']==sequence for row in json.loads(path.read_text())['candidates']):
        raise ValueError('Exact duplicate of an existing RFD4 rehearsal')
settings=audit['settings']
if (settings['templates'] or settings['target_interval']!=[1,236]
        or settings['starting_binder']!='random simplex probabilities; no known-positive input'):
    raise ValueError('Unreviewed Mosaic starting recipe')
reference={'target_id':'il7ra','role':'reference_rehearsal_only',
           'positions':list(range(1,237)),'reference_sequence':target['sequence'],
           'alignment_positions':list(range(37,232)),'missing_official_positions':[],
           'source_provenance':'Mosaic postdesign discrete Boltz2 prediction; Boltz2 is in the design objective. Core anchors match RFD4 review.'}
candidate_id='il7ra-mosaic-'+digest(audit_path)[:12]
record={'candidate_id':candidate_id,'target_id':'il7ra','sequence':sequence,'format':'minibinder',
        'generator':'Mosaic-Boltz2-ProteinMPNN','generator_revision':audit['mosaic_revision'],
        'campaign_kind':'reference_rehearsal','submission_eligible':False,'qc_reasons':[],
        'prediction_relationships':{'esmfold2':'separate_model_from_design_objective',
                                    'boltz':'same_model_family_as_design_objective'},
        'ignored_generator_metrics':{'generator_model_iptm':'Mosaic predict(PSSM=None) uses a zero-length binder in its ipTM helper; this field is not interpreted'},
        'generator_audit':{**audit,'reference_audit':reference,
                           'model':{'revision':audit['checkpoint_sha256']}},
        'generator_structure':str(folder/'model.cif'),'generator_structure_sha256':audit['model_sha256'],
        'backbone_family_id':candidate_id,'source_audit':str(audit_path),'source_sha256':digest(audit_path),
        'screen_status':'not_run','independent_prediction_status':'not_run','novelty_review':'pending'}
records=folder/'candidates.json'
if records.exists(): raise ValueError('Candidate records already exist')
write_json(records,{'candidates':[record],'count':1,'note':'Mosaic rehearsal only; Boltz prediction is not independent of its design objective'})
subprocess.run([sys.executable,str(pipeline/'scripts/prepare-candidate-evaluation.py'),str(records),
                str(folder/'evaluation-input'),'mosaic-il7ra'],check=True)
print('Mosaic rehearsal candidate imported:',candidate_id)
