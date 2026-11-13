"""Fetch public canonical checkpoints at resolved immutable revisions."""
import hashlib
import json
import os
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download

root = Path(os.environ["TASK_ROOT"])
api = HfApi(token=False)
records = []
for repo in ("biohub/ESMFold2",):
    info = api.model_info(repo, token=False)
    location = Path(snapshot_download(repo_id=repo, revision=info.sha, token=False,
                    allow_patterns=["*.json","*.safetensors","*.bin","*.pt","*.pth","*.pkl","*.txt"], max_workers=4))
    files = {}
    config=json.loads((location/'config.json').read_text())
    if config.get('esmc_config') is None:
        raise ValueError('This pilot requires a checkpoint with its ESMC backbone bundled; inspect separate-backbone requirements explicitly')
    for path in sorted(location.rglob("*")):
        if not path.is_file():
            continue
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                h.update(chunk)
        files[str(path.relative_to(location))] = {"sha256":h.hexdigest(),"bytes":path.stat().st_size}
    records.append({"repo":repo,"revision":info.sha,"path":str(location),"files":files})
    print(repo, info.sha, len(files), flush=True)
    (root / "env/esmfold2-checkpoints.json").write_text(json.dumps(records,indent=2)+"\n")
