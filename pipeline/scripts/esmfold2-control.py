"""One unconstrained two-protein ESMFold2 control with audited raw outputs."""
import io
import json
import os
from pathlib import Path
import subprocess
import resource
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import torch
from biotite.structure.io.pdbx import CIFFile, get_structure
from esm.models.esmfold2 import EsmFold2Model, ESMFold2InputBuilder, ProteinInput, StructurePredictionInput
from esm.utils.msa import MSA
from binder_campaign.runner import digest, write_json
from binder_campaign.structure import AA3

root=Path(os.environ['TASK_ROOT'])
input_path=Path(sys.argv[1]); out=Path(sys.argv[2]); out.mkdir(parents=True,exist_ok=True)
if (out/'model.cif').exists(): raise ValueError('Use a new pilot directory; refusing stale inference output')
request=json.loads(input_path.read_text())
checkpoints=json.loads((root/'env/esmfold2-checkpoints.json').read_text())
models={r['repo']:r for r in checkpoints}
if set(models)!={'biohub/ESMFold2'}: raise ValueError('Expected the pinned ESMFold2 checkpoint with its bundled backbone')
assert torch.cuda.is_available()
torch.cuda.reset_peak_memory_stats()
target=request['target']; partner=request['partner']; settings=request['settings'].copy()
if partner.get('msa') is not None: raise ValueError('Binder/partner MSA must be absent')
if settings['num_diffusion_samples'] != 1: raise ValueError('Pilot must use exactly one sample')
msa_path=Path(__file__).resolve().parents[1]/target['msa']
msa=MSA.from_a3m(msa_path,remove_insertions=True,max_sequences=1024)
started=time.monotonic()
print('Loading pinned ESMFold2 checkpoint',models['biohub/ESMFold2']['revision'],flush=True)
model=EsmFold2Model.from_pretrained(models['biohub/ESMFold2']['path'],load_esmc=False,device='cuda').eval()
if model.esmc is None or model.config.esmc_config is None:
    raise ValueError('Checkpoint did not supply its expected bundled ESMC backbone')
os.environ['ESMCFOLD_CCD_PATH']=str(Path(models['biohub/ESMFold2']['path'])/'ccd.pkl')
backend=settings.pop('kernel_backend')
model.set_kernel_backend(backend)
loaded=time.monotonic()
spi=StructurePredictionInput(sequences=[ProteinInput(id='A',sequence=target['sequence'],msa=msa),
                                       ProteinInput(id='B',sequence=partner['sequence'],msa=None)])
print('Folding natural-ligand control; no template or pocket constraints',flush=True)
result=ESMFold2InputBuilder(ccd_cache=Path(models['biohub/ESMFold2']['path'])).fold(model,spi,**settings)
torch.cuda.synchronize()
folded=time.monotonic()
pae=np.asarray(result.pae)
expected_length=len(target['sequence'])+len(partner['sequence'])
if pae.shape!=(expected_length,expected_length) or not np.isfinite(pae).all():
    raise ValueError('PAE does not have one finite token per input residue')
cif=result.complex.to_mmcif()
atoms=get_structure(CIFFile.read(io.StringIO(cif)),model=1,use_author_fields=False)
ca=atoms[atoms.atom_name=='CA']
if len(ca)!=expected_length: raise ValueError('CIF/PAE residue count mismatch')
observed=[]
for chain in dict.fromkeys(ca.chain_id.tolist()):
    observed.append(''.join(AA3[x] for x in ca[ca.chain_id==chain].res_name))
if observed != [target['sequence'],partner['sequence']]:
    raise ValueError('CIF chain order/sequence differs from PAE input convention')
if not np.isfinite(ca.coord).all(): raise ValueError('Invalid coordinates')
(out/'model.cif').write_text(cif)
# The reference scorer accepts AF3-style JSON + CIF; pLDDT-based auxiliary
# scores are excluded because atom_plddts are intentionally not synthesized.
write_json(out/'pae.json',{'pae':pae.tolist()})
np.savez_compressed(out/'raw.npz',pae=pae,plddt=np.asarray(result.plddt))
ipsae=root/'src/IPSAE/ipsae.py'
command=[sys.executable,str(ipsae),str(out/'pae.json'),str(out/'model.cif'),'10','10']
with (out/'ipsae.log').open('w') as log:
    subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
scores=out/'model_10_10.txt'
if not scores.is_file() or len(scores.read_text().splitlines())<4:
    raise ValueError('ipSAE produced no pairwise score rows')
pairwise=[]
for line in scores.read_text().splitlines():
    fields=line.split()
    if len(fields)>5 and fields[4] in ('asym','max'):
        value=float(fields[5])
        if not np.isfinite(value): raise ValueError('Nonfinite ipSAE output')
        pairwise.append({'chain1':fields[0],'chain2':fields[1],'type':fields[4],'ipsae':value})
chain_ids=list(dict.fromkeys(ca.chain_id.tolist()))
expected_pairs={(str(chain_ids[0]),str(chain_ids[1])),(str(chain_ids[1]),str(chain_ids[0]))}
if {(r['chain1'],r['chain2']) for r in pairwise if r['type']=='asym'} != expected_pairs:
    raise ValueError('Missing or unexpected directional ipSAE pairs')
plddt=float(np.asarray(result.plddt).mean())
if not all(np.isfinite([plddt,float(result.ptm),float(result.iptm)])):
    raise ValueError('Nonfinite confidence metrics')
write_json(out/'metrics.json',{
    'status':'prediction_control_only; not official admission or experimental evidence',
    'input_sha256':digest(input_path),'target_msa_sha256':digest(msa_path),
    'model_revisions':{k:v['revision'] for k,v in models.items()},'settings':request['settings'],
    'chains':[{'id':str(c),'length':int(sum(ca.chain_id==c))} for c in dict.fromkeys(ca.chain_id.tolist())],
    'plddt_raw_mean':plddt,'ptm':float(result.ptm),'iptm':float(result.iptm),
    'load_seconds':loaded-started,'fold_seconds':folded-loaded,
    'peak_allocated_mib':torch.cuda.max_memory_allocated()/1024**2,
    'peak_reserved_mib':torch.cuda.max_memory_reserved()/1024**2,
    'host_peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024),
    'cpu_user_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_utime,
    'cpu_system_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_stime,
    'ipsae':{'script_sha256':digest(ipsae),'pae_cutoff':10,'distance_cutoff':10,
             'pairwise':pairwise,
             'aggregation':'raw directional and symmetric-max rows retained; organizer aggregation unknown',
             'auxiliary_plddt_based_metrics':'not used; upstream lacks atom_plddts in this adapter'},
    'artifacts':{p.name:digest(p) for p in [out/'model.cif',out/'pae.json',scores]},
    'protocol_status':request['protocol_status'],'construct_status':request['construct_status']
})
print('Validated ESMFold2 control outputs',out,flush=True)
