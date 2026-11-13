"""Independent local CPU implementation gate, with no binding-score pass criterion."""
import argparse
import json
from pathlib import Path
import runpy
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest,write_json
from binder_campaign.pose_review import read_pair,align_pair
parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();w=args.workspace.resolve();e=w/'outputs/execution-evidence';folder=e/'site-diversity-pilot-v1'
helper=runpy.run_path(str(w/'pipeline/scripts/assemble-controlled-campaign.py'));sources={};rows=[]
target=json.loads((w/'pipeline/data/targets/il7ra/manifest.json').read_text())['sequence']
for case in ('control-s201','patch139-s201'):
    directory=e/f'site-{case}-v1';record=json.loads((directory/'candidates.json').read_text())['candidates'][0]
    request=directory/'evaluation-input/input.json'
    for statepath in (directory/'case-state.json',directory/'task-state.json',e/f'site-{case}-boltz-v1/task-state.json'):
        state=json.loads(statepath.read_text());assert state['status']=='success' and state['exit_code']==0
        helper['verify_recorded_inputs'](state,w,sources);helper['verify_recorded_outputs'](state,w,sources)
        sources[str(statepath.relative_to(w))]=digest(statepath)
    reference=record['generator_audit']['reference_audit']
    gen=read_pair(directory/'prediction/model.cif',reference['reference_sequence'],record['sequence'],reference['positions'])
    for name,sha in record['generator_audit']['raw_structure_hashes'].items():assert digest(directory/'prediction'/name)==sha
    poses={};scores={}
    for model in ('esmfold2','boltz'):
        prediction=(folder/f'staging/gate/predictions-v1/seed-{case}/prediction' if model=='esmfold2' else e/f'site-{case}-boltz-v1/prediction')
        metrics=json.loads((prediction/'metrics.json').read_text());assert metrics['input_sha256']==digest(request)
        for name,sha in metrics['artifacts'].items():assert digest(prediction/name)==sha
        pae=np.array(json.loads((prediction/'pae.json').read_text())['pae'])
        raw=prediction/('raw.npz' if model=='esmfold2' else 'boltz_results_input/predictions/input/pae_input_model_0.npz')
        assert pae.shape==(296,296) and np.isfinite(pae).all() and np.array_equal(pae,np.load(raw)['pae'])
        poses[model]=read_pair(prediction/'model.cif',target,record['sequence'],list(range(1,237)))
        directions=[r for r in metrics['ipsae']['pairwise'] if r['type']=='asym']
        assert [(r['chain1'],r['chain2']) for r in directions]==[('A','B'),('B','A')]
        scores[model]={'iptm':metrics['iptm'],'ipsae_directional':[r['ipsae'] for r in directions],
            'generator_to_refold':align_pair(poses[model],gen,reference['positions']),
            'close_pairs':poses[model]['heavy_atom_pairs_lt_2A']}
    rows.append({'case':case,'candidate_id':record['candidate_id'],'scores':scores,
                 'cross_refold':align_pair(poses['esmfold2'],poses['boltz'],reference['positions'])})
statepath=folder/'staging/gate/task-state.json';state=json.loads(statepath.read_text());assert state['status']=='success'
helper['verify_recorded_inputs'](state,w,sources);helper['verify_recorded_outputs'](state,w,sources)
if args.output.exists():raise ValueError('Use fresh audit output')
write_json(args.output,{'status':'passed_implementation_gate_only','cases':rows,'source_sha256':sources,
    'scientific_interpretation':'Low confidence/disagreement retained; no binding acceptance claimed',
    'submission_eligible':False})
print(json.dumps({'status':'passed_implementation_gate_only','source_count':len(sources),'cases':rows},indent=2))
