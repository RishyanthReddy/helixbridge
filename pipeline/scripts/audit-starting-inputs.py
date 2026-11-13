"""Verify the two rehearsal recipes supplied only a target and a new binder segment."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from biotite.structure.io.pdbx import CIFFile, get_structure
from binder_campaign.runner import digest, write_json
from binder_campaign.structure import AA3

root=Path(os.environ['TASK_ROOT'])
pipeline=root/'src/pipeline'
folder=pipeline/'data/targets/il7ra/rfd4-reference'
audit=json.loads((folder/'audit.json').read_text())
for name,sha in audit['files'].items():
    if digest(folder/name)!=sha: raise ValueError('Prepared input changed')
payload=json.loads((folder/'conditions.json').read_text())
if set(payload)!={'il7ra'}: raise ValueError('Unexpected design recipe')
recipe=payload['il7ra']
if set(recipe)!={'input','contig','conditions'} or recipe['input']!='target.cif' or recipe['contig']!='60, /0, A37-231':
    raise ValueError('Only the reviewed target plus new expandable binder segment is permitted')
conditions=recipe['conditions']
if set(conditions)!={'C_CRDGRP','C_SEQ','C_HOT'}:
    raise ValueError('Unreviewed conditioning supplied')
if conditions['C_SEQ']!={'true':[{'select':"sel('A')"}]}:
    raise ValueError('Fixed starting binder sequence is prohibited in this de novo recipe')
if conditions['C_CRDGRP']!={'1':[{'select':"sel('A/*/*/[N,CA,C,O]')"}]}:
    raise ValueError('Only reviewed target geometry is permitted')
expected_hotspots="sel('A/*/["+','.join(map(str,audit['hotspots_uniprot']))+"]')"
if conditions['C_HOT']!={'true':[{'select':expected_hotspots}]}:
    raise ValueError('Unreviewed hotspot conditioning')
atoms=get_structure(CIFFile.read(folder/'target.cif'),model=1,use_author_fields=False)
ca=atoms[atoms.atom_name=='CA']
if set(atoms.chain_id)!={'A'} or ca.res_id.tolist()!=audit['positions']:
    raise ValueError('Source structure contains a non-target chain or unexpected residues')
if ''.join(AA3[n] for n in ca.res_name)!=audit['reference_sequence']:
    raise ValueError('Target identity differs')
seen=set()
records=[]
for campaign in ['rfd4-il7ra','rfd4-il7ra-high']:
    result=root/f'results/{campaign}-v1'
    candidate=json.loads((result/'candidates.json').read_text())['candidates'][0]
    state=json.loads((result/'task-state.json').read_text())
    for name in ['target.cif','conditions.json','audit.json']:
        path=folder/name
        if state['inputs'][str(path)]!=digest(path):
            raise ValueError('Executed model did not record these exact starting inputs')
    sequence=candidate['sequence']
    if sequence in seen: raise ValueError('Exact duplicate across rehearsal variants')
    seen.add(sequence)
    record={'candidate_id':candidate['candidate_id'],'initialization_review':'passed_for_this_recipe',
            'target_only_coordinates':True,'fixed_sequence_condition_only_on_target':True,
            'new_binder_segment_length':60,'supplied_starting_binder_sequence_or_coordinates':False,
            'source_conditions_sha256':digest(folder/'conditions.json'),
            'source_target_cif_sha256':digest(folder/'target.cif'),
            'executed_model_state_sha256':digest(result/'task-state.json'),
            'scope':'No experimentally positive binder was supplied as an optimization starting input in this audited recipe. This is not comprehensive sequence novelty or cross-team duplicate clearance.',
            'submission_eligible':False}
    write_json(root/f'results/{campaign}-review-v1/starting-input-audit.json',record)
    records.append(record)
print('Both executed recipes used only target inputs plus a generated 60-residue segment; no exact sequence duplicate',flush=True)
