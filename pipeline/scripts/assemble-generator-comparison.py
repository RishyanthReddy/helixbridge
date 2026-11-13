"""Verify the bounded Mosaic pilot alongside all four preserved RFD4 rehearsals."""
import argparse
import csv
import json
import math
from pathlib import Path
import runpy

base = runpy.run_path(str(Path(__file__).with_name('assemble-rehearsal-package.py')))
sha256, read_json, require = (base[name] for name in ('sha256', 'read_json', 'require'))


def verify_mosaic(workspace, sources):
    evidence = workspace / 'outputs/execution-evidence'
    generation = evidence / 'mosaic-il7ra-design-v1'
    review_dir = evidence / 'mosaic-il7ra-review-v1'
    def read(path):
        sources[str(path.relative_to(workspace))] = sha256(path)
        return read_json(path)
    records_path = generation / 'candidates.json'
    records = read(records_path)['candidates']
    require(len(records) == 1, 'Expected one Mosaic pilot candidate')
    record = records[0]
    audit = read(generation / 'audit.json')
    review_path = review_dir / 'review.json'
    review = read(review_path)
    independent = read(review_dir / 'independent-pose-audit.json')
    context = read(review_dir / 'target-context-audit.json')
    request_path = generation / 'evaluation-input/input.json'
    request = read(request_path)
    target_path = workspace / 'pipeline/data/targets/il7ra/manifest.json'
    target = read(target_path)
    sequence = record['sequence']
    require(record['candidate_id'] == review['candidate_id'] == independent['candidate_id']
            == context['candidate_id'] == request['candidate_id'], 'Mosaic candidate identity mismatch')
    require(sequence == audit['binder_sequence'] == review['sequence'] == request['partner']['sequence']
            and len(sequence) == 60 and set(sequence) <= base['ALPHABET'], 'Mosaic sequence mismatch')
    require(all(item['submission_eligible'] is False for item in (record, audit, review, context))
            and record['campaign_kind'] == 'reference_rehearsal' and audit['mode'] == 'design',
            'Mosaic rehearsal eligibility guard failed')
    require(audit['mosaic_revision']=='5937f37164bcb28bc6f1000f10134145438e5971'
            and audit['joltz_revision']=='ed0f04257dac85bd4b7bf45521cc280f86d38ded'
            and audit['boltz_fork_revision']=='7ea718a1440ecbe8e2418317192b501544147edd',
            'Mosaic source revisions differ from the qualified pilot')
    reference=record['generator_audit']['reference_audit']
    require(reference['positions']==list(range(1,237))
            and reference['alignment_positions']==list(range(37,232))
            and reference['reference_sequence']==target['sequence'], 'Mosaic reference mapping changed')
    require(review['candidate_records_sha256'] == request['candidate_records_sha256'] == sha256(records_path),
            'Mosaic record hash mismatch')
    require(independent['source_review_sha256'] == context['review_sha256'] == sha256(review_path),
            'Mosaic review audit hash mismatch')
    require(audit['adapter_sha256'] == sha256(workspace / 'pipeline/scripts/mosaic-il7ra.py')
            and audit['environment_freeze_sha256'] == sha256(evidence / 'mosaic-install-v1/mosaic-boltz2-freeze.txt'),
            'Mosaic executable/environment record changed')
    require(audit['target_manifest_sha256'] == request['target_manifest_sha256'] == sha256(target_path)
            and request['target']['sequence'] == target['sequence'], 'Mosaic full target mismatch')
    require(audit['settings']['target_interval'] == [1,236] and audit['settings']['templates'] is False
            and audit['settings']['starting_binder'] == 'random simplex probabilities; no known-positive input',
            'Mosaic starting recipe changed')
    require(record['prediction_relationships']['boltz'] == 'same_model_family_as_design_objective',
            'Mosaic Boltz relationship missing')
    for filename, key in [('model.cif','model_sha256'), ('raw.npz','raw_sha256')]:
        path = generation / filename
        require(sha256(path) == audit[key], 'Mosaic generated artifact changed: '+filename)
        sources[str(path.relative_to(workspace))] = sha256(path)
    require(sha256(generation/'model.cif') == record['generator_structure_sha256']
            == review['generation']['generator_pose_sha256'], 'Mosaic generator pose mismatch')
    export = read(review_dir/'export-audit.json')
    csv_path = review_dir/'REHEARSAL_ONLY.csv'
    require(export['round_trip_checked'] and not export['official_submission_schema']
            and export['csv_sha256'] == sha256(csv_path), 'Mosaic diagnostic export mismatch')
    with csv_path.open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    require(len(rows)==1 and rows[0]['sequence']==sequence and rows[0]['submission_eligible']=='False',
            'Mosaic diagnostic CSV guard failed')
    sources[str(csv_path.relative_to(workspace))] = sha256(csv_path)
    result = {'candidate_id':record['candidate_id'], 'sequence':sequence, 'label':'Mosaic, seed 42',
              'decision':'pilot_only_generator_promotion_deferred', 'de_fraction':review['sequence_review']['DE_fraction'],
              'generation_elapsed_seconds':audit['elapsed_seconds'], 'generation_jax_memory_stats':audit['memory_stats'],
              'predictors':{}, 'target_context':context}
    for model in ('esmfold2','boltz'):
        prediction = evidence / f'mosaic-il7ra-{model}-v1/prediction'
        metrics_path = prediction/'metrics.json'
        metrics = read(metrics_path)
        state = read(prediction.parent/'task-state.json')
        require(state['status']=='success' and state['exit_code']==0, model+' Mosaic evaluation failed')
        base['verify_state_file'](state,'outputs','/prediction/metrics.json',metrics_path)
        require(metrics['input_sha256']==sha256(request_path), model+' Mosaic evaluation input changed')
        summary = review['predictions'][model]
        require(sha256(metrics_path)==summary['metrics_sha256'], model+' Mosaic metrics changed')
        for filename, expected in metrics['artifacts'].items():
            path = prediction/filename
            require(sha256(path)==expected, model+' Mosaic artifact changed: '+filename)
            sources[str(path.relative_to(workspace))] = expected
        pose_hash=sha256(prediction/'model.cif')
        require(pose_hash==summary['model_cif_sha256']==context['poses'][model]['structure_sha256'],
                model+' Mosaic pose mismatch')
        matrix=read_json(prediction/'pae.json')['pae']
        require(len(matrix)==296 and all(len(row)==296 for row in matrix)
                and all(isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
                        for row in matrix for value in row), model+' Mosaic PAE mapping invalid')
        directions=[row for row in metrics['ipsae']['pairwise'] if row['type']=='asym']
        require([(row['chain1'],row['chain2']) for row in directions]==[('A','B'),('B','A')]
                and [row['ipsae'] for row in directions]==summary['ipsae_directional'],
                model+' Mosaic directional score mapping invalid')
        require(math.isclose(metrics['iptm'],summary['iptm'],abs_tol=1e-9)
                and math.isclose(summary['target_aligned_binder_ca_rmsd_angstrom'],
                    independent['generator_comparisons'][model]['target_aligned_binder_ca_rmsd'],abs_tol=1e-4),
                model+' Mosaic independently audited metrics disagree')
        result['predictors'][model]={'iptm':summary['iptm'],'ipsae_directional':summary['ipsae_directional'],
            'target_aligned_binder_ca_rmsd_angstrom':summary['target_aligned_binder_ca_rmsd_angstrom'],
            'heavy_atom_pairs_lt_2a':summary['contacts']['heavy_atom_pairs_lt_2A'],
            'peak_reserved_mib':metrics['peak_reserved_mib'],
            'relationship':'separate_model_from_design' if model=='esmfold2' else 'same_model_family_as_design'}
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    workspace=args.workspace.resolve(); out=args.output_dir.resolve()
    require(not out.exists(),'Use a fresh comparison directory')
    sources={}
    cases=[base['verify_case'](workspace,case,sources) for case in base['CASES']]
    mosaic=verify_mosaic(workspace,sources); cases.append(mosaic)
    require(len({case['candidate_id'] for case in cases})==5 and len({case['sequence'] for case in cases})==5,
            'Duplicate candidate in comparison')
    for path in [Path(__file__).resolve(),Path(__file__).with_name('assemble-rehearsal-package.py').resolve(),
                 workspace/'pipeline/scripts/mosaic-il7ra.py',
                 workspace/'outputs/execution-evidence/mosaic-install-v1/mosaic-boltz2-freeze.txt']:
        sources[str(path.relative_to(workspace))]=sha256(path)
    evidence=workspace/'outputs/execution-evidence'
    for directory in ['mosaic-scheduler-audit-v1','grouped-screen-validation-v2','mosaic-il7ra-smoke-v1']:
        for path in sorted((evidence/directory).rglob('*')):
            if path.is_file(): sources[str(path.relative_to(workspace))]=sha256(path)
    for relative in ['outputs/il7ra-context-review-2026-11-02.md',
                     'outputs/fallback-generator-assessment-2026-11-02.md',
                     'work/fallback-generator-refresh-2026-11-02.json']:
        sources[relative]=sha256(workspace/relative)
    rows=[]
    for case in cases:
        for model,metrics in case['predictors'].items():
            rows.append({'candidate_id':case['candidate_id'],'label':case['label'],'predictor':model,
                'iptm':metrics['iptm'],'ipsae_target_to_binder':metrics['ipsae_directional'][0],
                'ipsae_binder_to_target':metrics['ipsae_directional'][1],
                'generator_to_refold_binder_ca_rmsd_angstrom':metrics['target_aligned_binder_ca_rmsd_angstrom'],
                'interchain_heavy_atom_pairs_lt_2a':metrics['heavy_atom_pairs_lt_2a'],
                'relationship':metrics.get('relationship','separate_model_from_design'),
                'submission_eligible':'false'})
    out.mkdir(parents=True)
    loaded=base['write_csv'](out/'DIAGNOSTIC_scores.csv',list(rows[0]),rows)
    require(all(row['submission_eligible']=='false' for row in loaded),'Comparison eligibility guard failed')
    (out/'comparison.json').write_text(json.dumps({'status':'internal_rehearsal_only','candidates':cases,
        'generator_promotion':'deferred; one Mosaic candidate and four RFD4 candidates are not a controlled success-rate comparison',
        'submission_eligible_count':0},indent=2)+'\n')
    report='''# Generator pilot comparison — internal only

Decision: keep RFD4 as the current generation baseline and seed 43 as the provisional
rehearsal follow-up lead. Hold this Mosaic candidate and defer production promotion
of the Mosaic recipe. No candidate is submission-eligible; no binding has been measured.

| Candidate | Predictor | ipTM | ipSAE target→binder / binder→target | Generator-to-refold binder shift | Heavy-atom pairs <2 Å |
|---|---|---:|---:|---:|---:|
'''
    for row in rows:
        report+=(f"| {row['label']} | {row['predictor']} | {row['iptm']:.3f} | "
                 f"{row['ipsae_target_to_binder']:.3f} / {row['ipsae_binder_to_target']:.3f} | "
                 f"{row['generator_to_refold_binder_ca_rmsd_angstrom']:.2f} Å | "
                 f"{row['interchain_heavy_atom_pairs_lt_2a']} |\n")
    report+='''
Both predictors used the complete official 236-residue target and a template-free,
sequence-only binder input. Pose comparisons fit the same 195-residue target core
(positions 37–231). An independent Bio.PDB parser reproduced both pose calculations.
Mosaic used the full target during design; RFD4 used the 195-residue structural
reference. Different inputs, four RFD4 designs versus one Mosaic design, and unequal
compute prevent a generator-wide success-rate or accuracy comparison.

Boltz is part of Mosaic's optimization objective, so its refold is related model
evidence. ESMFold2 provides the separate-model check. The wrapper's generator ipTM
is excluded because of its zero-length-binder helper issue. All raw outputs remain.
The logged Mosaic optimization losses were finite, but the native optimizer can
sanitize gradients; only the smoke test directly established finite raw gradients.

Mosaic qualification and design each used one L40S: 4:55 smoke plus 15:55 design.
The common ESMFold2 and Boltz jobs took 1:51 and 1:19, concurrently on separately
allocated GPUs. Total allocated GPU time was 24 minutes (0.40 GPU-hour), below the
two-hour initial-pilot budget. The design measured ~10.2 GiB peak live JAX memory
and ~16.0 GiB peak pool memory. These differ from PyTorch's reserved-memory metric.
Source/checkpoint/environment hashes and successful scheduler exits are preserved.

Target glycan occupancy and assay processing remain unresolved. Sequence sequons
and distances from unmodified atoms do not establish glycan compatibility. The
public-data ranking check also found no reliable consensus improvement; retain
raw scores and disagreement rather than introducing an average-score cutoff.

BoltzGen is the first reserve and PXDesign the second, subject to their own bounded
input/memory qualification. Their current official documentation was reviewed;
neither was installed or claimed to fit the L40S. This pilot's weak candidate does
not show that Mosaic cannot work, and it does not justify an unbounded search.

`DIAGNOSTIC_scores.csv` retains all five candidates and both score directions.
`comparison.json` retains numeric summaries and target-context records.
`manifest.json` fingerprints the source evidence and package outputs. These are
diagnostic records, not the organizer's submission format.
'''
    (out/'REVIEW.md').write_text(report)
    outputs={path.name:sha256(path) for path in out.iterdir() if path.is_file()}
    (out/'manifest.json').write_text(json.dumps({'source_sha256':sources,'output_sha256':outputs,
        'submission_eligible_count':0,'official_submission_schema':False},indent=2)+'\n')
    print(json.dumps({'status':'ok','candidates':len(cases),'predictor_rows':len(rows),'verified_sources':len(sources)}))


if __name__=='__main__':
    main()
