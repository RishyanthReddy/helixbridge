"""One audited IL7RA reference generation; independent scoring is a later stage."""
import json
import os
from pathlib import Path
import resource
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import torch
from biotite.structure.io.pdbx import CIFFile, get_structure
from binder_campaign.runner import digest, write_json
from binder_campaign.structure import AA3
import rfd4_proteina as rfd4

root = Path(os.environ["TASK_ROOT"])
os.environ["DATA_PATH"] = str(root / "data/rfd4")
os.environ["WANDB_MODE"] = "disabled"
reference_audit = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
if out.exists() and any(out.iterdir()):
    raise ValueError("Use a fresh native output directory")
reference = json.loads(reference_audit.read_text())
if reference["target_id"] != "il7ra" or reference["role"] != "reference_rehearsal_only":
    raise ValueError("This bounded adapter requires the reviewed IL7RA rehearsal input")
for name, sha in reference["files"].items():
    if digest(reference_audit.parent / name) != sha:
        raise ValueError("Reference input changed after preparation")
spec = reference_audit.parent / "conditions.json"
source = reference_audit.parent / "target.cif"
atoms = get_structure(CIFFile.read(source), model=1, use_author_fields=False)
target_ca = atoms[atoms.atom_name == "CA"]
target_sequence = "".join(AA3[x] for x in target_ca.res_name)
canonical = json.loads((root / "src/pipeline/data/targets/il7ra/manifest.json").read_text())
if (target_ca.res_id.tolist() != reference["positions"] or target_sequence != reference["reference_sequence"]
        or target_sequence != "".join(canonical["sequence"][i-canonical["start"]] for i in reference["positions"])):
    raise ValueError("Reference mapping/identity differs from audited canonical target")
model_record = json.loads((root / "env/rfd4-checkpoints.json").read_text())
assert torch.cuda.is_available()
torch.cuda.reset_peak_memory_stats()
started = time.monotonic()
rfd4.generate(overrides=[
    "inference_experiment=quickstart", f"inputs={spec}", f"out_dir={out}",
    f"hf_ckpt_path={model_record['path']}", f"hf_ckpt_revision={model_record['revision']}",
    "num_replicates=1", "batch_size=1", "num_workers=0", "seed=42", "compile_lengths=null", "recycle_strategy=thinking_high",
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
if len(chains) != 2 or len(targets) != 1 or len(binders) != 1 or len(binders[0]["sequence"]) != reference["binder_length"]:
    raise ValueError("Generated target identity or one-chain 60-residue binder validation failed")
(out / "model.cif").write_bytes(generated[0].read_bytes())
write_json(out / "audit.json", {
    "status": "IL7RA_reference_rehearsal; not a submission-eligible candidate or binding result",
    "reference_audit": reference, "reference_audit_sha256": digest(reference_audit),
    "canonical_target_manifest_sha256": digest(root / "src/pipeline/data/targets/il7ra/manifest.json"),
    "target_chain": targets[0]["id"], "binder_chain": binders[0]["id"],
    "binder_sequence": binders[0]["sequence"],
    "model": model_record, "code_revision": "ddd934f7e6b86f7582ce487d5b19f6c526c644b5",
    "spec_sha256": digest(spec), "reference_sha256": digest(source),
    "seed": 42, "replicates": 1, "batch_size": 1, "compilation": False,
    "external_metrics": False, "recycle_strategy": "thinking_high", "comparison": "Same input, seed, length and evaluators as v1; only recycling strategy raised from medium to high", "generated_structure": str(out / "model.cif"),
    "generated_sha256": digest(out / "model.cif"), "chains": chains,
    "raw_structure_hashes": {str(p.relative_to(out)): digest(p) for p in out.rglob("*.cif")},
    "generation_seconds": time.monotonic() - started,
    "peak_reserved_mib": torch.cuda.max_memory_reserved() / 1024**2,
    "peak_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2,
    "host_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
})
print("One generated control structure and target/binder identities validated", flush=True)
