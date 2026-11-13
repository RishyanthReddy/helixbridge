"""Explicitly renumber the existing target for BoltzGen; audit parser annotations."""
import json
import os
from pathlib import Path
import sys
import numpy as np
from Bio.PDB.MMCIF2Dict import MMCIF2Dict
from huggingface_hub import HfApi
from boltzgen.data.mol import load_canonicals
from boltzgen.data.parse.schema import YamlDesignParser
from boltzgen.data import const
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest,write_json
from binder_campaign.structure import AA3
root=Path(os.environ['TASK_ROOT']);folder=root/'results/boltzgen-reserve-v1';out=folder/'input-v1'
if out.exists():raise ValueError('Use a fresh input directory')
out.mkdir()
assets=json.loads((folder/'assets.json').read_text());files={r['name']:r for r in assets['files']}
api=HfApi(token=False)
for row in assets['files'][:2]:
    info=(api.model_info(row['repo'],revision=row['revision'],files_metadata=True,token=False)
          if row['name'].endswith('.ckpt') else api.dataset_info(row['repo'],revision=row['revision'],files_metadata=True,token=False))
    remote=next(r for r in info.siblings if r.rfilename==row['name'])
    expected=remote.lfs.sha256 if remote.lfs else None
    if expected!=row['sha256']:raise ValueError('Independent upstream LFS hash differs')
reference=root/'src/pipeline/data/targets/il7ra/rfd4-reference'
audit=json.loads((reference/'audit.json').read_text());data=MMCIF2Dict(str(reference/'target.cif'))
positions=audit['positions'];mapping={p:i+1 for i,p in enumerate(positions)}
names=[data['_atom_site.label_comp_id'][i] for i,n in enumerate(data['_atom_site.label_atom_id']) if n=='CA']
lines=[]
for i in range(0,len(names),13):lines.append(f'SEQRES {i//13+1:3d} A {len(names):4d}  '+ ' '.join(names[i:i+13]))
source_atoms={}
for i,(name,res,number,x,y,z,element) in enumerate(zip(data['_atom_site.label_atom_id'],data['_atom_site.label_comp_id'],
        data['_atom_site.label_seq_id'],data['_atom_site.Cartn_x'],data['_atom_site.Cartn_y'],data['_atom_site.Cartn_z'],data['_atom_site.type_symbol']),1):
    p=mapping[int(number)];xyz=np.array([x,y,z],float);source_atoms[(p,name)]=xyz
    lines.append(f'ATOM  {i:5d} {name:>4s} {res:3s} A{p:4d}    {xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}  1.00  0.00          {element:>2s}')
(out/'target.pdb').write_text('\n'.join(lines)+'\nTER\nEND\n')
original=[138,139,140,141,142,143,144,147,191,192];local=[mapping[p] for p in original]
spec={'entities':[{'protein':{'id':'B','sequence':60}},{'file':{'path':'target.pdb','include':[{'chain':{'id':'A'}}],
    'binding_types':[{'chain':{'id':'A','binding':','.join(map(str,local))}}],'structure_groups':'all'}}]}
import yaml
(out/'design.yaml').write_text(yaml.safe_dump(spec,sort_keys=False))
moldir=Path(files['mols.zip']['path']);parsed=YamlDesignParser(moldir).parse_yaml(out/'design.yaml',load_canonicals(moldir),moldir)
s=parsed.structure;d=parsed.design_info
if len(s.residues)!=255 or int(d.res_design_mask.sum())!=60:raise ValueError('Design mask or total size differs')
chain=next(c for c in s.chains if c['name']=='A');start=int(chain['res_idx']);residues=s.residues[start:start+int(chain['res_num'])]
sequence=''.join(AA3[str(r['name'])] for r in residues)
if sequence!=audit['reference_sequence'] or d.res_design_mask[start:start+195].any():raise ValueError('Target sequence/design mask changed')
binding=(np.where(d.res_binding_type[start:start+195]==const.binding_type_ids['BINDING'])[0]+1).tolist()
if binding!=local:raise ValueError('Binding-site indexing differs after parsing')
errors=[]
for i,r in enumerate(residues,1):
    for atom in s.atoms[int(r['atom_idx']):int(r['atom_idx'])+int(r['atom_num'])]:
        key=(i,str(atom['name']))
        if key in source_atoms:errors.append(float(np.linalg.norm(atom['coords']-source_atoms[key])))
if len(errors)!=len(source_atoms) or max(errors)>.001:raise ValueError('Parsed target coordinates changed')
write_json(out/'input-audit.json',{'status':'passed_cpu_parser','source_target_sha256':digest(reference/'target.cif'),
    'target_pdb_sha256':digest(out/'target.pdb'),'design_yaml_sha256':digest(out/'design.yaml'),
    'target_sequence':sequence,'target_positions_uniprot':positions,'target_local_indices':list(range(1,196)),
    'hotspots_uniprot':original,'hotspots_local':local,'parsed_binding_indices':binding,
    'designed_residue_count':60,'fixed_target_residue_count':195,'provided_target_atoms_checked':len(errors),
    'max_target_coordinate_roundtrip_error_A':max(errors),'upstream_lfs_hashes_checked':True,
    'supplied_starting_binder_sequence_or_coordinates':False,'source_reference_audit':audit,
    'script_sha256':digest(__file__),'submission_eligible':False})
print('BoltzGen input mapping and upstream asset checks passed',flush=True)
