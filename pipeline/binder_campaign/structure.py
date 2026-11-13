"""Conservative PDB reference extraction using a verified linear DBREF map.

This is NOT a general mmCIF/SIFTS mapper: insertion codes or non-linear maps
are refused. Mutations and missing positions remain explicit in the report.
"""
import json
from pathlib import Path
from .runner import digest, write_json

AA3 = dict(zip(
    "ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL".split(),
    "ARNDCQEGHILKMFPSTWYV"))


def extract_reference(pdb_path, manifest_path, sifts_path, output):
    pdb_path, output = Path(pdb_path), Path(output)
    manifest = json.loads(Path(manifest_path).read_text())
    mapping = json.loads(Path(sifts_path).read_text())
    base = manifest["uniprot"].split("-")[0]
    chain = manifest["chains"][0]
    lines = pdb_path.read_text().splitlines()
    refs = [l for l in lines if l.startswith("DBREF ") and l[12] == chain and l[33:41].strip() == base]
    if len(refs) != 1:
        raise ValueError("Expected exactly one matching DBREF")
    ref = refs[0]
    pdb_start, pdb_end = int(ref[14:18]), int(ref[20:24])
    unp_start, unp_end = int(ref[55:60]), int(ref[62:67])
    if any(ref[i].strip() for i in (18,24,60,67)) or pdb_end-pdb_start != unp_end-unp_start:
        raise ValueError("Non-linear/insertion DBREF map requires a general residue mapper")
    sifts_maps = mapping[manifest["pdb"].lower()]["UniProt"][base]["mappings"]
    if not any(m["chain_id"] == chain and m["unp_start"] == unp_start and m["unp_end"] == unp_end for m in sifts_maps):
        raise ValueError("SIFTS and DBREF disagree")
    offset = unp_start - pdb_start
    residues, extracted = {}, []
    for line in lines:
        if not line.startswith("ATOM  ") or line[21] != chain:
            continue
        if line[26].strip():
            raise ValueError("Insertion codes require a general residue mapper")
        number = int(line[22:26]); unp = number + offset
        if not manifest["start"] <= unp <= manifest["end"]:
            continue
        letter = AA3[line[17:20]]
        if unp in residues and residues[unp]["observed"] != letter:
            raise ValueError("Conflicting residue identity")
        expected = manifest["sequence"][unp-manifest["start"]]
        residues[unp] = {"uniprot_position":unp,"source_chain":chain,"source_number":number,
                         "observed":letter,"expected":expected}
        if line[16] not in (" ", "A"):
            continue
        # Single protein chain, WT numbering, original residue identity unchanged.
        extracted.append(line[:16]+" "+line[17:21]+"A"+f"{unp:4d}"+line[26:])
    if not residues:
        raise ValueError("No mapped protein coordinates")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("REMARK Reference rehearsal only; mutations/missing residues in mapping.json\n" + "\n".join(extracted) + "\nTER\nEND\n")
    report = {"pdb":manifest["pdb"],"original_chain":chain,"output_chain":"A",
              "numbering":"UniProt positions; residue identities retained from PDB",
              "pdb_sha256":digest(pdb_path),"sifts_sha256":digest(sifts_path),"output_sha256":digest(output),
              "observed_positions":len(residues),"residues":list(residues.values()),
              "missing_official_positions":[i for i in range(manifest["start"],manifest["end"]+1) if i not in residues],
              "mismatches":[v for v in residues.values() if v["observed"] != v["expected"]],
              "status":"reference_rehearsal_only; full official construct and sequence reconciliation required"}
    write_json(output.parent / "mapping.json", report)
    return report
