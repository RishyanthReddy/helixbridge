"""Interrupt/recover a real completed-stage audit without launching model work on CPU."""
import json
import os
from pathlib import Path
import signal
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest, run_task, write_json

root=Path(os.environ['TASK_ROOT'])
pipeline=root/'src/pipeline'
stages=[pipeline/'config/rfd4-il7ra-task.json',
        root/'results/rfd4-il7ra-v1/evaluation-input/esmfold2-task.json',
        root/'results/rfd4-il7ra-v1/evaluation-input/boltz-task.json']
journal=root/'results/stage-recovery-audit-v1/journal.json'
snapshot={}
for spec_path in stages:
    spec=json.loads(spec_path.read_text())
    state=Path(spec['state'])
    if not state.is_file() or json.loads(state.read_text()).get('status')!='success':
        raise ValueError('Audit only: all model stages must already be successful; refusing inference on CPU')
    snapshot[str(state)]=digest(state)
if journal.exists():
    record=json.loads(journal.read_text())
    if record['initial_model_state_hashes']!=snapshot:
        raise ValueError('Completed model state changed since interrupted audit')
else:
    record={'status':'in_progress','initial_model_state_hashes':snapshot,'completed_audit_stages':[],
            'scope':'pipeline recovery between completed stages; not within-trajectory neural checkpoint recovery',
            'model_inference_reexecutions':0}
for spec_path in stages:
    result=run_task(spec_path)
    if result.get('resumed') is not True:
        raise ValueError('Completed stage unexpectedly executed')
    label=str(spec_path)
    if label not in record['completed_audit_stages']:
        record['completed_audit_stages'].append(label)
    write_json(journal,record)
    if '--interrupt-after-first' in sys.argv:
        record['status']='intentional_SIGTERM_after_one_completed_stage'
        write_json(journal,record)
        print('Saved partial audit journal; injecting SIGTERM after one reused real stage',flush=True)
        os.kill(os.getpid(),signal.SIGTERM)
for state,sha in snapshot.items():
    if digest(state)!=sha:
        raise ValueError('A model state was modified during resume')
record['status']='complete'
record['all_three_model_states_unchanged']=True
record['all_declared_output_hashes_revalidated']=True
write_json(journal,record)
print('Recovered interrupted real-stage audit; all three model outputs reused and states unchanged',flush=True)
