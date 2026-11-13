"""CPU-only official AF2-Multimer reference, capturing the exact MSA boundary."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
os.environ['JAX_PLATFORMS']='cpu'
parser=argparse.ArgumentParser()
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args(); w=args.workspace.resolve(); out=args.output.resolve()
if out.exists(): raise ValueError('Use a fresh native-reference directory')
out.mkdir(parents=True)
sys.path.insert(0,str(w/'work/vendor/alphafold-native'))
sys.path.insert(0,str(w/'pipeline'))
import numpy as np
import jax
import jax.numpy as jnp
import haiku as hk
from alphafold.model import config,data,modules_multimer as mm,utils
from binder_campaign.runner import digest,write_json
import subprocess
source=w/'work/vendor/alphafold-native'
revision=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
if revision!='c77e5d2a8961d1a353632c462914ff0a32a950f6':raise ValueError('Native AF2 source changed')
checkpoint=w/'work/localfold-weights/native/params_model_1_multimer_v3.npz'
params=utils.flat_params_to_haiku(dict(np.load(checkpoint)))
cfg=config.model_config('model_1_multimer_v3')
cfg.model.num_recycle=0
cfg.model.num_ensemble_eval=1
cfg.model.global_config.bfloat16=False
evo=cfg.model.embeddings_and_evoformer
evo.num_msa=1;evo.num_extra_msa=1;evo.masked_msa.replace_fraction=0
n=16
aa=np.random.default_rng(0).integers(0,20,size=n,dtype=np.int32)
sequence=''.join('ARNDCQEGHILKMFPSTWYV'[i] for i in aa)
batch={'aatype':aa,'residue_index':np.tile(np.arange(8,dtype=np.int32),2),
       'seq_mask':np.ones(n,np.float32),'msa':np.stack([aa,np.full(n,21,np.int32)]),
       'msa_mask':np.stack([np.ones(n,np.float32),np.zeros(n,np.float32)]),
       'deletion_matrix':np.zeros((2,n),np.float32),'cluster_bias_mask':np.array([1,0],np.float32),
       'asym_id':np.repeat(np.array([1,2],np.int32),8),'entity_id':np.repeat(np.array([1,2],np.int32),8),
       'sym_id':np.ones(n,np.int32),'template_aatype':np.full((1,n),20,np.int32),
       'all_atom_positions':np.zeros((n,37,3),np.float32),'all_atom_mask':np.zeros((n,37),np.float32),
       'template_all_atom_mask':np.zeros((1,n,37),np.float32),
       'template_all_atom_positions':np.zeros((1,n,37,3),np.float32),
       'template_mask':np.zeros(1,np.float32)}
original=mm.create_msa_feat
def capture_msa(b):
    feat=original(b)
    extra,mask=mm.create_extra_msa_feature(b,1)
    named={key:b[key] for key in ['aatype','residue_index','seq_mask','msa_mask','asym_id','entity_id','sym_id']}
    named.update(msa_feat=feat,extra_msa=b['extra_msa'][:1],extra_has_deletion=extra[:,:,-2],
                 extra_deletion_value=extra[:,:,-1],extra_msa_mask=mask)
    def dump(values):
        write_json(out/'inputs.json',{'length':n,'sequence':sequence,'chain_lengths':[8,8],
            'msa_sequences':1,'extra_sequences':1,
            'features':{key:np.asarray(value).ravel().tolist() for key,value in values.items()}})
    jax.debug.callback(dump,named,ordered=True)
    return feat
mm.create_msa_feat=capture_msa
@hk.transform
def forward(b):
    return mm.AlphaFold(cfg.model)(b,is_training=False,return_representations=True)
started=time.monotonic()
result=jax.jit(forward.apply)(params,jax.random.PRNGKey(0),jax.tree.map(jnp.asarray,batch))
result=jax.tree.map(np.asarray,result)
jax.effects_barrier()
write_json(out/'reference.json',{'ca':result['structure_module']['final_atom_positions'][:,1].ravel().tolist(),
    'pair':result['representations']['pair'].ravel().tolist(),
    'plddt_logits':result['predicted_lddt']['logits'].ravel().tolist(),
    'source_revision':revision,'checkpoint_sha256':digest(checkpoint),'elapsed_seconds':time.monotonic()-started,
    'settings':{'recycles':0,'msa_rows':1,'extra_rows':1,'masked_msa_replace_fraction':0,'bfloat16':False},
    'scope':'Exact forward-pass diagnostic on a 16-residue synthetic two-chain fixture; not binding validation'})
print('Official native AF2-Multimer reference saved',flush=True)
