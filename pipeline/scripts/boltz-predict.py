"""One independent protein-complex prediction with explicit target-only MSA."""
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import torch
from Bio.PDB import MMCIFParser
from boltz.main import predict
from binder_campaign.runner import digest, write_json
from binder_campaign.structure import AA3

root = Path(os.environ["TASK_ROOT"])
request_path = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
if out.exists() and any(out.iterdir()):
    raise ValueError("Use a new directory; native output skipping is not a verified resume")
out.mkdir(parents=True, exist_ok=True)
request = json.loads(request_path.read_text())
seed = request.get("settings", {}).get("seed", 0)
if type(seed) is not int or not 0 <= seed < 2**31:
    raise ValueError("Prediction seed must be a nonnegative 31-bit integer")
target, partner = request["target"], request["partner"]
if partner.get("msa") is not None:
    raise ValueError("Partner MSA must be absent")
msa = Path(__file__).resolve().parents[1] / target["msa"]
if not msa.is_file():
    raise ValueError("Target precomputed MSA missing")
checkpoints = json.loads((root / "env/boltz-checkpoints.json").read_text())
# JSON is a supported native YAML input encoding. No templates, pocket/contact
# constraints, affinity properties or external MSA service are supplied.
native = out / "input.yaml"
write_json(native, {"version": 1, "sequences": [
    {"protein": {"id": "A", "sequence": target["sequence"], "msa": str(msa)}},
    {"protein": {"id": "B", "sequence": partner["sequence"], "msa": "empty"}},
]})
assert torch.cuda.is_available()
torch.cuda.reset_peak_memory_stats()
command = [str(native), "--out_dir", str(out), "--cache", checkpoints["cache"],
           "--model", "boltz2", "--devices", "1", "--accelerator", "gpu",
           "--seed", str(seed), "--recycling_steps", "3", "--sampling_steps", "200",
           "--diffusion_samples", "1", "--max_parallel_samples", "1",
           "--write_full_pae", "--output_format", "mmcif", "--num_workers", "0",
           "--preprocessing-threads", "1", "--max_msa_seqs", "1024", "--no_kernels"]
started = time.monotonic()
predict.main(args=command, standalone_mode=False)
torch.cuda.synchronize()
folded = time.monotonic()
predictions = out / "boltz_results_input/predictions/input"
cif = predictions / "input_model_0.cif"
pae_path = predictions / "pae_input_model_0.npz"
confidence_path = predictions / "confidence_input_model_0.json"
confidence = json.loads(confidence_path.read_text())
with np.load(pae_path) as archive:
    pae = archive["pae"]
expected = [target["sequence"], partner["sequence"]]
length = sum(map(len, expected))
if pae.shape != (length, length) or not np.isfinite(pae).all():
    raise ValueError("PAE must have one finite protein token per requested residue")
structure = MMCIFParser(QUIET=True, auth_chains=False, auth_residues=False).get_structure("prediction", cif)
models = list(structure.get_models())
if len(models) != 1:
    raise ValueError("Expected one predicted model")
chains = list(models[0].get_chains())
chain_ids = [c.id for c in chains]
observed = []
for chain in chains:
    residues = list(chain.get_residues())
    if any("CA" not in residue for residue in residues):
        raise ValueError("Every protein PAE token must have a CA coordinate")
    observed.append("".join(AA3[r.resname] for r in residues))
coordinates = np.asarray([a.coord for a in models[0].get_atoms()])
if observed != expected or not np.isfinite(coordinates).all():
    raise ValueError("Predicted chain order/sequence/coordinates do not match PAE inputs")
if not all(np.isfinite(float(confidence[key])) for key in ("iptm", "ptm")):
    raise ValueError("Nonfinite Boltz confidence")
pae_json = out / "pae.json"
write_json(pae_json, {"pae": pae.tolist()})
ipsae = root / "src/IPSAE/ipsae.py"
# Copy bytes so the scorer's derived filenames are stable and easy to audit.
model_cif = out / "model.cif"
model_cif.write_bytes(cif.read_bytes())
with (out / "ipsae.log").open("w") as log:
    subprocess.run([sys.executable, str(ipsae), str(pae_json), str(model_cif), "10", "10"],
                   stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
scores = out / "model_10_10.txt"
pairwise = []
for line in scores.read_text().splitlines():
    fields = line.split()
    if len(fields) > 5 and fields[4] in ("asym", "max"):
        value = float(fields[5])
        if not np.isfinite(value):
            raise ValueError("Nonfinite ipSAE")
        pairwise.append({"chain1": fields[0], "chain2": fields[1], "type": fields[4], "ipsae": value})
expected_pairs = {(str(chain_ids[0]), str(chain_ids[1])), (str(chain_ids[1]), str(chain_ids[0]))}
if {(r["chain1"], r["chain2"]) for r in pairwise if r["type"] == "asym"} != expected_pairs:
    raise ValueError("Missing/extra directional ipSAE pairs")
write_json(out / "metrics.json", {
    "status": "independent computational prediction; not affinity or official admission",
    "input_role": request["role"], "input_sha256": digest(request_path), "msa_sha256": digest(msa),
    "model": checkpoints, "native_argv": command, "seed": seed, "samples": 1,
    "target_only_precomputed_msa": True, "templates_or_pocket_constraints": False,
    "chains": [{"id": str(c), "length": len(s)} for c, s in zip(chain_ids, observed)],
    "iptm": confidence["iptm"], "ptm": confidence["ptm"], "raw_confidence": confidence,
    "prediction_seconds": folded - started,
    "peak_reserved_mib": torch.cuda.max_memory_reserved() / 1024**2,
    "peak_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2,
    "host_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    "ipsae": {"pae_cutoff": 10, "distance_cutoff": 10, "pairwise": pairwise,
              "script_sha256": digest(ipsae), "official_aggregation": "unconfirmed",
              "ignored_auxiliary_columns": "ipTM_af placeholder and pLDDT-based pDockQ/pDockQ2; adapter supplies PAE only"},
    "artifacts": {str(p.relative_to(out)): digest(p) for p in
                  (model_cif, pae_path, confidence_path, pae_json, scores)},
    "construct_status": request["construct_status"],
})
print("Validated independent Boltz-2 prediction and raw interface confidence", flush=True)
