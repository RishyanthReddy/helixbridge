"""Review target-only arm inputs and freeze six generation/Boltz tasks."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest,write_json

root=Path(os.environ['TASK_ROOT']);pipeline=root/'src/pipeline'
folder=root/'results/site-diversity-pilot-v1'
proposal=folder/'inputs';plan=json.loads((proposal/'plan.json').read_text())
if (folder/'execution-plan.json').exists():raise ValueError('Execution already prepared')
control=json.loads((proposal/'control/conditions.json').read_text())
target_hash=digest(proposal/'control/target.cif')
baseline=pipeline/'data/targets/il7ra/rfd4-reference'
if target_hash!=digest(baseline/'target.cif'):raise ValueError('Reference changed')
checks=[]
for arm in plan['arms']:
    name=arm['arm'];path=proposal/name;spec=json.loads((path/'conditions.json').read_text());audit=json.loads((path/'audit.json').read_text())
    if digest(path/'target.cif')!=target_hash or len(arm['hotspots_uniprot'])!=10:raise ValueError('Unmatched target/hotspot count')
    expected=json.loads(json.dumps(control))
    expected['il7ra']['conditions']['C_HOT']['true'][0]['select']="sel('A/*/["+','.join(map(str,arm['hotspots_uniprot']))+"]')"
    if spec!=expected or spec['il7ra']['contig']!='60, /0, A37-231':raise ValueError('Unreviewed non-hotspot conditioning')
    for n,h in audit['files'].items():
        if digest(path/n)!=h:raise ValueError('Audited input changed')
    checks.append({'arm':name,'target_only':True,'new_binder_length':60,'supplied_starting_binder':False,
                   'audit_sha256':digest(path/'audit.json'),'conditions_sha256':digest(path/'conditions.json')})
    for seed in (201,202):
        case=f'{name}-s{seed}';campaign='site-'+case;result=root/f'results/{campaign}-v1'
        task={'cwd':str(pipeline),'revision':'Paired site pilot; generation then separate Boltz prediction',
            'command':[str(root/'env/rfd4/bin/python'),'scripts/run-site-pilot-design.py',name,str(seed)],
            'timeout_seconds':400,'inputs':[str(path/n) for n in ('target.cif','conditions.json','audit.json')]+
                [str(pipeline/'scripts'/n) for n in ('run-site-pilot-design.py','rfd4-site-pilot.py','prepare-candidate-evaluation.py','boltz-predict.py')],
            'outputs':[{'path':str(result/'candidates.json'),'kind':'json'},
                {'path':str(root/f'results/{campaign}-boltz-v1/prediction/metrics.json'),'kind':'metrics_json','finite_keys':['iptm','ptm']}],
            'state':str(result/'case-state.json'),'log':str(result/'case.log')}
        write_json(folder/f'tasks/{case}.json',task)
write_json(folder/'input-review.json',{'checks':checks,'only_hotspot_changes_between_arms':True,'submission_eligible':False})
write_json(folder/'execution-plan.json',{**plan,'status':'authorized_bounded_execution',
    'input_review_sha256':digest(folder/'input-review.json'),'case_stems':[f'{a["arm"]}-s{s}' for a in plan['arms'] for s in (201,202)]})
write_json(folder/'gpu-budget.json',{'gpu_seconds_cap':5400,'max_concurrent_gpus':2,'jobs':[],
    'scope':'Six paired IL7Ra site designs plus common evaluation; all failures/configuration included'})
print('Prepared six bounded tasks and independently reviewed target-only arm inputs')
