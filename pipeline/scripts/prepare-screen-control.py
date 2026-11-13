"""Use the natural IL-7 ligand as a prediction control, never a design seed."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.targets import download
from binder_campaign.runner import digest, write_json

root=Path(__file__).resolve().parents[1]
folder=root/'data/controls/il7-il7ra'
folder.mkdir(parents=True,exist_ok=True)
source=download('https://rest.uniprot.org/uniprotkb/P13232.json',folder/'P13232.json')
entry=json.loads(source.read_text())
ligand=entry['sequence']['value'][25:177]
assert len(ligand)==152
target=json.loads((root/'data/targets/il7ra/manifest.json').read_text())
write_json(folder/'input.json',{
    'role':'natural_ligand_prediction_control_only; not a competition candidate or optimization seed',
    'target':{'id':'A','sequence':target['sequence'],'uniprot':'P16871-1','range':[1,236],
              'msa':'data/targets/il7ra/msa/target.a3m'},
    'partner':{'id':'B','sequence':ligand,'uniprot':'P13232','range':[26,177],'msa':None},
    'source_url':'https://rest.uniprot.org/uniprotkb/P13232.json','source_sha256':digest(source),
    'settings':{'num_loops':20,'num_sampling_steps':200,'num_diffusion_samples':1,'seed':0,
                'lm_dropout':0.3,'msa_max_depth':1024,'msa_column_mask_rate':0.1,'kernel_backend':'fused'},
    'protocol_status':'published-settings approximation; organizer checkpoint, seed value, inference defaults and ipSAE convention unspecified',
    'construct_status':'official sequence interval retained; signal processing and actual assay construct unconfirmed'
})
print(folder/'input.json')
