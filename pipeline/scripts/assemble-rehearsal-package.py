#!/usr/bin/env python3
"""Verify and assemble the existing IL-7Rα rehearsal evidence for review.

This is an internal diagnostic export. It cannot promote rehearsal candidates
to a competition submission and does not implement the organizer's CSV schema.
"""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


CASES = (
    {
        "campaign": "rfd4-il7ra",
        "label": "medium recycling",
        "decision": "hold_rehearsal_only",
        "reason": "Large predicted pose shift; acidic sequence; ESMFold2 clash flag",
    },
    {
        "campaign": "rfd4-il7ra-high",
        "label": "high recycling",
        "decision": "hold_rehearsal_only",
        "reason": "Acidic sequence; Boltz interchain clash flag; expression and binding unverified",
    },
    {
        "campaign": "rfd4-il7ra-high-s43",
        "label": "high recycling, seed 43",
        "decision": "rehearsal_followup_lead",
        "reason": "Consistent predicted poses; review unmodeled target glycan context and construct",
    },
    {
        "campaign": "rfd4-il7ra-high-s44",
        "label": "high recycling, seed 44",
        "decision": "hold_rehearsal_only",
        "reason": "Large disagreement between ESMFold2 and Boltz predicted poses",
    },
)
ALPHABET = set("ACDEFGHIKLMNPQRSTVWY")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_state_file(state, field, suffix, path):
    matches = [value for name, value in state[field].items() if name.endswith(suffix)]
    require(len(matches) == 1 and matches[0] == sha256(path),
            "Recorded task " + field + " hash mismatch: " + suffix)


def write_csv(path, fields, rows):
    with Path(path).open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with Path(path).open(newline="") as stream:
        loaded = list(csv.DictReader(stream))
    require(len(loaded) == len(rows), "CSV row count changed on round trip: " + str(path))
    return loaded


def verify_case(workspace, case, sources):
    evidence = workspace / "outputs/execution-evidence"
    campaign = case["campaign"]
    generation = evidence / (campaign + "-v1")
    review_dir = evidence / (campaign + "-review-v1")
    record_path = generation / "candidates.json"
    audit_path = generation / "prediction/audit.json"
    generated_pose = generation / "prediction/model.cif"
    state_path = generation / "task-state.json"
    review_path = review_dir / "review.json"
    input_audit_path = review_dir / "starting-input-audit.json"
    independent_path = review_dir / "independent-pose-audit.json"
    export_path = review_dir / "REHEARSAL_ONLY.csv"
    export_audit_path = review_dir / "export-audit.json"
    input_path = generation / "evaluation-input/input.json"
    target_path = workspace / "pipeline/data/targets/il7ra/manifest.json"
    for path in [record_path, audit_path, generated_pose, state_path, review_path,
                 input_audit_path, independent_path, export_path, export_audit_path,
                 input_path, target_path]:
        require(path.is_file(), "Missing evidence: " + str(path))
        sources[str(path.relative_to(workspace))] = sha256(path)

    records = read_json(record_path)["candidates"]
    require(len(records) == 1, "Expected exactly one candidate for " + campaign)
    candidate = records[0]
    review = read_json(review_path)
    audit = read_json(audit_path)
    state = read_json(state_path)
    starting = read_json(input_audit_path)
    independent = read_json(independent_path)
    export_audit = read_json(export_audit_path)
    request = read_json(input_path)
    target = read_json(target_path)
    candidate_id = candidate["candidate_id"]
    sequence = candidate["sequence"]

    require(candidate_id == review["candidate_id"] == starting["candidate_id"]
            == independent["candidate_id"] == request["candidate_id"], "Candidate ID mismatch")
    require(sequence == review["sequence"] == audit["binder_sequence"]
            == request["partner"]["sequence"], "Candidate sequence mismatch")
    require(candidate["target_id"] == "il7ra" and candidate["format"] == "minibinder", "Wrong format")
    require(40 <= len(sequence) <= 100 and not (set(sequence) - ALPHABET), "Invalid sequence")
    require(candidate["campaign_kind"] == "reference_rehearsal"
            and not candidate["submission_eligible"] and not review["submission_eligible"],
            "Rehearsal eligibility guard failed")
    require(not candidate["qc_reasons"], "Candidate importer flagged a hard QC problem")
    require(sha256(record_path) == review["candidate_records_sha256"]
            == request["candidate_records_sha256"], "Candidate record hash mismatch")
    require(sha256(generated_pose) == candidate["generator_structure_sha256"]
            == audit["generated_sha256"] == review["generation"]["generator_pose_sha256"],
            "Generator pose hash mismatch")
    require(state["status"] == "success" and state["exit_code"] == 0, "Generator task failed")
    verify_state_file(state, "outputs", "/prediction/audit.json", audit_path)
    verify_state_file(state, "outputs", "/prediction/model.cif", generated_pose)
    reference = workspace / "pipeline/data/targets/il7ra/rfd4-reference"
    for filename in ("target.cif", "conditions.json", "audit.json"):
        reference_path = reference / filename
        require(reference_path.is_file(), "Missing source reference: " + filename)
        verify_state_file(state, "inputs", "/rfd4-reference/" + filename, reference_path)
        sources[str(reference_path.relative_to(workspace))] = sha256(reference_path)
    require(starting["source_conditions_sha256"] == sha256(reference / "conditions.json")
            and starting["source_target_cif_sha256"] == sha256(reference / "target.cif"),
            "Starting-input source hash mismatch")
    require(starting["executed_model_state_sha256"] == sha256(state_path)
            and starting["initialization_review"] in (
                "passed_for_this_recipe", "same_hashes_as_previously_audited_target_only_recipe")
            and starting["supplied_starting_binder_sequence_or_coordinates"] is False,
            "Starting-input review mismatch")
    require(independent["source_review_sha256"] == sha256(review_path), "Pose audit review hash mismatch")
    require(request["target"]["sequence"] == target["sequence"]
            and request["target_manifest_sha256"] == sha256(target_path), "Evaluation target mismatch")
    require(export_audit["round_trip_checked"] and not export_audit["official_submission_schema"]
            and export_audit["csv_sha256"] == sha256(export_path), "Diagnostic export audit mismatch")
    with export_path.open(newline="") as stream:
        exported = list(csv.DictReader(stream))
    require(len(exported) == 1 and exported[0]["candidate_id"] == candidate_id
            and exported[0]["sequence"] == sequence and exported[0]["submission_eligible"] == "False",
            "Diagnostic export round trip mismatch")

    result = {"candidate_id": candidate_id, "sequence": sequence, "label": case["label"],
              "decision": case["decision"], "reason": case["reason"],
              "de_fraction": review["sequence_review"]["DE_fraction"],
              "generation_reserved_mib": audit["peak_reserved_mib"], "predictors": {}}
    for model in ("esmfold2", "boltz"):
        prediction = evidence / (campaign + "-" + model + "-v1/prediction")
        metrics_path = prediction / "metrics.json"
        prediction_state_path = prediction.parent / "task-state.json"
        prediction_state = read_json(prediction_state_path)
        metrics = read_json(metrics_path)
        summary = review["predictions"][model]
        require(prediction_state["status"] == "success" and prediction_state["exit_code"] == 0,
                model + " prediction task failed")
        verify_state_file(prediction_state, "outputs", "/prediction/metrics.json", metrics_path)
        sources[str(prediction_state_path.relative_to(workspace))] = sha256(prediction_state_path)
        # The Boltz adapter pins the full input hash but does not repeat candidate_id.
        require(metrics.get("candidate_id", candidate_id) == candidate_id
                and metrics["input_sha256"] == sha256(input_path), model + " input mismatch")
        require(sha256(metrics_path) == summary["metrics_sha256"], model + " metrics hash mismatch")
        sources[str(metrics_path.relative_to(workspace))] = sha256(metrics_path)
        for filename, expected in metrics["artifacts"].items():
            path = prediction / filename
            require(path.is_file() and sha256(path) == expected, model + " artifact mismatch: " + filename)
            sources[str(path.relative_to(workspace))] = expected
        require(sha256(prediction / "model.cif") == summary["model_cif_sha256"], model + " pose hash mismatch")
        matrix = read_json(prediction / "pae.json")["pae"]
        expected_size = len(target["sequence"]) + len(sequence)
        require(len(matrix) == expected_size and all(len(row) == expected_size for row in matrix),
                model + " PAE dimensions mismatch")
        require(all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
                    for row in matrix for value in row), model + " PAE contains a nonfinite value")
        require(math.isclose(float(metrics["iptm"]), float(summary["iptm"]), abs_tol=1e-9),
                model + " ipTM mismatch")
        direction_rows = [row for row in metrics["ipsae"]["pairwise"] if row["type"] == "asym"]
        require([(row["chain1"], row["chain2"]) for row in direction_rows] == [("A", "B"), ("B", "A")],
                model + " directional chain mapping mismatch")
        directions = [row["ipsae"] for row in direction_rows]
        require(directions == summary["ipsae_directional"] and len(directions) == 2,
                model + " directional ipSAE mismatch")
        require(math.isclose(summary["target_aligned_binder_ca_rmsd_angstrom"],
                             independent["generator_comparisons"][model]["target_aligned_binder_ca_rmsd"],
                             abs_tol=1e-4), model + " independent pose audit disagrees")
        result["predictors"][model] = {
            "iptm": summary["iptm"], "ipsae_directional": directions,
            "target_aligned_binder_ca_rmsd_angstrom": summary["target_aligned_binder_ca_rmsd_angstrom"],
            "heavy_atom_pairs_lt_2a": summary["contacts"]["heavy_atom_pairs_lt_2A"],
            "min_heavy_atom_distance_angstrom": summary["contacts"]["min_interchain_heavy_atom_distance_angstrom"],
            "peak_reserved_mib": metrics["peak_reserved_mib"],
        }
    context_path = review_dir / "target-context-audit.json"
    if campaign in ("rfd4-il7ra-high-s43", "rfd4-il7ra-high-s44"):
        context = read_json(context_path)
        require(context["candidate_id"] == candidate_id and context["review_sha256"] == sha256(review_path),
                "Target context audit mismatch")
        for model in ("esmfold2", "boltz"):
            require(context["poses"][model]["structure_sha256"] == review["predictions"][model]["model_cif_sha256"],
                    model + " target context structure mismatch")
        sources[str(context_path.relative_to(workspace))] = sha256(context_path)
        result["target_context"] = context
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    out = args.output_dir.resolve()
    require(not out.exists(), "Use a fresh package directory")
    sources = {}
    cases = [verify_case(workspace, case, sources) for case in CASES]
    require(len({case["candidate_id"] for case in cases}) == len(cases), "Duplicate candidate IDs")
    require(len({case["sequence"] for case in cases}) == len(cases), "Duplicate candidate sequences")
    recovery_path = workspace / "outputs/execution-evidence/stage-recovery-audit-v1/journal.json"
    recovery = read_json(recovery_path)
    require(recovery["status"] == "complete" and recovery["all_three_model_states_unchanged"]
            and recovery["all_declared_output_hashes_revalidated"]
            and recovery["model_inference_reexecutions"] == 0, "Stage recovery audit incomplete")
    sources[str(recovery_path.relative_to(workspace))] = sha256(recovery_path)
    benchmark = workspace / "outputs/execution-evidence/screen-benchmark-audit-v4/report.md"
    sources[str(benchmark.relative_to(workspace))] = sha256(benchmark)
    for directory in ("bc2-supplied-control-v1", "il7ra-reference-v1", "il7ra-focused-v2"):
        for filename in ("task-state.json", "bc2/summary.csv"):
            path = workspace / "outputs/execution-evidence" / directory / filename
            require(path.is_file(), "Missing preserved BC2 evidence: " + str(path))
            sources[str(path.relative_to(workspace))] = sha256(path)
    script_path = Path(__file__).resolve()
    sources[str(script_path.relative_to(workspace))] = sha256(script_path)

    out.mkdir(parents=True)
    candidate_fields = ["candidate_id", "target_id", "sequence", "status", "submission_eligible", "review_reason"]
    candidate_rows = [{"candidate_id": item["candidate_id"], "target_id": "il7ra", "sequence": item["sequence"],
                       "status": item["decision"], "submission_eligible": "false", "review_reason": item["reason"]}
                      for item in cases]
    written = write_csv(out / "REHEARSAL_ONLY_candidates.csv", candidate_fields, candidate_rows)
    require(all(row["submission_eligible"] == "false" and row["status"] in
                ("hold_rehearsal_only", "rehearsal_followup_lead")
                for row in written), "Rehearsal CSV guard failed")
    leads = [row for row in candidate_rows if row["status"] == "rehearsal_followup_lead"]
    require(len(leads) == 1, "Expected one explicitly selected rehearsal follow-up lead")
    write_csv(out / "REHEARSAL_ONLY_followup_leads.csv", candidate_fields, leads)
    write_csv(out / "EMPTY_submission_shortlist.csv", ["candidate_id", "target_id", "sequence"], [])
    screen_rows = []
    for item in cases:
        for model, metrics in item["predictors"].items():
            screen_rows.append({"candidate_id": item["candidate_id"], "predictor": model,
                                "status": "local_approximation_not_official",
                                "iptm": metrics["iptm"], "ipsae_target_to_binder": metrics["ipsae_directional"][0],
                                "ipsae_binder_to_target": metrics["ipsae_directional"][1],
                                "target_aligned_binder_ca_rmsd_angstrom": metrics["target_aligned_binder_ca_rmsd_angstrom"],
                                "heavy_atom_pairs_lt_2a": metrics["heavy_atom_pairs_lt_2a"]})
    write_csv(out / "admission_screen_approximation.csv", list(screen_rows[0]), screen_rows)

    summary = """# IL-7Rα rehearsal review — internal only

**Decision: seed 43 is a provisional rehearsal follow-up lead; three other designs are on hold.**
The submission shortlist is empty. The candidate CSVs are diagnostic drafts and are not the organizer's submission format.
No binding, affinity, expression, selectivity or official admission is established.

The RFD4 generator used a 195-residue IL-7Rα reference (positions 37–231); its origin is
unestablished and 41 residues of the declared 236-residue interval are absent. Both
ESMFold2 and Boltz predictions used the full declared target sequence. Organizer
processing and exact screen settings remain unconfirmed.

| Rehearsal | Generated vs ESM pose | Generated vs Boltz pose | D/E fraction | Review |
|---|---:|---:|---:|---|
"""
    for item in cases:
        esm, boltz = item["predictors"]["esmfold2"], item["predictors"]["boltz"]
        summary += (f"| {item['label']} | {esm['target_aligned_binder_ca_rmsd_angstrom']:.2f} Å "
                    f"| {boltz['target_aligned_binder_ca_rmsd_angstrom']:.2f} Å "
                    f"| {item['de_fraction']:.0%} | {item['reason']} |\n")
    summary += """
The seed-43 lead has no interchain heavy-atom pair below 2 Å in either refold.
Its generated-to-refold pose shift is 1.49 Å for ESMFold2 and 0.89 Å for Boltz;
the two refolds agree to 0.87 Å after fitting the reference core. These are model
consistency signals, not evidence of binding. The candidate is rehearsal-only
because the design reference and assay construct are not fully verified.

One target N-X-S/T sequon, Asn182, has its unmodified ND2 atom approximately
10.4–10.6 Å from the seed-43 binder in the two refolds. Sugar occupancy and
geometry were not modeled, so this is a context flag rather than a glycan-clash
prediction. The full target-context records retain all motif distances.

The original high-recycling design has one Boltz interchain heavy-atom pair at
1.49 Å; the original medium-recycling design has one such ESMFold2 pair at
1.77 Å. These are geometric alerts, not experimentally measured properties.

Each stage used one allocated L40S; two independent candidates' screening stages
ran concurrently after user authorization. For these 296-residue complexes,
measured peak reserved GPU memory was approximately 2,564 MiB for
RFD4, 26,316 MiB for ESMFold2 and 4,478 MiB for Boltz. GPU-job elapsed times
were roughly 1–2 minutes per stage, including startup. These are pilot measurements,
not throughput guarantees for other targets.

Three bounded BindCraft2 runs produced no accepted candidates. Their failed
trajectories and refolds remain in `../execution-evidence/`. A real interrupted
stage-level recovery reused all three completed model stages with verified hashes;
it did not test recovery inside an unfinished neural-model trajectory.

`REHEARSAL_ONLY_candidates.csv` contains all diagnostic records;
`REHEARSAL_ONLY_followup_leads.csv` identifies the one research lead;
`EMPTY_submission_shortlist.csv` intentionally contains no candidates;
`admission_screen_approximation.csv` preserves both directional local scores.
`manifest.json` records source and output hashes. For the experimental benchmark,
see `../execution-evidence/screen-benchmark-audit-v4/report.md`.
"""
    (out / "REVIEW.md").write_text(summary)
    output_files = {path.name: sha256(path) for path in sorted(out.iterdir()) if path.is_file()}
    manifest = {"status": "internal_rehearsal_only", "official_submission_schema": False,
                "rehearsal_followup_lead_count": len(leads), "submission_shortlist_count": 0,
                "submission_eligible_count": 0,
                "workspace": str(workspace), "source_sha256": sources, "output_sha256": output_files}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"status": "ok", "output": str(out), "candidates_on_hold": len(cases) - len(leads),
                      "rehearsal_followup_leads": len(leads), "submission_shortlist_count": 0,
                      "verified_source_files": len(sources)}))


if __name__ == "__main__":
    main()
