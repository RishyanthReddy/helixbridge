"""Import one bounded seed rehearsal and link it to the audited starting recipe."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.candidates import import_rfd4
from binder_campaign.runner import digest, write_json


def recorded_hash(state, field, suffix):
    values = [value for path, value in state[field].items() if path.endswith(suffix)]
    if len(values) != 1:
        raise ValueError("Expected exactly one recorded " + suffix)
    return values[0]


root = Path(os.environ["TASK_ROOT"])
pipeline = root / "src/pipeline"
seed = int(sys.argv[1])
if seed not in (43, 44):
    raise ValueError("Seed must be one of the two predeclared diagnostics")
campaign = f"rfd4-il7ra-high-s{seed}"
result = root / "results" / (campaign + "-v1")
state = json.loads((result / "task-state.json").read_text())
audit_path = result / "prediction/audit.json"
audit = json.loads(audit_path.read_text())
anchor_path = root / "results/rfd4-il7ra-high-review-v1/starting-input-audit.json"
anchor = json.loads(anchor_path.read_text())
anchor_state = root / "results/rfd4-il7ra-high-v1/task-state.json"
if anchor["executed_model_state_sha256"] != digest(anchor_state):
    raise ValueError("Original audited starting recipe state changed")
if (anchor["initialization_review"] != "passed_for_this_recipe"
        or anchor["supplied_starting_binder_sequence_or_coordinates"] is not False):
    raise ValueError("Original starting recipe was not cleared")
if state["status"] != "success" or state["exit_code"] != 0:
    raise ValueError("Generation task did not finish successfully")
if audit["seed"] != seed or audit["recycle_strategy"] != "thinking_high":
    raise ValueError("Generation setting mismatch")
reference = pipeline / "data/targets/il7ra/rfd4-reference"
for name, anchor_key in (("target.cif", "source_target_cif_sha256"),
                         ("conditions.json", "source_conditions_sha256")):
    actual = digest(reference / name)
    if actual != anchor[anchor_key] or actual != recorded_hash(state, "inputs", "/rfd4-reference/" + name):
        raise ValueError("Executed starting recipe differs from the audited recipe: " + name)
for name in ("audit.json", "model.cif"):
    actual = digest(result / "prediction" / name)
    if actual != recorded_hash(state, "outputs", "/prediction/" + name):
        raise ValueError("Generated output changed: " + name)

sequence = audit["binder_sequence"]
previous = ["rfd4-il7ra", "rfd4-il7ra-high", "rfd4-il7ra-high-s43", "rfd4-il7ra-high-s44"]
for other in previous:
    if other == campaign:
        continue
    path = root / "results" / (other + "-v1") / "candidates.json"
    if path.is_file() and any(row["sequence"] == sequence for row in json.loads(path.read_text())["candidates"]):
        raise ValueError("Exact duplicate of an earlier rehearsal candidate: " + other)
records_path = result / "candidates.json"
input_audit_path = result / "starting-input-audit.json"
if records_path.exists() or input_audit_path.exists():
    raise ValueError("Candidate preparation outputs already exist; inspect before reusing")
records = import_rfd4(audit_path, pipeline / "data/targets/il7ra/manifest.json", records_path)
if len(records) != 1 or records[0]["qc_reasons"]:
    raise ValueError("Imported candidate failed alphabet, length, format, or provenance checks")
write_json(input_audit_path, {
    "candidate_id": records[0]["candidate_id"],
    "initialization_review": "same_hashes_as_previously_audited_target_only_recipe",
    "supplied_starting_binder_sequence_or_coordinates": False,
    "source_conditions_sha256": anchor["source_conditions_sha256"],
    "source_target_cif_sha256": anchor["source_target_cif_sha256"],
    "anchor_audit_sha256": digest(anchor_path),
    "executed_model_state_sha256": digest(result / "task-state.json"),
    "candidate_records_sha256": digest(records_path),
    "scope": "Checks this recipe and exact duplicates against existing rehearsal records; not comprehensive novelty or cross-team duplicate clearance.",
    "submission_eligible": False,
})
print(json.dumps({"status": "ok", "candidate_id": records[0]["candidate_id"], "seed": seed}))
