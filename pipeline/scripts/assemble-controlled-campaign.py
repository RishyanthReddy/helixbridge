"""Verify the full bounded goal and assemble a diagnostic, explicitly reviewed package."""
import argparse
import csv
from datetime import datetime
import itertools
import json
from pathlib import Path
import runpy
import math
from Bio.Align import PairwiseAligner

base=runpy.run_path(str(Path(__file__).with_name('assemble-rehearsal-package.py')))
sha256,read_json,require=(base[name] for name in ['sha256','read_json','require'])


def verify_recorded_inputs(state,workspace,sources):
    root=Path('/cfs/earth/scratch/mekalris/changjiang-2026')
    for remote,expected in state['inputs'].items():
        relative=Path(remote).relative_to(root)
        if str(relative).startswith('src/pipeline/'):
            local=workspace/'pipeline'/relative.relative_to('src/pipeline')
        elif str(relative).startswith('results/'):
            local=workspace/'outputs/execution-evidence'/relative.relative_to('results')
        elif str(relative).startswith('env/') and len(relative.parts)==2:
            local=workspace/'outputs/execution-evidence/controlled-campaign-env-records-v1'/relative.name
        elif str(relative)=='src/IPSAE/ipsae.py':
            local=workspace/'work/vendor/IPSAE/ipsae.py'
        else:
            raise ValueError('Unmapped execution input: '+remote)
        require(local.is_file() and sha256(local)==expected,'Executed input changed or missing: '+remote)
        sources[str(local.relative_to(workspace))]=expected


def verify_recorded_outputs(state,workspace,sources):
    root=Path('/cfs/earth/scratch/mekalris/changjiang-2026/results')
    for remote,expected in state['outputs'].items():
        local=workspace/'outputs/execution-evidence'/Path(remote).relative_to(root)
        require(local.is_file() and sha256(local)==expected,'Declared execution output changed: '+remote)
        sources[str(local.relative_to(workspace))]=expected


def components(ids,edges):
    parent={key:key for key in sorted(ids)}
    def find(key):
        while parent[key]!=key:
            parent[key]=parent[parent[key]];key=parent[key]
        return key
    for left,right in edges:
        left,right=find(left),find(right)
        if left!=right:parent[max(left,right)]=min(left,right)
    return {key:find(key) for key in sorted(ids)}


def verify_robustness(workspace,sources):
    evidence=workspace/'outputs/execution-evidence'
    records=evidence/'rfd4-il7ra-high-s43-v1/candidates.json'
    baseline=read_json(evidence/'rfd4-il7ra-high-s43-v1/evaluation-input/input.json')
    rows=[]
    for seed in [1,2]:
        campaign=f'rfd4-il7ra-high-s43-eval-s{seed}'
        request_path=evidence/f'robust-localfold-campaign-v1/robustness-s{seed}/input.json'
        request=read_json(request_path)
        require(request['candidate_records_sha256']==sha256(records),'Robustness candidate changed')
        for key in ['target','partner','construct_status','protocol_status']:
            require(request[key]==baseline[key],'Robustness input differs: '+key)
        require(request['settings']['seed']==seed,'Robustness prediction seed mismatch')
        require({k:v for k,v in request['settings'].items() if k!='seed'}==
                {k:v for k,v in baseline['settings'].items() if k!='seed'},'Non-seed settings changed')
        review_path=evidence/f'{campaign}-review-v1/review.json'
        review=read_json(review_path)
        require(review['candidate_records_sha256']==sha256(records) and not review['submission_eligible'],
                'Robustness review eligibility/identity changed')
        audit_path=review_path.parent/'independent-pose-audit.json';audit=read_json(audit_path)
        require(audit['source_review_sha256']==sha256(review_path),'Robustness independent audit mismatch')
        for path in [request_path,review_path,audit_path]:sources[str(path.relative_to(workspace))]=sha256(path)
        for model in ['esmfold2','boltz']:
            prediction=evidence/f'{campaign}-{model}-v1/prediction'
            state_path=prediction.parent/'task-state.json';state=read_json(state_path)
            require(state['status']=='success' and state['exit_code']==0,'Robustness predictor failed')
            verify_recorded_inputs(state,workspace,sources)
            verify_recorded_outputs(state,workspace,sources)
            metrics_path=prediction/'metrics.json';metrics=read_json(metrics_path)
            base['verify_state_file'](state,'outputs','/prediction/metrics.json',metrics_path)
            require(metrics['input_sha256']==sha256(request_path),'Robustness predictor input mismatch')
            actual_seed=metrics['settings']['seed'] if model=='esmfold2' else metrics['seed']
            require(actual_seed==seed,'Predictor did not record requested seed')
            for filename,expected in metrics['artifacts'].items():
                path=prediction/filename;require(sha256(path)==expected,'Robustness artifact changed')
                sources[str(path.relative_to(workspace))]=expected
            summary=review['predictions'][model]
            require(summary['metrics_sha256']==sha256(metrics_path),'Robustness metrics changed')
            require(math.isclose(summary['target_aligned_binder_ca_rmsd_angstrom'],
                audit['generator_comparisons'][model]['target_aligned_binder_ca_rmsd'],abs_tol=1e-4),
                'Robustness independent geometry mismatch')
            sources[str(metrics_path.relative_to(workspace))]=sha256(metrics_path)
            sources[str(state_path.relative_to(workspace))]=sha256(state_path)
            rows.append({'seed':seed,'model':model,**summary})
    return rows


def budget_audit(workspace,ledger,scheduler_path):
    jobs={row['job_id']:row for row in ledger['jobs']};observed={};events=[]
    for line in scheduler_path.read_text().splitlines():
        if not line.strip():continue
        job,name,state,exit_code,start,end,elapsed,tres=line.split('|')
        require(job in jobs and job not in observed,'Scheduler job identity mismatch')
        require(state in {'COMPLETED','FAILED','TIMEOUT','OUT_OF_MEMORY','CANCELLED','NODE_FAIL','PREEMPTED'},
                'All GPU allocations must be terminal for the final review')
        require('gres/gpu=1' in tres,'Not a one-GPU allocation')
        observed[job]={'name':name,'state':state,'exit_code':exit_code,'gpu_seconds':int(elapsed)}
        events.extend([(datetime.fromisoformat(start),1),(datetime.fromisoformat(end),-1)])
    require(set(jobs)==set(observed),'GPU ledger not fully covered by accounting')
    active=peak=0
    for _,change in sorted(events):active+=change;peak=max(peak,active)
    total=sum(row['gpu_seconds'] for row in observed.values())
    require(peak<=2 and total<=5400,'Authorized GPU budget/concurrency exceeded')
    return {'gpu_seconds':total,'gpu_minutes':total/60,'maximum_concurrent_gpus':peak,'allocations':observed}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--selection',type=Path,required=True)
    args=parser.parse_args();workspace=args.workspace.resolve();out=args.output_dir.resolve()
    require(not out.exists(),'Use a fresh package directory')
    evidence=workspace/'outputs/execution-evidence';folder=evidence/'robust-localfold-campaign-v1'
    sources={}
    plan=read_json(folder/'campaign-plan.json');ledger=read_json(folder/'gpu-budget.json')
    selection=read_json(args.selection)
    require(selection['submission_eligible_count']==0,'Selection cannot promote submission eligibility')
    cases=[base['verify_case'](workspace,case,sources) for case in base['CASES']]
    failures=[]
    for seed in plan['design_seeds']:
        campaign=f'rfd4-il7ra-campaign-s{seed}'
        state_path=evidence/f'{campaign}-v1/campaign-task-state.json'
        if not state_path.exists():
            failures.append({'seed':seed,'status':'not_run_or_unaccounted'});continue
        state=read_json(state_path);sources[str(state_path.relative_to(workspace))]=sha256(state_path)
        if state['status']!='success' or state.get('exit_code')!=0:
            failures.append({'seed':seed,'status':state['status'],'error':state.get('error')});continue
        verify_recorded_inputs(state,workspace,sources)
        verify_recorded_outputs(state,workspace,sources)
        for name in [f'{campaign}-v1/task-state.json',f'{campaign}-esmfold2-v1/task-state.json',
                     f'{campaign}-boltz-v1/task-state.json']:
            recorded=read_json(evidence/name)
            verify_recorded_inputs(recorded,workspace,sources)
            verify_recorded_outputs(recorded,workspace,sources)
        generation=evidence/f'{campaign}-v1/prediction'
        for name,expected in read_json(generation/'audit.json')['raw_structure_hashes'].items():
            path=generation/name
            require(sha256(path)==expected,'Native generated structure changed')
            sources[str(path.relative_to(workspace))]=expected
        case=base['verify_case'](workspace,{'campaign':campaign,'label':f'new seed {seed}',
            'decision':'manual_research_review','reason':'bounded same-recipe seed variation'},sources)
        review_dir=evidence/f'{campaign}-review-v1';review_path=review_dir/'review.json'
        context_path=review_dir/'target-context-audit.json';context=read_json(context_path)
        require(context['candidate_id']==case['candidate_id'] and context['review_sha256']==sha256(review_path),
                'Campaign target-context mismatch')
        for model in ['esmfold2','boltz']:
            require(context['poses'][model]['structure_sha256']==read_json(review_path)['predictions'][model]['model_cif_sha256'],
                    'Campaign context pose changed')
        for output in state['outputs']:
            local=evidence/Path(output).relative_to('/cfs/earth/scratch/mekalris/changjiang-2026/results')
            require(sha256(local)==state['outputs'][output],'Campaign declared output changed')
        sources[str(context_path.relative_to(workspace))]=sha256(context_path)
        case['target_context']=context
        case['cross_refold_core_binder_rmsd']=read_json(review_dir/'independent-pose-audit.json')['predictor_to_predictor_core_aligned_binder_ca_rmsd']
        case['seed']=seed;cases.append(case)
    require(len({case['candidate_id'] for case in cases})==len(cases),'Duplicate candidate ID')
    require(len({case['sequence'] for case in cases})==len(cases),'Exact sequence duplicates in pool')
    candidate_ids={case['candidate_id'] for case in cases}
    require(set(selection['candidate_reviews'])<=candidate_ids,'Selection names an unknown candidate')
    require(all(case['candidate_id'] in selection['candidate_reviews'] for case in cases if 'seed' in case),
            'Every new candidate needs an explicit selection review')
    robustness=verify_robustness(workspace,sources)
    scheduler=evidence/'controlled-campaign-scheduler-v1/gpu-allocations.txt'
    budget=budget_audit(workspace,ledger,scheduler)
    aligner=PairwiseAligner(mode='global',match_score=1,mismatch_score=0,open_gap_score=0,extend_gap_score=0)
    pairs=[];sequence_edges=[];site_edges=[]
    for left,right in itertools.combinations(cases,2):
        identity=float(aligner.score(left['sequence'],right['sequence'])/max(len(left['sequence']),len(right['sequence'])))
        entry={'left':left['candidate_id'],'right':right['candidate_id'],'lcs_fraction_of_longer':identity}
        if identity>=.8:sequence_edges.append((entry['left'],entry['right']))
        if left.get('target_context') and right.get('target_context'):
            for model in ['esmfold2','boltz']:
                a=set(left['target_context']['poses'][model]['target_contact_positions_lt_5a'])
                b=set(right['target_context']['poses'][model]['target_contact_positions_lt_5a'])
                value=len(a&b)/len(a|b) if a|b else None
                entry[model+'_target_contact_jaccard']=value
                if model=='esmfold2' and value is not None and value>=.5:site_edges.append((entry['left'],entry['right']))
        pairs.append(entry)
    site_ids={case['candidate_id'] for case in cases if case.get('target_context')}
    groups={'sequence_lcs_80_components':components(candidate_ids,sequence_edges),
            'esm_target_contact_jaccard_50_components':components(site_ids,site_edges),
            'unmeasured_site_candidate_ids':sorted(candidate_ids-site_ids),
            'scope':'Connected components are descriptive heuristics; not evolutionary/structural-fold families or calibrated binding criteria.'}
    out.mkdir(parents=True)
    rows=[]
    for case in cases:
        decision=selection['candidate_reviews'].get(case['candidate_id'],{'decision':case['decision'],'reason':case['reason']})
        for model,metrics in case['predictors'].items():
            rows.append({'candidate_id':case['candidate_id'],'label':case['label'],'predictor':model,
                'iptm':metrics['iptm'],'ipsae_target_to_binder':metrics['ipsae_directional'][0],
                'ipsae_binder_to_target':metrics['ipsae_directional'][1],
                'generator_to_refold_binder_rmsd_angstrom':metrics['target_aligned_binder_ca_rmsd_angstrom'],
                'heavy_atom_pairs_lt_2a':metrics['heavy_atom_pairs_lt_2a'],'DE_fraction':case['de_fraction'],
                'review_decision':decision['decision'],'review_reason':decision['reason'],'submission_eligible':'false'})
    loaded=base['write_csv'](out/'REHEARSAL_ONLY_scores.csv',list(rows[0]),rows)
    require(all(row['submission_eligible']=='false' for row in loaded),'CSV eligibility guard failed')
    followups=[]
    for case in cases:
        review=selection['candidate_reviews'].get(case['candidate_id'],{})
        if review.get('decision') in {'repeat_tested_research_lead','provisional_research_lead','research_backup'}:
            followups.append({'candidate_id':case['candidate_id'],'target_id':'il7ra','sequence':case['sequence'],
                'role':review['decision'],'submission_eligible':'false','reason':review['reason']})
    exported=base['write_csv'](out/'REHEARSAL_ONLY_followups.csv',
        ['candidate_id','target_id','sequence','role','submission_eligible','reason'],followups)
    require(all(row['submission_eligible']=='false' and row['sequence'] in {case['sequence'] for case in cases}
                for row in exported),'Follow-up export guard failed')
    base['write_csv'](out/'EMPTY_submission_shortlist.csv',['candidate_id','target_id','sequence'],[])
    (out/'comparison.json').write_text(json.dumps({'status':'internal_rehearsal_only','cases':cases,'failures':failures,
        'robustness_added_seeds':robustness,'budget':budget,'diversity':groups,'pairwise_diversity':pairs,
        'selection':selection,'submission_eligible_count':0},indent=2,allow_nan=False)+'\n')
    report=f'''# Bounded IL-7Rα campaign review — internal only

{selection['summary']}

The plan contained 12 new seed-diverse designs. This package has
{sum('seed' in case for case in cases)} complete new reviews and {len(failures)} failed/unrun cases,
plus four preserved RFD4 baselines. No binding, affinity, expression, glycan
compatibility or official admission is established. The submission shortlist is empty.

| Case | ESM ipSAE min | Boltz ipSAE min | Generator→refold shift, ESM / Boltz | Heavy-atom pairs <2 Å, ESM / Boltz | D/E fraction | Research review |
|---|---:|---:|---:|---:|---:|---|
'''
    for case in cases:
        esm=case['predictors']['esmfold2'];boltz=case['predictors']['boltz']
        decision=selection['candidate_reviews'].get(case['candidate_id'],{'decision':case['decision']})
        report+=(f"| {case['label']} | {min(esm['ipsae_directional']):.3f} | {min(boltz['ipsae_directional']):.3f} | "
                 f"{esm['target_aligned_binder_ca_rmsd_angstrom']:.2f} / {boltz['target_aligned_binder_ca_rmsd_angstrom']:.2f} Å | "
                 f"{esm['heavy_atom_pairs_lt_2a']} / {boltz['heavy_atom_pairs_lt_2a']} | {case['de_fraction']:.0%} | {decision['decision']} |\n")
    report+=f'''
All designs used the same reviewed target-only initialization, 60 new binder
residues, thinking_high schedule and distinct predeclared seeds 101–112. The
generator reference covers positions 37–231; all common refolds use the complete
declared 1–236 interval. The reference's origin and the organizer's processing,
glycan occupancy and exact screen protocol remain unresolved.

The original seed-43 candidate was additionally tested with prediction seeds 1
and 2 in both models. Inputs and non-seed settings were checked against the
original seed-0 request, and independent coordinate audits reproduced the pose
calculations. This measures sampling robustness, not binding.

LocalFold AF2-Multimer completed three mapped diagnostic complexes on the Mac M3
using Node/Dawn WebGPU, not the L40S. The actual bundle was int5. Versioned exports
preserve their exact imported alignment. The full-precision native comparison
missed the predeclared numerical gate, including with explicit f32 compute, so
LocalFold remains optional inspection and contributes no ranking score here.
The browser UI was not qualified by the Node kernel checks.

The GPU ledger and scheduler records cover **{budget['gpu_minutes']:.2f} GPU-minutes**,
maximum **{budget['maximum_concurrent_gpus']} simultaneous one-GPU allocations**, within
the authorized 90 GPU-minute cap. Failed allocations, if any, are included.

`comparison.json` preserves pairwise sequence/contact diversity and all outcomes.
Sequence and contact connected components are descriptive heuristics, not
structural-fold/evolutionary families. Missing site measurements are explicit.
Both models' directional scores remain separate: the experimental benchmark did
not establish a reliable benefit from a consensus cutoff. Research selection is
manual and provisional; no calibrated binding probability or universal generator
success rate is inferred from this single target and fixed recipe.

`REHEARSAL_ONLY_scores.csv` is diagnostic; `REHEARSAL_ONLY_followups.csv` contains
the explicitly selected research leads/backups and their sequences, all marked
ineligible for submission. `EMPTY_submission_shortlist.csv` has
zero entries. `manifest.json` records source and output hashes.
'''
    (out/'REVIEW.md').write_text(report)
    directories=['robust-localfold-campaign-v1','controlled-campaign-scheduler-v1','controlled-campaign-env-records-v1']
    directories += [path.name for path in evidence.glob('localfold-*') if path.is_dir()]
    for directory in directories:
        for path in sorted((evidence/directory).rglob('*')):
            if path.is_file() and path.suffix!='.lock':sources[str(path.relative_to(workspace))]=sha256(path)
    for path in [Path(__file__).resolve(),Path(__file__).with_name('assemble-rehearsal-package.py').resolve(),args.selection.resolve()]:
        sources[str(path.relative_to(workspace))]=sha256(path)
    outputs={path.name:sha256(path) for path in out.iterdir() if path.is_file()}
    (out/'manifest.json').write_text(json.dumps({'source_sha256':sources,'output_sha256':outputs,
        'submission_eligible_count':0,'official_submission_schema':False},indent=2)+'\n')
    print(json.dumps({'status':'ok','new_cases':sum('seed' in case for case in cases),'failures':len(failures),
        'predictor_rows':len(rows),'verified_sources':len(sources),'gpu_minutes':budget['gpu_minutes']}))


if __name__=='__main__':main()
