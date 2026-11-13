"""One historical IL7Ra rehearsal on Modal. No candidate submission or services."""
from pathlib import Path
import json
import modal

HERE = Path(__file__).resolve().parent
app = modal.App("helixbridge-rehearsal")
cache = modal.Volume.from_name("helixbridge-model-cache", create_if_missing=True)
RFD_REV = "ddd934f7e6b86f7582ce487d5b19f6c526c644b5"
base = modal.Image.debian_slim(python_version="3.12").apt_install("git", "build-essential").pip_install("uv==0.12.9")
rfd_image = base.run_commands(
    "git clone https://github.com/RosettaCommons/RFD4-Proteina.git /opt/RFD4-Proteina",
    f"git -C /opt/RFD4-Proteina checkout {RFD_REV}",
    "uv pip install --system --no-sources --torch-backend cu132 'torch==2.14.1' 'atomworks[ml,openbabel]==3.0.4' 'biotite==1.6.0' -e /opt/RFD4-Proteina",
 ).apt_install("libxrender1", "libxext6", "libsm6", "libglib2.0-0").run_commands(
    "python -c 'from rfproteina.generate import run_generation'",
).add_local_dir(HERE / "pipeline", "/opt/pipeline", ignore=["data/", "__pycache__/", "*.pyc"]).add_local_dir(HERE / "examples", "/opt/examples")
boltz_image = base.uv_pip_install("boltz==2.2.1", "huggingface-hub", "biopython").run_commands(
    "git clone https://github.com/DunbrackLab/IPSAE.git /opt/IPSAE",
    "git -C /opt/IPSAE checkout 6174cf9e71cb1bd660cc805856a18c4871a6dec3",
).add_local_dir(HERE / "pipeline", "/opt/pipeline", ignore=["data/", "__pycache__/", "*.pyc"]).add_local_dir(HERE / "examples", "/opt/examples")


def environment(root):
    import os
    os.environ.update(TASK_ROOT=str(root), HF_HOME="/cache/hf", HF_HUB_DISABLE_IMPLICIT_TOKEN="1", WANDB_MODE="disabled")


@app.function(image=rfd_image, volumes={"/cache": cache}, timeout=1800, retries=0, max_containers=1, scaledown_window=2, cpu=2, memory=8192)
def prepare_models():
    """Download public pinned assets on CPU, once per workspace."""
    import subprocess, sys
    root = Path("/cache")
    (root / "env").mkdir(exist_ok=True)
    environment(root)
    for name in ["fetch-rfd4.py", "fetch-boltz.py"]:
        subprocess.run([sys.executable, f"/opt/pipeline/scripts/{name}"], check=True, timeout=1500)
    cache.commit()
    return {"status": "public checkpoints cached", "notes": "Separate cache for each workspace"}


def stage_root(run_id):
    import re, shutil
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", run_id):
        raise ValueError("Use a unique short alphanumeric run ID")
    root = Path("/cache/runs") / run_id
    root.mkdir(parents=True, exist_ok=True)
    pipeline = root / "src/pipeline"
    if not pipeline.exists():
        shutil.copytree("/opt/pipeline", pipeline)
        example = Path("/opt/examples/il7ra-rehearsal")
        target = pipeline / "data/targets/il7ra"
        (target / "rfd4-reference").mkdir(parents=True)
        for name in ["target.cif", "conditions.json", "audit.json"]:
            shutil.copy2(example / name, target / "rfd4-reference" / name)
        shutil.copy2(example / "historical-target.json", target / "manifest.json")
        (target / "msa").mkdir()
        shutil.copy2(example / "historical-target.a3m", target / "msa/target.a3m")
    (root / "env").mkdir(exist_ok=True)
    for name in ["rfd4-checkpoints.json", "boltz-checkpoints.json"]:
        shutil.copy2(Path("/cache/env") / name, root / "env" / name)
    environment(root)
    return root, pipeline


def archive_result(directory):
    import io, tarfile
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as tar:
        tar.add(directory, arcname=directory.name)
    return stream.getvalue()


@app.function(image=rfd_image, gpu=["L40S", "A10G", "A100"], cpu=4, memory=32768, volumes={"/cache": cache}, timeout=900, retries=0, max_containers=1, scaledown_window=2)
def generate(run_id: str, seed: int):
    import subprocess, sys, time
    root, pipeline = stage_root(run_id)
    output = root / "generation"
    started = time.monotonic()
    subprocess.run([sys.executable, str(pipeline / "scripts/rfd4-il7ra-seed.py"), str(pipeline / "data/targets/il7ra/rfd4-reference/audit.json"), str(output), str(seed)], check=True, timeout=780)
    (output / "environment.txt").write_text(subprocess.check_output(["uv", "pip", "freeze", "--system"], text=True))
    cache.commit()
    return {"audit": json.loads((output / "audit.json").read_text()), "worker_seconds": time.monotonic()-started, "gpu": __import__("torch").cuda.get_device_name(), "archive": archive_result(output)}


@app.function(image=boltz_image, gpu=["L40S", "A10G", "A100"], cpu=4, memory=32768, volumes={"/cache": cache}, timeout=900, retries=0, max_containers=1, scaledown_window=2)
def evaluate(run_id: str):
    import subprocess, sys, shutil, time
    cache.reload()
    root, pipeline = stage_root(run_id)
    audit = json.loads((root / "generation/audit.json").read_text())
    target = json.loads((pipeline / "data/targets/il7ra/manifest.json").read_text())
    shutil.copytree("/opt/IPSAE", root / "src/IPSAE", dirs_exist_ok=True)
    request = {"target": {"sequence": target["sequence"], "msa": "data/targets/il7ra/msa/target.a3m"}, "partner": {"sequence": audit["binder_sequence"], "msa": None}, "settings": {"seed": 0}, "role": "historical_rehearsal_only", "construct_status": "Historical 1-236 interval; current competition is 21-239. Not submission eligible."}
    (root / "request.json").write_text(json.dumps(request))
    output = root / "boltz"
    started = time.monotonic()
    subprocess.run([sys.executable, str(pipeline / "scripts/boltz-predict.py"), str(root / "request.json"), str(output)], check=True, timeout=780)
    (output / "environment.txt").write_text(subprocess.check_output(["uv", "pip", "freeze", "--system"], text=True))
    cache.commit()
    return {"metrics": json.loads((output / "metrics.json").read_text()), "worker_seconds": time.monotonic()-started, "gpu": __import__("torch").cuda.get_device_name(), "archive": archive_result(output)}


@app.local_entrypoint()
def main(stage: str = "prepare", run_id: str = "", seed: int = 43):
    """Explicit stages: prepare, generate, evaluate. Never launches a batch."""
    import os
    if stage not in {"prepare", "generate", "evaluate"}:
        raise ValueError("Choose prepare, generate or evaluate")
    if stage == "prepare":
        print(json.dumps(prepare_models.remote(), indent=2))
        return
    import re
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", run_id):
        raise ValueError("Supply a fresh short alphanumeric --run-id")
    if seed not in (43,44,*range(101,113)):
        raise ValueError("This historical adapter supports 43,44,101-112")
    output = HERE / "results" / run_id
    output.mkdir(parents=True, exist_ok=True)
    filename = output / (stage + ".tar.gz")
    if filename.exists():
        raise ValueError("Refusing existing local result")
    result = generate.remote(run_id,seed) if stage == "generate" else evaluate.remote(run_id)
    filename.write_bytes(result.pop("archive"))
    result["modal_profile"] = os.environ.get("MODAL_PROFILE", "active CLI profile")
    (output / (stage + ".json")).write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"saved":str(filename),"worker_seconds":result["worker_seconds"],"role":"historical rehearsal only"},indent=2))
