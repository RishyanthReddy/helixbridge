"""Freeze one staged ESM batch only for completed generation/Boltz cases."""
import json
import os
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest,write_json
root=Path(os.environ['TASK_ROOT']);pipeline=root/'src/pipeline';folder=root/'results/site-diversity-pilot-v1'
batch=sys.argv[1]
groups={'gate':['control-s201','patch139-s201'],
        'main':['control-s202','patch139-s202','patch72-s201','patch72-s202']}
if batch not in groups:raise ValueError('Unknown batch')
stage=folder/'staging'/batch
if stage.exists():raise ValueError('Batch already prepared')
cases=[];inputs=[]
for case in groups[batch]:
    result=root/f'results/site-{case}-v1'
    state=json.loads((result/'case-state.json').read_text())
    if state['status']!='success' or state['exit_code']!=0:raise ValueError('Case must complete generation/Boltz before ESM')
    records=result/'candidates.json';row=json.loads(records.read_text())['candidates'][0]
    request=result/'evaluation-input/input.json'
    cases.append({'case':case,'candidate_id':row['candidate_id'],'input':str(request),'input_sha256':digest(request),
                  'records_sha256':digest(records)})
    inputs.extend([str(records),str(request),str(result/'case-state.json')])
stage.mkdir(parents=True)
original=root/'results/esm-startup-recovery-v1'
for name in ('preparation.json','environment-archive.json','checkpoint-archive.json'):
    shutil.copyfile(original/name,stage/name);inputs.append(str(stage/name))
(stage/'cpu-qualification-v1').mkdir()
shutil.copyfile(original/'cpu-qualification-v1/staging-state.json',stage/'cpu-qualification-v1/staging-state.json')
inputs.append(str(stage/'cpu-qualification-v1/staging-state.json'))
write_json(stage/'batch-plan.json',{'cases':cases,'prediction_seed':0,'submission_eligible':False})
inputs.append(str(stage/'batch-plan.json'))
inputs.extend(str(pipeline/n) for n in ('scripts/site-pilot-stage-esm.py','scripts/esmfold2-predict.py',
    'scripts/probe-esm-runtime.py','binder_campaign/staging.py','slurm/run-stage.sbatch'))
outputs=[{'path':str(stage/'predictions-v1/staging-state.json'),'kind':'json'}]
for case in groups[batch]:
    prediction=stage/f'predictions-v1/seed-{case}/prediction'
    outputs.extend([{'path':str(prediction/'metrics.json'),'kind':'metrics_json','finite_keys':['iptm','ptm']}]+
        [{'path':str(prediction/n),'kind':'file'} for n in ('model.cif','pae.json','raw.npz','model_10_10.txt')])
minutes=10 if batch=='gate' else 12
task={'cwd':str(pipeline),'revision':'Unchanged pinned ESM adapter; staged immutable runtime; fresh process per case',
    'command':[str(root/'env/rfd4/bin/python'),'scripts/site-pilot-stage-esm.py','predict',batch],
    'timeout_seconds':minutes*60-20,'inputs':inputs,'outputs':outputs,
    'state':str(stage/'task-state.json'),'log':str(stage/'task.log')}
write_json(folder/f'tasks/esm-{batch}.json',task)
print(json.dumps({'task':str(folder/f'tasks/esm-{batch}.json'),'minutes':minutes,'cases':groups[batch]}))
