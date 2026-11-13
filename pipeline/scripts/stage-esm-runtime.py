"""Qualify or use byte-identical staged files; keep neural inference unchanged."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest, write_json
from binder_campaign.staging import extract_verified

parser = argparse.ArgumentParser()
parser.add_argument('mode', choices=['qualify', 'predict'])
args = parser.parse_args()
root = Path(os.environ['TASK_ROOT'])
folder = root / 'results/esm-startup-recovery-v1'
out = folder / ('cpu-qualification-v1' if args.mode == 'qualify' else 'predictions-v1')
if out.exists():
    raise ValueError('Use fresh staging results')
out.mkdir()
started = time.monotonic()
stage = Path('/data/scratch') / os.environ['SLURM_JOB_ID'] / 'cj-esm-runtime'
state = {'status': 'running', 'mode': args.mode, 'stage_root': str(stage),
         'slurm_job_id': os.environ['SLURM_JOB_ID'], 'script_sha256': digest(__file__),
         'preparation_sha256': digest(folder / 'preparation.json'), 'predictions': [],
         'submission_eligible': False}


def interrupted(signum, frame):
    raise InterruptedError('Staging/inference interrupted by signal ' + str(signum))


def run_logged(argv, log, environment, timeout):
    process = None
    before = time.monotonic()
    try:
        with log.open('w') as stream:
            process = subprocess.Popen(argv, stdout=stream, stderr=subprocess.STDOUT, env=environment)
            code = process.wait(timeout=timeout)
        return {'exit_code': code, 'elapsed_seconds': time.monotonic() - before,
                'status': 'success' if code == 0 else 'failed'}
    except BaseException:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        raise


signal.signal(signal.SIGTERM, interrupted)
signal.signal(signal.SIGINT, interrupted)
write_json(out / 'staging-state.json', state)
try:
    preparation = json.loads((folder / 'preparation.json').read_text())
    environment_path = folder / 'environment-archive.json'
    checkpoint_path = folder / 'checkpoint-archive.json'
    if digest(environment_path) != preparation['environment_descriptor_sha256'] \
            or digest(checkpoint_path) != preparation['checkpoint_descriptor_sha256']:
        raise ValueError('Archive descriptors changed')
    env_desc = json.loads(environment_path.read_text())
    weight_desc = json.loads(checkpoint_path.read_text())
    if digest(preparation['python_realpath']) != preparation['python_sha256']:
        raise ValueError('System Python differs from the prepared runtime')
    if args.mode == 'predict':
        qualification = json.loads((folder / 'cpu-qualification-v1/staging-state.json').read_text())
        if qualification['status'] != 'success' or qualification['preparation_sha256'] != state['preparation_sha256']:
            raise ValueError('Require matching successful CPU staging qualification')
    if stage.exists():
        raise ValueError('Node-local staging root already exists')
    stage.mkdir(parents=True)
    free = shutil.disk_usage(stage).free
    required = env_desc['bytes'] + weight_desc['bytes'] + 2 * 1024**3
    if free < required:
        raise ValueError('Insufficient node-local free space')
    state['initial_local_free_bytes'] = free
    common_env = {**os.environ, 'HF_HUB_DISABLE_IMPLICIT_TOKEN': '1', 'HF_HUB_OFFLINE': '1',
                  'TRANSFORMERS_OFFLINE': '1', 'PYTHONUNBUFFERED': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    if args.mode == 'qualify':
        original_checkpoint = json.loads((root / 'env/esmfold2-checkpoints.json').read_text())[0]['path']
        try:
            state['shared_probe'] = run_logged([str(root / 'env/esmfold2/bin/python'), '-u',
                str(root / 'src/pipeline/scripts/probe-esm-runtime.py'), original_checkpoint],
                out / 'shared-probe.log', {**common_env, 'ESMCFOLD_CCD_PATH': original_checkpoint + '/ccd.pkl'}, 150)
        except subprocess.TimeoutExpired:
            state['shared_probe'] = {'status': 'timeout', 'timeout_seconds': 150}
        write_json(out / 'staging-state.json', state)
    before = time.monotonic()
    local_env = stage / 'env/esmfold2'
    subprocess.run([preparation['python_realpath'], '-m', 'venv', '--without-pip', str(local_env)], check=True, timeout=30)
    (local_env / 'pyvenv.cfg').write_text(env_desc['pyvenv_cfg'])
    site = local_env / 'lib/python3.12/site-packages'
    site.rmdir()  # Empty directory just created above; archived packages replace it.
    state['environment_extraction'] = extract_verified(env_desc['path'], site, env_desc)
    model_dir = stage / 'data/weights/esmfold2'
    state['checkpoint_extraction'] = extract_verified(weight_desc['path'], model_dir, weight_desc)
    state['extraction_and_hash_seconds'] = time.monotonic() - before
    for source, expected in preparation['source_sha256'].items():
        source = Path(source)
        if digest(source) != expected:
            raise ValueError('Small pinned source changed: ' + str(source))
        target = stage / source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if digest(target) != expected:
            raise ValueError('Copied small source changed')
    original_manifest = json.loads((stage / 'env/esmfold2-checkpoints.json').read_text())
    runtime_manifest = [{**r, 'path': str(model_dir)} for r in original_manifest]
    write_json(stage / 'env/esmfold2-checkpoints.json', runtime_manifest)
    write_json(out / 'original-checkpoints.json', original_manifest)
    write_json(out / 'runtime-checkpoints.json', runtime_manifest)
    probe_source = root / 'src/pipeline/scripts/probe-esm-runtime.py'
    probe = stage / 'probe-esm-runtime.py'
    shutil.copyfile(probe_source, probe)
    local_python = local_env / 'bin/python'
    local_variables = {**common_env, 'TASK_ROOT': str(stage), 'HF_HOME': str(stage / 'hf-cache'),
                       'XDG_CACHE_HOME': str(stage / 'cache'), 'ESMCFOLD_CCD_PATH': str(model_dir / 'ccd.pkl')}
    state['staged_probe'] = run_logged([str(local_python), '-u', str(probe), str(model_dir)],
                                      out / 'staged-probe.log', local_variables, 120)
    if state['staged_probe']['exit_code'] != 0:
        raise ValueError('Staged import/CCD probe failed')
    probe_line = [line for line in (out / 'staged-probe.log').read_text().splitlines() if line.startswith('{')][-1]
    probe_result = json.loads(probe_line)
    if not Path(probe_result['prefix']).is_relative_to(stage) or probe_result['nn_parameters_loaded']:
        raise ValueError('Probe did not use the staged environment')
    state['probe_result'] = probe_result
    state['ready_seconds'] = time.monotonic() - started
    write_json(out / 'staging-state.json', state)
    if args.mode == 'predict':
        for seed in (1, 2):
            source = root / f'results/lead101-validation-v1/prediction-seed-{seed}/input.json'
            request = json.loads(source.read_text())
            if request['candidate_id'] != 'il7ra-rfd4-6b3ca40a31bb' or request['settings']['seed'] != seed:
                raise ValueError('Unexpected candidate or prediction seed')
            local_input = stage / f'input-seed-{seed}.json'
            shutil.copyfile(source, local_input)
            if digest(local_input) != digest(source):
                raise ValueError('Input copy changed')
            case = out / f'seed-{seed}'
            case.mkdir()
            local_result = stage / f'prediction-seed-{seed}'
            row = {'seed': seed, 'input_sha256': digest(source), 'status': 'running'}
            state['predictions'].append(row)
            write_json(out / 'staging-state.json', state)
            remaining = 650 - (time.monotonic() - started)
            if remaining < 100:
                row.update(status='not_run', reason='Insufficient time remaining in bounded task')
                continue
            try:
                row.update(run_logged([str(local_python), '-u', str(stage / 'src/pipeline/scripts/esmfold2-predict.py'),
                    str(local_input), str(local_result)], case / 'model.log', local_variables, min(200, remaining - 20)))
            except subprocess.TimeoutExpired:
                row.update(status='timeout', reason='Bounded per-prediction timeout')
            finally:
                if local_result.exists():
                    shutil.copytree(local_result, case / 'prediction')
                row['persisted_output_sha256'] = {str(p.relative_to(case)): digest(p)
                    for p in sorted(case.rglob('*')) if p.is_file()}
                write_json(out / 'staging-state.json', state)
        if len(state['predictions']) != 2 or any(r['status'] != 'success' for r in state['predictions']):
            raise ValueError('Both recovered predictions did not complete successfully')
    state['status'] = 'success'
except BaseException as exc:
    state.update(status='failed', error=type(exc).__name__ + ': ' + str(exc))
    raise
finally:
    state['elapsed_seconds'] = time.monotonic() - started
    write_json(out / 'staging-state.json', state)
print(json.dumps({'status': state['status'], 'ready_seconds': state.get('ready_seconds'),
                  'predictions': state['predictions']}, indent=2), flush=True)
