"""Prepare two sequence-only evaluations of a single recorded rehearsal candidate."""
import json
import os
from pathlib import Path
import sys
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest, write_json

root = Path(os.environ["TASK_ROOT"])
pipeline = root / "src/pipeline"
records_path = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
campaign = sys.argv[3] if len(sys.argv) > 3 else "rfd4-il7ra"
if not re.fullmatch(r"[a-z0-9-]+",campaign):
    raise ValueError("Invalid campaign directory stem")
records = json.loads(records_path.read_text())["candidates"]
if len(records) != 1:
    raise ValueError("This first rehearsal adapter requires exactly one candidate")
candidate = records[0]
if candidate['target_id'] != 'il7ra' or candidate['campaign_kind'] != 'reference_rehearsal' or candidate['qc_reasons']:
    raise ValueError("Require a format-valid recorded IL7RA reference candidate")
if digest(candidate['generator_structure']) != candidate['generator_structure_sha256']:
    raise ValueError("Generator pose changed")
manifest = pipeline / 'data/targets/il7ra/manifest.json'
target = json.loads(manifest.read_text())
control = json.loads((pipeline / 'data/controls/il7-il7ra/input.json').read_text())
if target['sequence'] != control['target']['sequence']:
    raise ValueError("Control's official interval changed")
request = {
    'role': 'de_novo_reference_rehearsal_candidate; not natural ligand or submission entry',
    'candidate_id': candidate['candidate_id'], 'preparation_script_sha256':digest(__file__), 'candidate_records_sha256': digest(records_path),
    'target_manifest_sha256': digest(manifest), 'target': control['target'],
    'partner': {'id':'B','sequence':candidate['sequence'],'msa':None},
    'settings': control['settings'], 'protocol_status': control['protocol_status'],
    'construct_status': {'full_evaluation_interval':[target['start'],target['end']],
                         'official_expression_processing':'unconfirmed',
                         'generator_reference':candidate['generator_audit']['reference_audit']},
}
if len(sys.argv) > 4:
    prediction_seed = int(sys.argv[4])
    if not 0 <= prediction_seed < 2**31:
        raise ValueError("Prediction seed must be a nonnegative 31-bit integer")
    request['settings'] = {**request['settings'], 'seed':prediction_seed}
if out.exists():
    raise ValueError("Use a fresh evaluation input directory")
out.mkdir(parents=True)
write_json(out / 'input.json', request)
for model,script in [('esmfold2','esmfold2-predict.py'),('boltz','boltz-predict.py')]:
    result = root / 'results' / f'{campaign}-{model}-v1'
    expected = ['iptm','ptm','peak_reserved_mib','host_peak_rss_mib']
    task = {
        'cwd':str(pipeline), 'revision':model+' pinned manifests; one full-target candidate refold',
        'command':[str(root/f'env/{model}/bin/python'),f'scripts/{script}',str(out/'input.json'),str(result/'prediction')],
        'timeout_seconds':3300,
        'inputs':[str(records_path),str(out/'input.json'),str(manifest),str(pipeline/f'scripts/{script}'),
                  str(pipeline/'data/targets/il7ra/msa/target.a3m'),str(root/f'env/{model}-freeze.txt'),
                  str(root/f'env/{model}-checkpoints.json'),str(root/'src/IPSAE/ipsae.py'),str(pipeline/'slurm/run-stage.sbatch')],
        'outputs':[{'path':str(result/'prediction/metrics.json'),'kind':'metrics_json','finite_keys':expected}]+
                  [{'path':str(result/'prediction'/f),'kind':'file'} for f in ['model.cif','pae.json','model_10_10.txt']],
        'state':str(result/'task-state.json'),'log':str(result/'model.log'),
    }
    raw = 'raw.npz' if model == 'esmfold2' else 'boltz_results_input/predictions/input/pae_input_model_0.npz'
    task['outputs'].append({'path':str(result/'prediction'/raw),'kind':'file'})
    write_json(out/f'{model}-task.json',task)
print('Prepared one full-target, template-free input for both predictors', flush=True)
