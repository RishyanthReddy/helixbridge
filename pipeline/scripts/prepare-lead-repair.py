#!/usr/bin/env python3
"""Prepare and independently audit input to constrained SolubleMPNN repair.

Research-only preparation for RFD4 IL7Ra seed101 design.
CLI arguments:
  --workspace PATH   Directory containing pipeline/, outputs/, work/
  --output-dir PATH  Fresh output directory to receive prepared inputs and audit

Refuses pre-existing output directory.
No model inference executed; no candidate submission; no energy/affinity claims.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

import numpy as np
from Bio.PDB.MMCIF2Dict import MMCIF2Dict
from Bio.PDB import PDBParser

# Add repository root to path for binder_campaign imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binder_campaign.runner import digest, write_json
from binder_campaign.structure import AA3


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare and independently audit input to constrained SolubleMPNN repair of RFD4 IL7Ra seed101."
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        required=True,
        help="Workspace directory containing pipeline/, outputs/, work/",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Path to fresh output directory (must not pre-exist)",
    )
    return parser.parse_args()


def format_pdb_atom_line(
    serial: int,
    atom_name: str,
    res_name: str,
    chain_id: str,
    res_seq: int,
    x: float,
    y: float,
    z: float,
    occupancy: float = 1.00,
    temp_factor: float = 0.00,
    element: str = "",
) -> str:
    """Format a standard PDB ATOM record (80 characters)."""
    if len(atom_name) < 4:
        atom_field = f" {atom_name:<3}"
    else:
        atom_field = f"{atom_name:<4}"
    elem = element.strip().rjust(2)
    return (
        f"ATOM  {serial:5d} {atom_field} {res_name:3s} {chain_id}{res_seq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{occupancy:6.2f}{temp_factor:6.2f}          {elem}"
    )


def format_pdb_ter_line(serial: int, res_name: str, chain_id: str, res_seq: int) -> str:
    """Format a standard PDB TER record."""
    return f"TER   {serial:5d}      {res_name:3s} {chain_id}{res_seq:4d}"


def main() -> None:
    args = parse_arguments()

    # Workspace validation
    workspace = args.workspace.resolve()
    pipeline_dir = workspace / "pipeline"
    outputs_dir = workspace / "outputs"
    work_dir = workspace / "work"

    if not pipeline_dir.is_dir():
        raise ValueError(f"Workspace missing pipeline directory: {pipeline_dir}")
    if not outputs_dir.is_dir():
        raise ValueError(f"Workspace missing outputs directory: {outputs_dir}")
    if not work_dir.is_dir():
        raise ValueError(f"Workspace missing work directory: {work_dir}")

    # Output directory validation: refuse pre-existing output
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise ValueError(f"Refusing pre-existing output directory: {output_dir}")

    # Identify exact evidence paths
    candidates_rel = "outputs/execution-evidence/rfd4-il7ra-campaign-s101-v1/candidates.json"
    candidates_path = workspace / candidates_rel
    if not candidates_path.is_file():
        raise FileNotFoundError(f"Missing candidates file: {candidates_path}")

    cif_rel = "outputs/execution-evidence/rfd4-il7ra-campaign-s101-v1/prediction/model.cif"
    cif_path = workspace / cif_rel
    if not cif_path.is_file():
        raise FileNotFoundError(f"Missing model CIF file: {cif_path}")

    manifest_rel = "pipeline/data/targets/il7ra/manifest.json"
    manifest_path = workspace / manifest_rel
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing target manifest file: {manifest_path}")

    starting_audit_rel = "outputs/execution-evidence/rfd4-il7ra-campaign-s101-v1/starting-input-audit.json"
    starting_audit_path = workspace / starting_audit_rel
    conditions_rel = "pipeline/data/targets/il7ra/rfd4-reference/conditions.json"
    reference_cif_rel = "pipeline/data/targets/il7ra/rfd4-reference/target.cif"
    for relative in (starting_audit_rel, conditions_rel, reference_cif_rel):
        if not (workspace / relative).is_file():
            raise FileNotFoundError(f"Missing starting-input evidence: {workspace / relative}")

    # Calculate input source digests
    candidates_sha256 = digest(candidates_path)
    cif_sha256 = digest(cif_path)
    manifest_sha256 = digest(manifest_path)

    source_hashes = {
        candidates_rel: candidates_sha256,
        cif_rel: cif_sha256,
        manifest_rel: manifest_sha256,
        starting_audit_rel: digest(starting_audit_path),
        conditions_rel: digest(workspace / conditions_rel),
        reference_cif_rel: digest(workspace / reference_cif_rel),
    }

    # 1. Parse and verify candidates.json
    candidates_data = json.loads(candidates_path.read_text())
    candidates_list = candidates_data.get("candidates", [])
    if len(candidates_list) != 1:
        raise ValueError(f"Expected exactly 1 candidate, found {len(candidates_list)}")
    cand = candidates_list[0]

    # Verify candidate identity
    expected_candidate_id = "il7ra-rfd4-6b3ca40a31bb"
    if cand.get("candidate_id") != expected_candidate_id:
        raise ValueError(f"Candidate ID mismatch: expected '{expected_candidate_id}', got '{cand.get('candidate_id')}'")

    # Verify generator_structure_sha256 against local CIF
    if cand.get("generator_structure_sha256") != cif_sha256:
        raise ValueError(
            f"generator_structure_sha256 mismatch against local CIF: "
            f"{cand.get('generator_structure_sha256')} vs {cif_sha256}"
        )
    generator_audit = cand.get("generator_audit", {})
    if generator_audit.get("generated_sha256") != cif_sha256:
        raise ValueError("generator_audit.generated_sha256 mismatch against local CIF")

    # Confirm generator and that no known external binder was used as starting sequence
    if cand.get("generator") != "RFD4-Proteina":
        raise ValueError(f"Expected generator 'RFD4-Proteina', got '{cand.get('generator')}'")
    if cand.get("campaign_kind") != "reference_rehearsal":
        raise ValueError(f"Expected campaign_kind 'reference_rehearsal', got '{cand.get('campaign_kind')}'")
    starting_audit = json.loads(starting_audit_path.read_text())
    if starting_audit.get("candidate_id") != expected_candidate_id:
        raise ValueError("Starting-input audit candidate identity mismatch")
    if starting_audit.get("supplied_starting_binder_sequence_or_coordinates") is not False:
        raise ValueError("Starting-input audit does not establish an unsupplied starting binder")
    for field, actual in (
        ("candidate_records_sha256", candidates_sha256),
        ("source_conditions_sha256", source_hashes[conditions_rel]),
        ("source_target_cif_sha256", source_hashes[reference_cif_rel]),
    ):
        if starting_audit.get(field) != actual:
            raise ValueError(f"Starting-input audit hash mismatch: {field}")

    # Check reference audit inside generator_audit
    reference_audit = generator_audit.get("reference_audit", {})
    ref_positions = reference_audit.get("positions", [])
    expected_ref_positions = list(range(37, 232))
    if ref_positions != expected_ref_positions:
        raise ValueError(
            f"Reference positions mismatch: expected 195 positions 37..231, got {len(ref_positions)} positions"
        )
    ref_sequence = reference_audit.get("reference_sequence")
    if not ref_sequence or len(ref_sequence) != 195:
        raise ValueError(f"Reference sequence missing or length != 195 (len={len(ref_sequence) if ref_sequence else 0})")

    # Binder sequence against record
    binder_seq_record = cand.get("sequence")
    if not binder_seq_record or len(binder_seq_record) != 60:
        raise ValueError(f"Binder sequence missing or length != 60 (len={len(binder_seq_record) if binder_seq_record else 0})")
    if generator_audit.get("binder_sequence") != binder_seq_record:
        raise ValueError("generator_audit.binder_sequence does not match candidate sequence")

    # 2. Check target sequence against official manifest slice
    manifest_data = json.loads(manifest_path.read_text())
    man_start = manifest_data["start"]  # 1
    man_end = manifest_data["end"]      # 236
    man_seq = manifest_data["sequence"]
    slice_start = 37 - man_start
    slice_end = 231 - man_start + 1
    manifest_slice = man_seq[slice_start:slice_end]
    if manifest_slice != ref_sequence:
        raise ValueError("Official manifest slice (37..231) does not match reference audit sequence")

    # 3. Parse and independently audit model.cif via Bio.PDB.MMCIF2Dict
    cif_dict = MMCIF2Dict(str(cif_path))

    asym_ids = np.asarray(cif_dict["_atom_site.label_asym_id"])
    label_seq_ids = np.asarray([int(s) for s in cif_dict["_atom_site.label_seq_id"]])
    comp_ids = np.asarray(cif_dict["_atom_site.label_comp_id"])
    atom_ids = np.asarray(cif_dict["_atom_site.label_atom_id"])
    type_symbols = np.asarray(cif_dict["_atom_site.type_symbol"])
    xs = np.asarray(cif_dict["_atom_site.Cartn_x"], dtype=float)
    ys = np.asarray(cif_dict["_atom_site.Cartn_y"], dtype=float)
    zs = np.asarray(cif_dict["_atom_site.Cartn_z"], dtype=float)
    total_atoms = len(asym_ids)

    # Verify finite coordinates
    if not (np.isfinite(xs).all() and np.isfinite(ys).all() and np.isfinite(zs).all()):
        raise ValueError("Non-finite coordinates detected in model.cif")

    # Verify chains
    unique_chains = sorted(list(set(asym_ids.tolist())))
    if unique_chains != ["A", "B"]:
        raise ValueError(f"Unexpected chains in CIF: {unique_chains}; expected ['A', 'B']")

    # Check unique (chain, residue, atom) keys
    seen_keys = set()
    for ch, r_num, a_name in zip(asym_ids, label_seq_ids, atom_ids):
        key = (ch, int(r_num), str(a_name))
        if key in seen_keys:
            raise ValueError(f"Duplicate (chain, residue, atom) key in CIF: {key}")
        seen_keys.add(key)

    # Verify all residues belong to standard 20 amino acids
    for resn in set(comp_ids.tolist()):
        if resn not in AA3:
            raise ValueError(f"Non-standard amino acid detected: {resn}")

    # Inspect Chain A (Target): native CIF label numbers 1..195
    ca_mask = atom_ids == "CA"
    target_mask = asym_ids == "A"
    binder_mask = asym_ids == "B"

    target_ca_seq_ids = label_seq_ids[ca_mask & target_mask]
    if len(target_ca_seq_ids) != 195:
        raise ValueError(f"Expected exactly 195 CA atoms in Chain A, found {len(target_ca_seq_ids)}")
    if target_ca_seq_ids.tolist() != list(range(1, 196)):
        raise ValueError("Native CIF label numbers for target Chain A are not contiguous 1..195")

    target_cif_seq = "".join(AA3[c] for c in comp_ids[ca_mask & target_mask])
    if target_cif_seq != ref_sequence:
        raise ValueError("Chain A sequence from CIF does not match reference sequence")
    if target_cif_seq != manifest_slice:
        raise ValueError("Chain A sequence from CIF does not match official manifest slice")

    # Inspect Chain B (Binder): native CIF label numbers 1..60
    binder_ca_seq_ids = label_seq_ids[ca_mask & binder_mask]
    if len(binder_ca_seq_ids) != 60:
        raise ValueError(f"Expected exactly 60 CA atoms in Chain B, found {len(binder_ca_seq_ids)}")
    if binder_ca_seq_ids.tolist() != list(range(1, 61)):
        raise ValueError("Native CIF label numbers for binder Chain B are not contiguous 1..60")

    binder_cif_seq = "".join(AA3[c] for c in comp_ids[ca_mask & binder_mask])
    if binder_cif_seq != binder_seq_record:
        raise ValueError("Chain B sequence from CIF does not match candidate record sequence")

    # Check completeness of backbone atoms (N, CA, C, O) for every residue
    required_backbone = {"N", "CA", "C", "O"}
    for ch, expected_count in [("A", 195), ("B", 60)]:
        ch_mask = asym_ids == ch
        for r_num in range(1, expected_count + 1):
            r_atoms = set(atom_ids[ch_mask & (label_seq_ids == r_num)])
            missing_bb = required_backbone - r_atoms
            if missing_bb:
                raise ValueError(f"Missing backbone atoms in chain {ch} residue {r_num}: {missing_bb}")

    # Require parent B18=N, B25=C, B29=N (1-indexed)
    parent_b18 = binder_cif_seq[18 - 1]
    parent_b25 = binder_cif_seq[25 - 1]
    parent_b29 = binder_cif_seq[29 - 1]
    if parent_b18 != "N":
        raise ValueError(f"Requirement failed: parent B18 must be 'N', found '{parent_b18}'")
    if parent_b25 != "C":
        raise ValueError(f"Requirement failed: parent B25 must be 'C', found '{parent_b25}'")
    if parent_b29 != "N":
        raise ValueError(f"Requirement failed: parent B29 must be 'N', found '{parent_b29}'")

    # 4. Construct all-heavy-atom PDB (Chain A: UniProt 37..231, Chain B: 1..60)
    # Native CIF label numbers for target are 1..195; mapped to UniProt positions 37..231
    # Native CIF label numbers for binder are 1..60; mapped to Chain B 1..60
    # No atoms or sidechains fabricated; original coordinates, resnames, elements preserved.
    pdb_lines: List[str] = [
        "REMARK 250 RESEARCH-ONLY PREPARATION FOR CONSTRAINED SOLUBLEMPNN REPAIR",
        f"REMARK 250 CANDIDATE ID: {expected_candidate_id}",
        "REMARK 250 CHAIN A: IL7RA REFERENCE TARGET (UNIPROT P16871 RESIDUES 37-231)",
        "REMARK 250 CHAIN B: DE NOVO DESIGNED MINIBINDER (RESIDUES 1-60)",
        "REMARK 250 NO INFERENCE EXECUTED; NOT A CANDIDATE SUBMISSION",
    ]

    original_atom_records: List[Dict[str, Any]] = []
    serial = 1

    # Chain A atoms
    target_atom_indices = np.where(asym_ids == "A")[0]
    last_res_a = ""
    last_unp_a = 231
    for idx in target_atom_indices:
        label_id = int(label_seq_ids[idx])
        unp_pos = label_id + 36  # label 1 -> 37, label 195 -> 231
        a_name = str(atom_ids[idx])
        resn = str(comp_ids[idx])
        elem = str(type_symbols[idx])
        x, y, z = float(xs[idx]), float(ys[idx]), float(zs[idx])

        line = format_pdb_atom_line(serial, a_name, resn, "A", unp_pos, x, y, z, 1.00, 0.00, elem)
        pdb_lines.append(line)
        original_atom_records.append({
            "serial": serial,
            "chain": "A",
            "cif_label_seq_id": label_id,
            "res_seq": unp_pos,
            "res_name": resn,
            "atom_name": a_name,
            "element": elem,
            "coord": np.array([x, y, z]),
        })
        last_res_a = resn
        last_unp_a = unp_pos
        serial += 1

    # Chain A TER
    pdb_lines.append(format_pdb_ter_line(serial, last_res_a, "A", last_unp_a))
    serial += 1

    # Chain B atoms
    binder_atom_indices = np.where(asym_ids == "B")[0]
    last_res_b = ""
    last_b_num = 60
    for idx in binder_atom_indices:
        label_id = int(label_seq_ids[idx])
        b_pos = label_id  # 1..60
        a_name = str(atom_ids[idx])
        resn = str(comp_ids[idx])
        elem = str(type_symbols[idx])
        x, y, z = float(xs[idx]), float(ys[idx]), float(zs[idx])

        line = format_pdb_atom_line(serial, a_name, resn, "B", b_pos, x, y, z, 1.00, 0.00, elem)
        pdb_lines.append(line)
        original_atom_records.append({
            "serial": serial,
            "chain": "B",
            "cif_label_seq_id": label_id,
            "res_seq": b_pos,
            "res_name": resn,
            "atom_name": a_name,
            "element": elem,
            "coord": np.array([x, y, z]),
        })
        last_res_b = resn
        last_b_num = b_pos
        serial += 1

    # Chain B TER and END
    pdb_lines.append(format_pdb_ter_line(serial, last_res_b, "B", last_b_num))
    pdb_lines.append("END")
    pdb_content = "\n".join(pdb_lines) + "\n"

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=False)

    # Write seed101-complex.pdb
    pdb_output_path = output_dir / "seed101-complex.pdb"
    pdb_output_path.write_text(pdb_content)

    # 5. Independent round-trip verification using Bio.PDB.PDBParser
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("seed101_complex", str(pdb_output_path))
    parsed_atoms = list(structure.get_atoms())

    if len(parsed_atoms) != len(original_atom_records):
        raise ValueError(
            f"PDB atom count mismatch: parsed {len(parsed_atoms)} atoms vs original {len(original_atom_records)}"
        )

    max_round_trip_error = 0.0
    for orig, parsed in zip(original_atom_records, parsed_atoms):
        p_chain = parsed.get_parent().get_parent().id
        p_res_seq = parsed.get_parent().id[1]
        p_res_name = parsed.get_parent().resname
        p_atom_name = parsed.get_name()
        p_element = parsed.element
        p_coord = parsed.get_coord()

        if p_chain != orig["chain"]:
            raise ValueError(f"Chain mismatch: parsed '{p_chain}' vs original '{orig['chain']}'")
        if p_res_seq != orig["res_seq"]:
            raise ValueError(f"Residue number mismatch: parsed {p_res_seq} vs original {orig['res_seq']}")
        if p_res_name != orig["res_name"]:
            raise ValueError(f"Residue name mismatch: parsed '{p_res_name}' vs original '{orig['res_name']}'")
        if p_atom_name != orig["atom_name"]:
            raise ValueError(f"Atom name mismatch: parsed '{p_atom_name}' vs original '{orig['atom_name']}'")
        if p_element != orig["element"]:
            raise ValueError(f"Element mismatch: parsed '{p_element}' vs original '{orig['element']}'")

        err = float(np.max(np.abs(p_coord - orig["coord"])))
        if err > max_round_trip_error:
            max_round_trip_error = err
        if err > 0.001:
            raise ValueError(
                f"Coordinate round-trip error exceeded 0.001 A threshold: "
                f"{err:.6f} A on atom {p_atom_name} of residue {p_chain}{p_res_seq}"
            )

    # 6. Geometric distance audit from binder residues B18, B25, B29 to target heavy atoms
    # Heavy atoms: element != 'H' and element != 'D'
    target_heavy_idx = np.where((asym_ids == "A") & (type_symbols != "H") & (type_symbols != "D"))[0]
    target_heavy_xyz = np.asarray([xs[target_heavy_idx], ys[target_heavy_idx], zs[target_heavy_idx]]).T
    target_heavy_atom_names = atom_ids[target_heavy_idx]
    target_heavy_cif_seq_ids = label_seq_ids[target_heavy_idx]
    target_heavy_resnames = comp_ids[target_heavy_idx]
    target_heavy_uniprot_pos = target_heavy_cif_seq_ids + 36

    nearest_target_distances: Dict[str, Any] = {}
    for r in [18, 25, 29]:
        b_res_heavy_idx = np.where(
            (asym_ids == "B") & (label_seq_ids == r) & (type_symbols != "H") & (type_symbols != "D")
        )[0]
        if len(b_res_heavy_idx) == 0:
            raise ValueError(f"No heavy atoms found for binder residue B{r}")

        b_xyz = np.asarray([xs[b_res_heavy_idx], ys[b_res_heavy_idx], zs[b_res_heavy_idx]]).T
        b_atom_names = atom_ids[b_res_heavy_idx]
        b_resname = str(comp_ids[b_res_heavy_idx][0])

        # Pairwise distance matrix between residue r heavy atoms and target heavy atoms
        dists = np.linalg.norm(b_xyz[:, None, :] - target_heavy_xyz[None, :, :], axis=-1)
        min_dist = float(dists.min())
        min_b_idx, min_t_idx = np.unravel_index(dists.argmin(), dists.shape)

        closest_b_atom = str(b_atom_names[min_b_idx])
        closest_t_atom = str(target_heavy_atom_names[min_t_idx])
        closest_t_unp = int(target_heavy_uniprot_pos[min_t_idx])
        closest_t_cif_label = int(target_heavy_cif_seq_ids[min_t_idx])
        closest_t_resname = str(target_heavy_resnames[min_t_idx])

        # CA distance
        ca_idx_local = np.where(b_atom_names == "CA")[0]
        if len(ca_idx_local) != 1:
            raise ValueError(f"Could not identify unique CA atom for binder residue B{r}")
        ca_dists = np.linalg.norm(b_xyz[ca_idx_local[0]] - target_heavy_xyz, axis=-1)
        min_ca_dist = float(ca_dists.min())
        closest_ca_t_idx = int(ca_dists.argmin())
        closest_ca_t_atom = str(target_heavy_atom_names[closest_ca_t_idx])
        closest_ca_t_unp = int(target_heavy_uniprot_pos[closest_ca_t_idx])
        closest_ca_t_resname = str(target_heavy_resnames[closest_ca_t_idx])

        nearest_target_distances[f"B{r}"] = {
            "residue": f"B{r}",
            "binder_position": r,
            "parent_amino_acid": AA3[b_resname],
            "parent_resname": b_resname,
            "heavy_atom_count": len(b_res_heavy_idx),
            "min_heavy_to_target_heavy_distance_angstrom": round(min_dist, 4),
            "closest_binder_atom": closest_b_atom,
            "closest_target_atom": closest_t_atom,
            "closest_target_uniprot_position": closest_t_unp,
            "closest_target_cif_label_seq_id": closest_t_cif_label,
            "closest_target_resname": closest_t_resname,
            "ca_to_nearest_target_heavy_distance_angstrom": round(min_ca_dist, 4),
            "ca_closest_target_atom": closest_ca_t_atom,
            "ca_closest_target_uniprot_position": closest_ca_t_unp,
            "ca_closest_target_resname": closest_ca_t_resname,
        }

    # 7. Write conditions.json
    conditions_data = {
        "candidate_id": expected_candidate_id,
        "model_type": "soluble_mpnn",
        "temperature": 0.1,
        "seed": 401,
        "samples": 16,
        "fixed_chains": ["A"],
        "designed_chains": ["B"],
        "derivation": "predeclared, not derived from scores",
        "required_parent_residues": {
            "B18": "N",
            "B25": "C",
            "B29": "N",
        },
        "cys25": {
            "model_type": "soluble_mpnn",
            "temperature": 0.1,
            "seed": 401,
            "samples": 16,
            "fixed_chains": ["A"],
            "redesigned_residues": ["B25"],
            "omit": {"B25": "C"},
            "omit_file": "cys25-omit.json",
            "notes": "Exact target chain A fixed; only specified B residue B25 can change; CYS omitted at B25; predeclared parameters",
        },
        "triple": {
            "model_type": "soluble_mpnn",
            "temperature": 0.1,
            "seed": 401,
            "samples": 16,
            "fixed_chains": ["A"],
            "redesigned_residues": ["B18", "B25", "B29"],
            "omit": {"B18": "N", "B25": "C", "B29": "N"},
            "omit_file": "triple-omit.json",
            "notes": "Exact target chain A fixed; only specified B residues B18, B25, B29 can change; parent amino acids omitted; predeclared parameters",
        },
        "arms": {
            "cys25": {
                "model_type": "soluble_mpnn",
                "temperature": 0.1,
                "seed": 401,
                "samples": 16,
                "fixed_chains": ["A"],
                "redesigned_residues": ["B25"],
                "omit": {"B25": "C"},
                "omit_file": "cys25-omit.json",
            },
            "triple": {
                "model_type": "soluble_mpnn",
                "temperature": 0.1,
                "seed": 401,
                "samples": 16,
                "fixed_chains": ["A"],
                "redesigned_residues": ["B18", "B25", "B29"],
                "omit": {"B18": "N", "B25": "C", "B29": "N"},
                "omit_file": "triple-omit.json",
            },
        },
        "scope": "Predeclared repair conditions for constrained SolubleMPNN; research only; no model inference executed",
    }
    conditions_path = output_dir / "conditions.json"
    write_json(conditions_path, conditions_data)

    # 8. Write native LigandMPNN CLI omit dictionaries
    cys25_omit_dict = {"B25": "C"}
    cys25_omit_path = output_dir / "cys25-omit.json"
    write_json(cys25_omit_path, cys25_omit_dict)

    triple_omit_dict = {"B18": "N", "B25": "C", "B29": "N"}
    triple_omit_path = output_dir / "triple-omit.json"
    write_json(triple_omit_path, triple_omit_dict)

    # 9. Build full residue map for audit
    target_residue_map = []
    for r_num in range(1, 196):
        unp_pos = r_num + 36
        aa_letter = target_cif_seq[r_num - 1]
        mask_r = (asym_ids == "A") & (label_seq_ids == r_num)
        atom_count = int(np.sum(mask_r))
        resn = str(comp_ids[mask_r][0])
        target_residue_map.append({
            "cif_label_seq_id": r_num,
            "uniprot_position": unp_pos,
            "pdb_chain": "A",
            "pdb_resseq": unp_pos,
            "amino_acid": aa_letter,
            "resname": resn,
            "atom_count": atom_count,
        })

    binder_residue_map = []
    for r_num in range(1, 61):
        aa_letter = binder_cif_seq[r_num - 1]
        mask_r = (asym_ids == "B") & (label_seq_ids == r_num)
        atom_count = int(np.sum(mask_r))
        resn = str(comp_ids[mask_r][0])
        binder_residue_map.append({
            "cif_label_seq_id": r_num,
            "binder_position": r_num,
            "pdb_chain": "B",
            "pdb_resseq": r_num,
            "amino_acid": aa_letter,
            "resname": resn,
            "atom_count": atom_count,
        })

    # 10. Write source and mapping audit
    audit_data: Dict[str, Any] = {
        "candidate_id": expected_candidate_id,
        "parent_sequence": binder_cif_seq,
        "target_sequence": target_cif_seq,
        "submission_eligible": False,
        "status": "passed_independent_audit; inputs_prepared_for_constrained_solublempnn_repair; no_inference_executed",
        "source_hashes": source_hashes,
        "input_hashes": source_hashes,
        "settings": {
            "model_type": "soluble_mpnn",
            "temperature": 0.1,
            "seed": 401,
            "samples": 16,
            "fixed_chains": ["A"],
            "derivation": "predeclared, not derived from scores",
            "arms": {
                "cys25": {
                    "redesigned_residues": ["B25"],
                    "omit": {"B25": "C"},
                },
                "triple": {
                    "redesigned_residues": ["B18", "B25", "B29"],
                    "omit": {"B18": "N", "B25": "C", "B29": "N"},
                },
            },
        },
        "verification": {
            "generator_structure_sha256_verified": True,
            "candidate_identity_verified": True,
            "target_sequence_matches_reference_audit": True,
            "target_sequence_matches_manifest_slice": True,
            "binder_sequence_matches_candidate_record": True,
            "target_residues_count": 195,
            "target_uniprot_range": [37, 231],
            "binder_residues_count": 60,
            "binder_position_range": [1, 60],
            "finite_coordinates": True,
            "unique_per_residue_ca": True,
            "all_20_standard_amino_acids": True,
            "backbone_atoms_complete": True,
            "required_parent_residues": {"B18": "N", "B25": "C", "B29": "N"},
            "parent_residues_satisfied": True,
            "coordinate_round_trip_checked": True,
            "coordinate_round_trip_max_error_angstrom": round(max_round_trip_error, 8),
            "starting_input_audit_reports_no_supplied_binder": True,
        },
        "nearest_target_distances": nearest_target_distances,
        "nearest_target_distances_disclaimer": (
            "Geometric distances measured between unmodified static coordinates of the generative model prediction "
            "and target reference heavy atoms. No binding energy, affinity, stability, or experimental activity claims "
            "are made or implied."
        ),
        "full_residue_map": {
            "target": target_residue_map,
            "binder": binder_residue_map,
            "target_summary": {
                "chain": "A",
                "cif_label_seq_id_range": [1, 195],
                "uniprot_range": [37, 231],
                "residue_count": 195,
                "atom_count": int(np.sum(asym_ids == "A")),
            },
            "binder_summary": {
                "chain": "B",
                "cif_label_seq_id_range": [1, 60],
                "binder_position_range": [1, 60],
                "residue_count": 60,
                "atom_count": int(np.sum(asym_ids == "B")),
            },
            "total_atoms": total_atoms,
        },
        "scope": (
            "Research-only preparation and independent audit of constrained SolubleMPNN repair inputs. "
            "No candidate submission, no model inference executed."
        ),
    }

    # Write audit to source-and-mapping-audit.json and audit.json
    audit_path = output_dir / "audit.json"
    source_audit_path = output_dir / "source-and-mapping-audit.json"
    write_json(audit_path, audit_data)
    write_json(source_audit_path, audit_data)

    # 11. Compile output hashes and generate plain text / JSON manifest
    output_files_to_hash = [
        "seed101-complex.pdb",
        "conditions.json",
        "cys25-omit.json",
        "triple-omit.json",
        "audit.json",
        "source-and-mapping-audit.json",
    ]
    output_sha256 = {fname: digest(output_dir / fname) for fname in output_files_to_hash}

    # Do not embed audit files' own hashes inside themselves. Their final
    # digests are recorded separately by the manifest after the audit is saved.
    audit_data["output_hashes"] = {
        fname: output_sha256[fname]
        for fname in output_files_to_hash
        if fname not in ("audit.json", "source-and-mapping-audit.json")
    }
    write_json(audit_path, audit_data)
    write_json(source_audit_path, audit_data)
    # Re-compute hashes for updated audit files
    output_sha256["audit.json"] = digest(audit_path)
    output_sha256["source-and-mapping-audit.json"] = digest(source_audit_path)

    # Manifest JSON
    manifest_obj = {
        "manifest_version": "1.0",
        "candidate_id": expected_candidate_id,
        "submission_eligible": False,
        "submission_eligible_count": 0,
        "source_sha256": source_hashes,
        "output_sha256": output_sha256,
        "files": [
            {
                "name": fname,
                "sha256": output_sha256[fname],
                "bytes": (output_dir / fname).stat().st_size,
            }
            for fname in output_files_to_hash
        ],
        "status": "passed_independent_audit; inputs_prepared_for_constrained_solublempnn_repair",
    }
    manifest_json_path = output_dir / "manifest.json"
    write_json(manifest_json_path, manifest_obj)

    # Manifest Plain Text (standard sha256 checksum format)
    manifest_txt_lines = []
    for fname in sorted(output_files_to_hash + ["manifest.json"]):
        h = digest(output_dir / fname)
        manifest_txt_lines.append(f"{h}  {fname}")
    manifest_txt_path = output_dir / "manifest.txt"
    manifest_txt_path.write_text("\n".join(manifest_txt_lines) + "\n")

    # Output execution summary
    summary = {
        "status": "passed_independent_audit; inputs_prepared_for_constrained_solublempnn_repair",
        "candidate_id": expected_candidate_id,
        "output_dir": str(output_dir),
        "files_created": sorted([p.name for p in output_dir.iterdir()]),
        "coordinate_round_trip_max_error_angstrom": max_round_trip_error,
        "nearest_target_distances": {
            k: {
                "closest_binder_atom": v["closest_binder_atom"],
                "closest_target": f"A{v['closest_target_uniprot_position']} {v['closest_target_resname']} {v['closest_target_atom']}",
                "min_heavy_distance_angstrom": v["min_heavy_to_target_heavy_distance_angstrom"],
                "min_ca_distance_angstrom": v["ca_to_nearest_target_heavy_distance_angstrom"],
            }
            for k, v in nearest_target_distances.items()
        },
        "submission_eligible": False,
        "disclaimer": (
            "Research-only preparation for constrained SolubleMPNN repair; "
            "no model inference executed; no candidate submission; no energy or affinity claims."
        ),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
