"""Bounded native supplied-example generation; this does not score a binder."""
import io
import json
import os
from pathlib import Path
import resource
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import torch
import zstandard
from biotite.structure.io.pdbx import CIFFile, get_structure
from binder_campaign.runner import digest, write_json
from binder_campaign.structure import AA3
import rfd4_proteina as rfd4

root = Path(os.environ["TASK_ROOT"])
os.environ["DATA_PATH"] = str(root / "data/rfd4")
os.environ["WANDB_MODE"] = "disabled"
spec = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
if out.exists() and any(out.iterdir()):
    raise ValueError("Use a fresh native output directory")
request = json.loads(spec.read_text())
condition = request["binder"]
source = (spec.parent / condition["input"]).resolve()
with source.open("rb") as stream:
    raw = zstandard.ZstdDecompressor().stream_reader(stream).read().decode()
atoms = get_structure(CIFFile.read(io.StringIO(raw)), model=1, use_author_fields=True)
target_ca = atoms[(atoms.atom_name == "CA") & (atoms.chain_id == "A") &
                  (atoms.res_id >= 17) & (atoms.res_id <= 131)]
if target_ca.res_id.tolist() != list(range(17, 132)):
    raise ValueError("Supplied reference is not the declared continuous PD-L1 segment")
target_sequence = "".join(AA3[x] for x in target_ca.res_name)
model_record = json.loads((root / "env/rfd4-checkpoints.json").read_text())
assert torch.cuda.is_available()
torch.cuda.reset_peak_memory_stats()
started = time.monotonic()
rfd4.generate(overrides=[
    "inference_experiment=quickstart", f"inputs={spec}", f"out_dir={out}",
    f"hf_ckpt_path={model_record['path']}", f"hf_ckpt_revision={model_record['revision']}",
    "num_replicates=1", "batch_size=1", "num_workers=0", "seed=42", "compile_lengths=null",
    "compress_outputs=false", "skip_existing=false", "prevalidate_inputs=true",
])
torch.cuda.synchronize()
generated = sorted(out.rglob("*_generated.cif"))
if len(generated) != 1:
    raise ValueError(f"Expected one generated structure, found {len(generated)}")
design = get_structure(CIFFile.read(generated[0]), model=1, use_author_fields=False)
ca = design[design.atom_name == "CA"]
if not np.isfinite(design.coord).all():
    raise ValueError("Nonfinite generated coordinates")
chains = [{"id": str(c), "sequence": "".join(AA3[x] for x in ca[ca.chain_id == c].res_name)}
          for c in dict.fromkeys(ca.chain_id.tolist())]
targets = [c for c in chains if c["sequence"] == target_sequence]
binders = [c for c in chains if c["sequence"] != target_sequence]
if len(chains) != 2 or len(targets) != 1 or len(binders) != 1 or len(binders[0]["sequence"]) != 60:
    raise ValueError("Generated target identity or one-chain 60-residue binder validation failed")
write_json(out / "audit.json", {
    "status": "supplied_PD-L1_software_control_only; not a competition candidate or binding result",
    "model": model_record, "code_revision": "ddd934f7e6b86f7582ce487d5b19f6c526c644b5",
    "spec_sha256": digest(spec), "reference_sha256": digest(source),
    "seed": 42, "replicates": 1, "batch_size": 1, "compilation": False,
    "external_metrics": False, "generated_structure": str(generated[0]),
    "generated_sha256": digest(generated[0]), "chains": chains,
    "generation_seconds": time.monotonic() - started,
    "peak_reserved_mib": torch.cuda.max_memory_reserved() / 1024**2,
    "peak_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2,
    "host_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
})
print("One generated control structure and target/binder identities validated", flush=True)
