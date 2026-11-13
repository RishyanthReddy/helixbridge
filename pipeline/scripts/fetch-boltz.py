"""Pin and hash the public Boltz-2 artifacts consumed by its native CLI."""
import hashlib
import json
import os
from pathlib import Path
import tarfile
from huggingface_hub import snapshot_download

root = Path(os.environ["TASK_ROOT"])
revision = "6fdef46d763fee7fbb83ca5501ccceff43b85607"
names = ["boltz2_conf.ckpt", "boltz2_aff.ckpt", "mols.tar"]
location = Path(snapshot_download(repo_id="boltz-community/boltz-2", revision=revision,
                                 allow_patterns=names, token=False, max_workers=2))
cache = root / "data/weights/boltz2"
cache.mkdir(parents=True, exist_ok=True)
files = {}
for name in names:
    source = location / name
    h = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    target = cache / name
    if target.exists() and target.resolve() != source.resolve():
        raise ValueError(f"Refusing to replace a different cache artifact: {name}")
    if not target.exists():
        target.symlink_to(source)
    files[name] = {"sha256": h.hexdigest(), "bytes": source.stat().st_size}
if not (cache / "mols").exists():
    with tarfile.open(cache / "mols.tar") as archive:
        archive.extractall(cache, filter="data")
if not (cache / "mols").is_dir():
    raise ValueError("Native CCD molecule directory was not extracted")
(root / "env/boltz-checkpoints.json").write_text(json.dumps({
    "repo": "boltz-community/boltz-2", "revision": revision, "cache": str(cache),
    "files": files, "access": "anonymous",
    "affinity_note": "Native CLI requires the affinity checkpoint to be cached; no protein affinity prediction is requested or interpreted.",
}, indent=2) + "\n")
print("Pinned Boltz-2 artifacts downloaded, hashed, and prepared", flush=True)
