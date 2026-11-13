"""Independently verify all six site-pilot cases and retain separate model evidence."""
import argparse
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import re
import runpy
import subprocess
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest,write_json
from binder_campaign.pose_review import read_pair,align_pair
from binder_campaign.sequence_review import sequence_diagnostic,overlap_diagnostic
from binder_campaign.structure import AA3

parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--output-dir',type=Path,required=True)
args=parser.parse_args();w=args.workspace.resolve();out=args.output_dir.resolve()
if out.exists():raise ValueError('Use a fresh review directory')
e=w/'outputs/execution-evidence';folder=e/'site-diversity-pilot-v1';sources={}
def keep(p,expected=None):
    h=digest(p)
    if expected and h!=expected:raise ValueError('Changed source: '+str(p))
    sources[str(p.relative_to(w))]=h;return p
def read(p):return json.loads(keep(p).read_text())
prior=w/'outputs/il7ra-diversity-2026-11-02-v2';manifest=read(prior/'manifest.json')
for n,h in manifest['source_sha256'].items():keep(w/n,h)
for n,h in manifest['output_sha256'].items():keep(prior/n,h)
helper=runpy.run_path(str(w/'pipeline/scripts/assemble-controlled-campaign.py'))
def verify_state(p):
    state=read(p)
    if state['status']!='success' or state['exit_code']!=0:raise ValueError('Incomplete case/stage: '+str(p))
    helper['verify_recorded_inputs'](state,w,sources);helper['verify_recorded_outputs'](state,w,sources)
    return state
plan=read(folder/'execution-plan.json');ledger=read(folder/'gpu-budget.json')
if ledger['gpu_seconds_cap']!=5400 or ledger['max_concurrent_gpus']!=2 or ledger.get('unresolved_submission'):
    raise ValueError('Resource envelope changed or ambiguous submission')
jobs={r['job_id']:r for r in ledger['jobs']};events=[];allocations={}
for line in keep(folder/'gpu-allocations.txt').read_text().splitlines():
    if not line.strip():continue
    job,name,state,code,start,end,elapsed,tres=line.split('|')
    if job not in jobs or job in allocations or state not in ('COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY'):
        raise ValueError('Missing/unfinished/duplicate scheduler row')
    if 'gres/gpu=1' not in tres:raise ValueError('Expected one GPU per allocation')
    allocations[job]={'name':name,'state':state,'exit_code':code,'seconds':int(elapsed)}
    events.extend([(datetime.fromisoformat(start),1),(datetime.fromisoformat(end),-1)])
if set(allocations)!=set(jobs):raise ValueError('Incomplete resource accounting')
active=peak=0
for _,change in sorted(events):active+=change;peak=max(peak,active)
seconds=sum(r['seconds'] for r in allocations.values())
if seconds>5400 or peak>2 or active:raise ValueError('Budget or concurrency exceeded')
for batch in ('gate','main'):
    stage=folder/f'staging/{batch}';verify_state(stage/'task-state.json')
    staged=read(stage/'predictions-v1/staging-state.json');prep=read(stage/'preparation.json')
    env=read(stage/'environment-archive.json');weights=read(stage/'checkpoint-archive.json')
    if staged['status']!='success' or staged['preparation_sha256']!=digest(stage/'preparation.json') \
            or staged['environment_extraction']['archive_sha256']!=env['sha256'] \
            or staged['checkpoint_extraction']['archive_sha256']!=weights['sha256']:
        raise ValueError('Staged runtime verification failed')
    original=read(stage/'predictions-v1/original-checkpoints.json');effective=read(stage/'predictions-v1/runtime-checkpoints.json')
    if len(original)!=1 or len(effective)!=1 or {k:v for k,v in original[0].items() if k!='path'}!={k:v for k,v in effective[0].items() if k!='path'}:
        raise ValueError('Effective checkpoint changed more than paths')
target=read(w/'pipeline/data/targets/il7ra/manifest.json')['sequence']
old=read(w/'outputs/esm-recovery-review-2026-11-02-v2/review.json')['sequence_context_review_unchanged']['research_followups']
lead_sites={row['candidate_id']:{m:set(p['target_contact_positions_lt_5A']) for m,p in row['poses'].items()} for row in old}
corpus_dir=e/'finalist-reference-corpus-v1';cm=read(corpus_dir/'manifest.json')
for n,h in cm['sources'].items():keep(w/n,h)
for n,h in cm['outputs'].items():keep(corpus_dir/n,h)
corpus=read(corpus_dir/'corpus.json')['rows']
out.mkdir(parents=True);(out/'fold-alignments').mkdir();(out/'binders').mkdir()
binary=keep(w/'work/vendor/USalign/USalign');reverse={v:k for k,v in AA3.items()}
cases=[]
for case in plan['case_stems']:
    campaign='site-'+case;directory=e/f'{campaign}-v1';record_path=directory/'candidates.json';record=read(record_path)['candidates'][0]
    verify_state(directory/'case-state.json');verify_state(directory/'task-state.json');verify_state(e/f'{campaign}-boltz-v1/task-state.json')
    reference=record['generator_audit']['reference_audit'];genpath=directory/'prediction/model.cif'
    if record['generator_audit']['seed']!=int(case.rsplit('-s',1)[1]):raise ValueError('Executed generation seed mismatch')
    if record['generator_audit']['model']['revision']!='621b785abf9d61dd24f4b81ae4dbd1330728f030':raise ValueError('RFD4 checkpoint changed')
    keep(genpath,record['generator_structure_sha256'])
    for n,h in record['generator_audit']['raw_structure_hashes'].items():keep(directory/'prediction'/n,h)
    gen=read_pair(genpath,reference['reference_sequence'],record['sequence'],reference['positions'])
    review=read(e/f'{campaign}-review-v1/review.json');independent=read(e/f'{campaign}-review-v1/independent-pose-audit.json')
    context=read(e/f'{campaign}-review-v1/target-context-audit.json');starting=read(directory/'starting-input-audit.json')
    if review['candidate_records_sha256']!=digest(record_path) or independent['source_review_sha256']!=digest(e/f'{campaign}-review-v1/review.json'):
        raise ValueError('Review identity changed')
    if context['review_sha256']!=digest(e/f'{campaign}-review-v1/review.json') or starting['supplied_starting_binder_sequence_or_coordinates']:
        raise ValueError('Context or initialization audit differs')
    arm=case.rsplit('-s',1)[0];hotspots=next(a['hotspots_uniprot'] for a in plan['arms'] if a['arm']==arm)
    if reference['hotspots_uniprot']!=hotspots:raise ValueError('Native input hotspot audit differs from declared arm')
    if starting['source_conditions_sha256']!=digest(folder/f'inputs/{arm}/conditions.json') or starting['source_target_cif_sha256']!=digest(folder/f'inputs/{arm}/target.cif') \
            or starting['input_review_sha256']!=digest(folder/'input-review.json'):
        raise ValueError('Starting-input review changed')
    request=directory/'evaluation-input/input.json';request_data=read(request);poses={};models={}
    for model in ('esmfold2','boltz'):
        prediction=e/f'{campaign}-{model}-v1/prediction';metrics=read(prediction/'metrics.json')
        if model=='esmfold2':
            batch='gate' if case in ('control-s201','patch139-s201') else 'main'
            copied=read(prediction.parent/'staged-source.json')
            if copied['batch_state_sha256']!=digest(folder/f'staging/{batch}/task-state.json'):raise ValueError('Copy source batch changed')
            original=folder/f'staging/{batch}/predictions-v1/seed-{case}/prediction'
            for filename,expected in copied['files'].items():
                keep(prediction/filename,expected);keep(original/filename,expected)
        if metrics['input_sha256']!=digest(request):raise ValueError('Prediction request mismatch')
        if request_data['settings']['seed']!=0 or request_data['partner']['msa'] is not None:raise ValueError('Evaluation seed/MSA policy changed')
        if model=='esmfold2':
            if metrics['model_revisions']!={'biohub/ESMFold2':'69869f737beffec5294845ede23db5fc0b4f509e'} or metrics['settings']!=request_data['settings'] \
                    or metrics['target_msa_sha256']!=digest(w/'pipeline/data/targets/il7ra/msa/target.a3m'):
                raise ValueError('ESMFold2 checkpoint/settings/MSA changed')
        elif metrics['seed']!=0 or metrics['samples']!=1 or not metrics['target_only_precomputed_msa'] or metrics['templates_or_pocket_constraints']:
            raise ValueError('Boltz settings changed')
        if request_data['target']['sequence']!=target or request_data['partner']['sequence']!=record['sequence']:
            raise ValueError('Scientific sequence mismatch')
        for n,h in metrics['artifacts'].items():keep(prediction/n,h)
        raw=keep(prediction/('raw.npz' if model=='esmfold2' else 'boltz_results_input/predictions/input/pae_input_model_0.npz'))
        pae=np.array(read(prediction/'pae.json')['pae'])
        if pae.shape!=(296,296) or not np.isfinite(pae).all() or not np.array_equal(pae,np.load(raw)['pae']):raise ValueError('Raw PAE mismatch')
        directions=[r for r in metrics['ipsae']['pairwise'] if r['type']=='asym']
        if [(r['chain1'],r['chain2']) for r in directions]!=[('A','B'),('B','A')]:raise ValueError('ipSAE chain order differs')
        pose=read_pair(prediction/'model.cif',target,record['sequence'],list(range(1,237)));poses[model]=pose
        fit=align_pair(pose,gen,reference['positions'])
        if not math.isclose(fit['target_aligned_binder_ca_rmsd_A'],review['predictions'][model]['target_aligned_binder_ca_rmsd_angstrom'],abs_tol=1e-4):
            raise ValueError('Independent geometry differs')
        sites=set(pose['target_contacts_lt_5A'])
        overlaps={key:len(sites&data[model])/len(sites|data[model]) if sites|data[model] else None for key,data in lead_sites.items()}
        pdb=out/'binders'/f'{case}-{model}.pdb'
        pdb.write_text('\n'.join(f'ATOM  {i:5d}  CA  {reverse[aa]:3s} B{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C'
            for i,(aa,(x,y,z)) in enumerate(zip(record['sequence'],pose['binder_ca']),1))+'\nTER\nEND\n')
        folds=[]
        for key in sorted(lead_sites):
            raw_text=subprocess.check_output([str(binary),str(pdb),str(prior/f'binders/{key}-{model}.pdb'),'-mol','prot'],text=True)
            (out/'fold-alignments'/f'{case}-{model}-{key}.txt').write_text(raw_text)
            scores=[float(x) for x in re.findall(r'TM-score=\s*([0-9.]+)',raw_text)]
            folds.append({'lead':key,'tm_scores':scores})
        models[model]={'iptm':metrics['iptm'],'ipsae_directional':[r['ipsae'] for r in directions],
            'generator_to_refold':fit,'heavy_atom_pairs_lt_2A':pose['heavy_atom_pairs_lt_2A'],
            'target_contacts':sorted(sites),'declared_hotspots_contacted':sorted(sites&set(hotspots)),
            'signal_peptide_contact_positions':sorted(sites&set(range(1,21))),
            'contacts_outside_generator_reference':sorted(sites-set(reference['positions'])),
            'contact_overlap_with_leads':overlaps,'maximum_lead_site_jaccard':max(overlaps.values()),'fold_comparisons':folds}
    public=[{**{k:r[k] for k in ('source','id','target')},**overlap_diagnostic(record['sequence'],r['sequence'])} for r in corpus]
    near=[r for r in public if r['exact_duplicate'] or r['over_90pct_contiguous_in_either_direction']]
    cross=align_pair(poses['esmfold2'],poses['boltz'],reference['positions'])
    eligible=all(m['maximum_lead_site_jaccard']<.3 and m['heavy_atom_pairs_lt_2A']==0 for m in models.values()) and cross['target_aligned_binder_ca_rmsd_A']<=3
    cases.append({'case':case,'arm':arm,'candidate_id':record['candidate_id'],'sequence':record['sequence'],
        'sequence_diagnostics':sequence_diagnostic(record['sequence']),'public_reference_rows':len(corpus),'public_overlap_flags':near,
        'generation_hotspots_contacted':sorted(set(gen['target_contacts_lt_5A'])&set(hotspots)),
        'models':models,'cross_refold':cross,'target_context':context,'conditional_followup_criteria_met':eligible,
        'submission_eligible':False})
if len({r['sequence'] for r in cases})!=6:raise ValueError('Duplicate sequences in pilot')
qualifying=sorted([r for r in cases if r['conditional_followup_criteria_met']],key=lambda r:(-min(r['models']['esmfold2']['ipsae_directional']),-min(r['models']['boltz']['ipsae_directional']),r['case']))
result={'status':'six_cases_reviewed_research_only','cases':cases,'budget':{'seconds':seconds,'maximum_concurrency':peak,'allocations':allocations},
    'conditional_followup_case':qualifying[0]['case'] if qualifying else None,
    'limitations':'Two generation seeds per arm; no wet-lab binding, global novelty, glycan compatibility or official screen equivalence established.',
    'submission_eligible_count':0}
write_json(out/'review.json',result)
fields=['case','candidate_id','predictor','iptm','ipsae_target_to_binder','ipsae_binder_to_target','generator_to_refold_A','maximum_lead_site_jaccard','close_pairs','submission_eligible']
with (out/'REHEARSAL_ONLY_scores.csv').open('x',newline='') as stream:
    writer=csv.DictWriter(stream,fields);writer.writeheader()
    for row in cases:
        for model,metrics in row['models'].items():writer.writerow({'case':row['case'],'candidate_id':row['candidate_id'],'predictor':model,
            'iptm':metrics['iptm'],'ipsae_target_to_binder':metrics['ipsae_directional'][0],'ipsae_binder_to_target':metrics['ipsae_directional'][1],
            'generator_to_refold_A':metrics['generator_to_refold']['target_aligned_binder_ca_rmsd_A'],
            'maximum_lead_site_jaccard':metrics['maximum_lead_site_jaccard'],'close_pairs':metrics['heavy_atom_pairs_lt_2A'],'submission_eligible':'false'})
with (out/'EMPTY_submission_shortlist.csv').open('x',newline='') as stream:csv.writer(stream).writerow(['candidate_id','target_id','sequence','submission_eligible'])
keep(w/'pipeline/scripts/assemble-site-pilot-review.py')
write_json(out/'manifest.json',{'source_sha256':dict(sorted(sources.items())),
    'output_sha256':{str(p.relative_to(out)):digest(p) for p in sorted(out.rglob('*')) if p.is_file()},'submission_eligible_count':0})
print(json.dumps({'status':'reviewed','sources':len(sources),'conditional_followup':result['conditional_followup_case'],'budget_seconds':seconds,
    'cases':[{k:r[k] for k in ('case','candidate_id','conditional_followup_criteria_met')} for r in cases]},indent=2))
