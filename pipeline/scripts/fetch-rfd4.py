"""Download only the public, paired native model bundle and verify release hashes."""
import hashlib
import json
import os
from pathlib import Path

from huggingface_hub import snapshot_download

REPO = "nvidia/RFD4-Proteina"
REVISION = "621b785abf9d61dd24f4b81ae4dbd1330728f030"
root = Path(os.environ["TASK_ROOT"])
location = Path(snapshot_download(
    repo_id=REPO, revision=REVISION, token=False, max_workers=2,
    allow_patterns=["config.json", "model.safetensors", "release-checkpoints.json", "provenance.json", "LICENSE"],
))
release = json.loads((location / "release-checkpoints.json").read_text())
bundle = release["bundles"]["model.safetensors"]
expected = {"model.safetensors": bundle["sha256"], "config.json": bundle["config_sha256"]}
files = {}
for path in sorted(location.iterdir()):
    if not path.is_file():
        continue
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    value = digest.hexdigest()
    if path.name in expected and value != expected[path.name]:
        raise ValueError(f"Release checksum mismatch: {path.name}")
    files[path.name] = {"sha256": value, "bytes": path.stat().st_size}
if not expected.keys() <= files.keys():
    raise ValueError("Incomplete paired native model bundle")
record = {"repo": REPO, "revision": REVISION, "path": str(location), "files": files,
          "latent_dim": release["latent_dim"], "residue_vocabulary_classes": release["residue_vocabulary_classes"],
          "access": "anonymous", "training_data_or_oracle_downloaded": False}
(root / "env/rfd4-checkpoints.json").write_text(json.dumps(record, indent=2) + "\n")
print(REPO, REVISION, len(files), "files; model/config release hashes verified", flush=True)
