"""CPU-only structural/site diagnostics and explicitly provisional surface inputs."""
import argparse
import itertools
import json
from pathlib import Path
import re
import subprocess
import sys

import numpy as np
from Bio.PDB import PDBParser, ShrakeRupley, Superimposer
from Bio.PDB.Structure import Structure
from Bio.PDB.Model import Model
from Bio.PDB.Chain import Chain
from Bio.PDB.Residue import Residue
from Bio.PDB.Atom import Atom
from Bio.PDB.MMCIF2Dict import MMCIF2Dict

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest,write_json
from binder_campaign.structure import AA3
from binder_campaign.pose_review import read_pair

parser=argparse.ArgumentParser()
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--output-dir',type=Path,required=True)
args=parser.parse_args();w=args.workspace.resolve();out=args.output_dir.resolve()
if out.exists():raise ValueError('Use a fresh output directory')
sources={}
def keep(p,expected=None):
    sha=digest(p)
    if expected and sha!=expected:raise ValueError('Changed source: '+str(p))
    sources[str(p.relative_to(w))]=sha
    return p
def read(p):return json.loads(keep(p).read_text())
prior=w/'outputs/esm-recovery-review-2026-11-02-v2'
manifest=read(prior/'manifest.json')
for n,h in manifest['source_sha256'].items():keep(w/n,h)
for n,h in manifest['output_sha256'].items():keep(prior/n,h)
pool=read(w/'outputs/controlled-campaign-review-2026-11-02-v4/comparison.json')['cases']
selected={r['candidate_id'] for r in read(prior/'review.json')['sequence_context_review_unchanged']['research_followups']}
records={}
for p in sorted((w/'outputs/execution-evidence').glob('rfd4*-v1/candidates.json')):
    r=json.loads(p.read_text())['candidates'][0]
    if r['candidate_id'] in {c['candidate_id'] for c in pool}:records[r['candidate_id']]=(p,r)
if len(records)!=16:raise ValueError('Expected sixteen RFD4 records')
out.mkdir(parents=True);(out/'binders').mkdir();(out/'alignments').mkdir()
binary=keep(w/'work/vendor/USalign/USalign')
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=binary.parent,text=True).strip()
target=read(w/'pipeline/data/targets/il7ra/manifest.json')['sequence']
poses={};names=[]
for identifier,(record_path,r) in sorted(records.items()):
    keep(record_path)
    campaign=record_path.parent.name[:-3]
    for model in ('esmfold2','boltz'):
        path=w/f'outputs/execution-evidence/{campaign}-{model}-v1/prediction/model.cif'
        review=read(w/f'outputs/execution-evidence/{campaign}-review-v1/review.json')
        keep(path,review['predictions'][model]['model_cif_sha256'])
        pose=read_pair(path,target,r['sequence'],list(range(1,237)))
        key=identifier+'-'+model;poses[key]=pose;names.append(key)
        pdb=out/'binders'/f'{key}.pdb'
        reverse={v:k for k,v in AA3.items()}
        lines=[f'ATOM  {i:5d}  CA  {reverse[aa]:3s} B{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C'
               for i,(aa,(x,y,z)) in enumerate(zip(r['sequence'],pose['binder_ca']),1)]
        pdb.write_text('\n'.join(lines)+'\nTER\nEND\n')
def align(a,b,stem):
    raw=subprocess.check_output([str(binary),str(out/'binders'/f'{a}.pdb'),str(out/'binders'/f'{b}.pdb'),'-mol','prot'],text=True)
    (out/'alignments'/f'{stem}.txt').write_text(raw)
    scores=[float(x) for x in re.findall(r'TM-score=\s*([0-9.]+)',raw)]
    match=re.search(r'Aligned length=\s*(\d+), RMSD=\s*([0-9.]+)',raw)
    if len(scores)!=2 or not match:raise ValueError('Unexpected USalign output')
    return {'tm_left':scores[0],'tm_right':scores[1],'aligned_length':int(match[1]),'rmsd_A':float(match[2])}
pairs=[]
for model in ('esmfold2','boltz'):
    ids=sorted(records)
    for index,(a,b) in enumerate(itertools.combinations(ids,2)):
        pa,pb=poses[a+'-'+model],poses[b+'-'+model]
        ca,cb=set(pa['target_contacts_lt_5A']),set(pb['target_contacts_lt_5A'])
        pairs.append({'model':model,'left':a,'right':b,**align(a+'-'+model,b+'-'+model,f'{model}-{index:03d}'),
                      'site_jaccard':len(ca&cb)/len(ca|cb) if ca|cb else 0})
checks=[]
for model in ('esmfold2','boltz'):
    a,b=sorted(selected)[:2]
    own=align(a+'-'+model,a+'-'+model,'self-'+model)
    reverse=align(b+'-'+model,a+'-'+model,'reverse-'+model)
    forward=next(r for r in pairs if r['model']==model and r['left']==a and r['right']==b)
    if min(own['tm_left'],own['tm_right'])<.99999 or abs(reverse['tm_left']-forward['tm_right'])>.001:
        raise ValueError('Self/reverse alignment check failed')
    checks.append({'model':model,'self':own,'reverse_order':reverse})
def groups(rows,field,threshold,coverage=False):
    lookup={tuple(sorted((r['left'],r['right']))):r for r in rows}
    def related(a,b):
        r=lookup[tuple(sorted((a,b)))]
        score=min(r['tm_left'],r['tm_right']) if field=='tm' else r['site_jaccard']
        return score>=threshold and (not coverage or r['aligned_length']>=48)
    complete=[]
    for identifier in sorted(records):
        for group in complete:
            if all(related(identifier,x) for x in group):group.append(identifier);break
        else:complete.append([identifier])
    connected=[];remaining=set(records)
    while remaining:
        group={min(remaining)}
        while True:
            expanded=group|{b for b in remaining if any(a!=b and related(a,b) for a in group)}
            if expanded==group:break
            group=expanded
        connected.append(sorted(group));remaining-=group
    return {'complete_link_greedy':complete,'connected_components':connected}
clusters={model:{'fold':{str(t):groups([r for r in pairs if r['model']==model],'tm',t,True) for t in (.5,.6,.7)},
                 'site':{str(t):groups([r for r in pairs if r['model']==model],'site',t) for t in (.3,.5,.7)}}
          for model in ('esmfold2','boltz')}
reference=w/'pipeline/data/targets/il7ra/rfd4-reference'
audit=read(reference/'audit.json');cif=MMCIF2Dict(str(keep(reference/'target.cif',audit['files']['target.cif'])))
structure=Structure('reference');m=Model(0);structure.add(m);chain=Chain('A');m.add(chain)
for i,(name,res,number,x,y,z,element) in enumerate(zip(cif['_atom_site.label_atom_id'],cif['_atom_site.label_comp_id'],
        cif['_atom_site.label_seq_id'],cif['_atom_site.Cartn_x'],cif['_atom_site.Cartn_y'],cif['_atom_site.Cartn_z'],cif['_atom_site.type_symbol'])):
    pos=int(number)
    if (' ',pos,' ') not in chain:chain.add(Residue((' ',pos,' '),res,' '))
    chain[(' ',pos,' ')].add(Atom(name,np.array([x,y,z],float),0.,1.,' ',name,i,element=element))
ShrakeRupley(n_points=960).compute(structure,level='R')
positions=sorted(r.id[1] for r in chain);coords={p:chain[(' ',p,' ')]['CA'].coord for p in positions}
sasa={p:float(chain[(' ',p,' ')].sasa) for p in positions}
experimental=PDBParser(QUIET=True).get_structure('native',str(keep(w/'work/3DI3.pdb')))[0]
mapping=read(w/'pipeline/data/targets/il7ra/mapping.json')
keep(w/'work/3DI3.pdb',mapping['pdb_sha256'])
common=[r for r in mapping['residues'] if r['uniprot_position'] in coords]
fit=Superimposer();fit.set_atoms([chain[(' ',r['uniprot_position'],' ')]['CA'] for r in common],
                               [experimental['B'][(' ',r['source_number'],' ')]['CA'] for r in common])
native_atoms=[a for a in experimental['A'].get_atoms() if a.element not in ('H','D')]
native_interface=sorted({r['uniprot_position'] for r in common if min(np.linalg.norm(a.coord-b.coord)
    for a in experimental['B'][(' ',r['source_number'],' ')] if a.element not in ('H','D') for b in native_atoms)<5})
sequons=[i+1 for i in range(len(target)-2) if target[i]=='N' and target[i+1]!='P' and target[i+2] in 'ST']
anchor={p:chain[(' ',p,' ')]['ND2'].coord for p in sequons if (' ',p,' ') in chain}
covered=set().union(*(set(poses[x+'-'+model]['target_contacts_lt_5A']) for x in selected for model in ('esmfold2','boltz')))
patches=[]
for center in positions:
    if center<=41 or center>=227 or sasa[center]<30 or np.linalg.norm(coords[center]-coords[66])<10:continue
    patch=[p for p in positions if 41<p<227 and sasa[p]>=20
           and np.linalg.norm(coords[p]-coords[center])<=10
           and np.linalg.norm(coords[p]-coords[66])>=10
           and min(np.linalg.norm(coords[p]-x) for x in anchor.values())>=8]
    if len(patch)<5:continue
    overlap=len(set(patch)&covered)/len(patch)
    nd=min(np.linalg.norm(coords[center]-x) for x in anchor.values())
    if overlap>.25 or nd<12:continue
    patches.append({'center':center,'positions':patch,'existing_contact_overlap_fraction':overlap,
        'center_to_nearest_sequon_ND2_A':float(nd),'surface_area_sum_A2':sum(sasa[p] for p in patch),
        'minimum_hotspot_CA_to_sequon_ND2_A':float(min(np.linalg.norm(coords[q]-x) for q in patch for x in anchor.values())),
        'native_IL7_interface_overlap':sorted(set(patch)&set(native_interface))})
chosen=[]
for p in sorted(patches,key=lambda r:(r['existing_contact_overlap_fraction'],-len(r['positions']),-r['surface_area_sum_A2'],r['center'])):
    if all(np.linalg.norm(coords[p['center']]-coords[q['center']])>=15 for q in chosen):chosen.append(p)
    if len(chosen)==3:break
for index,p in enumerate(chosen,1):
    arm=out/f'proposed-patch-{index}';arm.mkdir()
    spec=read(reference/'conditions.json')
    spec['il7ra']['conditions']['C_HOT']['true'][0]['select']="sel('A/*/["+','.join(map(str,p['positions']))+"]')"
    spec['il7ra']['input']='target.cif'
    (arm/'target.cif').write_bytes((reference/'target.cif').read_bytes())
    write_json(arm/'conditions.json',spec)
    proposal_audit={**audit,'hotspots_uniprot':p['positions'],
        'files':{'target.cif':digest(arm/'target.cif'),'conditions.json':digest(arm/'conditions.json')},
        'proposal_status':'not_run; adapter/input review required before execution'}
    write_json(arm/'audit.json',proposal_audit)
    write_json(arm/'proposal.json',{**p,'status':'research_proposal_not_run','submission_eligible':False,
        'limits':'Isolated unglycosylated reference geometry only; not glycan safety or assay accessibility. Source reference provenance unresolved.'})
result={'pool_size':16,'predictors':['esmfold2','boltz'],'pairwise':pairs,'clusters':clusters,'checks':checks,
    'selected_ids':sorted(selected),'selected_pairs':[r for r in pairs if r['left'] in selected and r['right'] in selected],
    'surface':{'reference_to_3DI3_CA_rmsd_A':float(fit.rms),'mapped_common_positions':len(common),
        'native_IL7_contact_positions':native_interface,'lead_contact_union':sorted(covered),'proposed_patches':chosen,
        'candidate_patch_count':len(patches),'sequon_positions':sequons,
        'limits':'No glycan conformers, membrane, receptor partners or full assay construct modeled;3DI3 mutation66 and missing ends remain explicit.'},
    'usalign':{'revision':revision,'binary_sha256':digest(binary),'compile':'clang++ -std=c++11 -O3 -Wno-deprecated-declarations'},
    'scope':'Structural similarity groups are descriptive, not SCOP/CATH assignments, evolutionary families, or binding predictions.',
    'submission_eligible_count':0}
write_json(out/'diversity.json',result)
keep(w/'pipeline/scripts/review-il7ra-diversity.py');keep(w/'outputs/diversity-public-sources-2026-11-02.json')
write_json(out/'manifest.json',{'source_sha256':dict(sorted(sources.items())),
    'output_sha256':{str(p.relative_to(out)):digest(p) for p in sorted(out.rglob('*')) if p.is_file()}})
print(json.dumps({'status':'reviewed','pairs':len(pairs),'patches':chosen,'reference_rmsd':float(fit.rms),
    'group_counts':{m:{k:{t:len(v['complete_link_greedy']) for t,v in d.items()} for k,d in x.items()} for m,x in clusters.items()}},indent=2))
