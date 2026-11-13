"""Report target sequons and their geometric proximity to a rehearsal interface.

This examines unmodified protein coordinates only. A sequence motif is not proof
of glycan occupancy and proximity is not a modeled glycan clash or binding result.
"""
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from Bio.PDB.MMCIF2Dict import MMCIF2Dict
from binder_campaign.runner import digest, write_json
from binder_campaign.structure import AA3


root = Path(os.environ["TASK_ROOT"])
campaign = sys.argv[1]
if campaign not in ("rfd4-il7ra-high-s43", "rfd4-il7ra-high-s44", "mosaic-il7ra",
                    *(f"rfd4-il7ra-campaign-s{seed}" for seed in range(101,113))):
    raise ValueError("This audit is bounded to the reviewed IL7Ra rehearsals")
records_path = Path(sys.argv[2]) if len(sys.argv)>2 else root / "results" / (campaign + "-v1") / "candidates.json"
review_dir = root / "results" / (campaign + "-review-v1")
output = review_dir / "target-context-audit.json"
if output.exists():
    raise ValueError("Target-context audit already exists")
record = json.loads(records_path.read_text())["candidates"][0]
review_path = review_dir / "review.json"
review = json.loads(review_path.read_text())
if review["candidate_id"] != record["candidate_id"] or review["candidate_records_sha256"] != digest(records_path):
    raise ValueError("Candidate and review records disagree")
target = json.loads((root / "src/pipeline/data/targets/il7ra/manifest.json").read_text())
reference = record["generator_audit"]["reference_audit"]
sites = [{"position": match.start() + 1, "motif": match.group(1)}
         for match in re.finditer(r"(?=(N[^P][ST]))", target["sequence"])]


def inspect_pose(path, expected_target, positions):
    data = MMCIF2Dict(str(path))
    xyz = np.asarray([data["_atom_site.Cartn_x"], data["_atom_site.Cartn_y"],
                      data["_atom_site.Cartn_z"]], dtype=float).T
    names = np.asarray(data["_atom_site.label_atom_id"])
    chains = np.asarray(data["_atom_site.label_asym_id"])
    residues = np.asarray(data["_atom_site.label_seq_id"])
    amino = np.asarray(data["_atom_site.label_comp_id"])
    elements = np.asarray(data["_atom_site.type_symbol"])
    if not np.isfinite(xyz).all():
        raise ValueError("Non-finite coordinates")
    ca = names == "CA"
    sequences = {chain: "".join(AA3[name] for name in amino[ca & (chains == chain)])
                 for chain in dict.fromkeys(chains.tolist())}
    target_chains = [chain for chain, sequence in sequences.items() if sequence == expected_target]
    binder_chains = [chain for chain, sequence in sequences.items() if sequence == record["sequence"]]
    if len(target_chains) != 1 or len(binder_chains) != 1 or len(sequences) != 2:
        raise ValueError("Ambiguous chain/sequence mapping")
    target_mask = chains == target_chains[0]
    binder_mask = chains == binder_chains[0]
    target_residues = residues[ca & target_mask]
    if len(target_residues) != len(positions) or len(set(target_residues)) != len(positions):
        raise ValueError("Target residue mapping is incomplete or ambiguous")
    mapping = dict(zip(target_residues, positions))
    reverse_mapping = {position: key for key, position in mapping.items()}
    heavy = (elements != "H") & (elements != "D")
    target_indices = np.where(target_mask & heavy)[0]
    binder_indices = np.where(binder_mask & heavy)[0]
    distances = np.linalg.norm(xyz[target_indices][:, None, :] - xyz[binder_indices][None, :, :], axis=-1)
    contacted = sorted({mapping[residues[target_indices[index]]]
                        for index in np.where(np.any(distances < 5.0, axis=1))[0]})
    sequons = []
    for site in sites:
        position = site["position"]
        entry = dict(site)
        if position not in reverse_mapping:
            entry.update({"status": "residue_absent", "min_nd2_to_binder_heavy_atom_angstrom": None})
        else:
            residue_key = reverse_mapping[position]
            indices = np.where(target_mask & (residues == residue_key) & (names == "ND2"))[0]
            if len(indices) != 1:
                entry.update({"status": "ND2_missing_or_ambiguous", "min_nd2_to_binder_heavy_atom_angstrom": None})
            else:
                nearest = float(np.linalg.norm(xyz[binder_indices] - xyz[indices[0]], axis=1).min())
                entry.update({"status": "measured_unmodified_protein_geometry",
                              "min_nd2_to_binder_heavy_atom_angstrom": nearest})
        sequons.append(entry)
    return {"structure_sha256": digest(path), "target_chain": target_chains[0],
            "binder_chain": binder_chains[0], "target_contact_positions_lt_5a": contacted,
            "target_sequon_geometry": sequons}


generator = Path(record["generator_structure"])
if digest(generator) != record["generator_structure_sha256"]:
    raise ValueError("Generator structure changed")
poses = {"generator": inspect_pose(generator, reference["reference_sequence"], reference["positions"])}
for model in ("esmfold2", "boltz"):
    path = root / "results" / (campaign + "-" + model + "-v1") / "prediction/model.cif"
    if digest(path) != review["predictions"][model]["model_cif_sha256"]:
        raise ValueError("Prediction structure changed: " + model)
    poses[model] = inspect_pose(path, target["sequence"], list(range(target["start"], target["end"] + 1)))
write_json(output, {
    "candidate_id": record["candidate_id"], "review_sha256": digest(review_path),
    "target_sequence_sha256": target["sequence_sha256"], "sequons": sites, "poses": poses,
    "scope": "N-X-S/T sequence motifs and unmodified-protein geometry only; no glycan occupancy, glycan conformation, expression or binding is established.",
    "submission_eligible": False,
})
print(json.dumps({"status": "ok", "candidate_id": record["candidate_id"], "sequons": len(sites)}))
