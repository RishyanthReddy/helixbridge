"""Convert only the audited WT reference; preserve coordinates and UniProt numbering."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from biotite.structure.io.pdb import PDBFile
from biotite.structure.io.pdbx import CIFFile, get_structure, set_structure
from binder_campaign.runner import digest, write_json
from binder_campaign.structure import AA3

root = Path(os.environ["TASK_ROOT"])
pipeline = root / "src/pipeline"
source = root / "src/BindCraft2/settings/target/structures/hIL7RA.pdb"
source_audit = json.loads((pipeline / "config/il7ra-focused-reference-audit.json").read_text())
if digest(source) != source_audit["sha256"]:
    raise ValueError("Reference changed after its identity audit")
target = json.loads((pipeline / "data/targets/il7ra/manifest.json").read_text())
atoms = PDBFile.read(source).get_structure(model=1)
ca = atoms[atoms.atom_name == "CA"]
positions = ca.res_id.tolist()
sequence = "".join(AA3[x] for x in ca.res_name)
expected = "".join(target["sequence"][p - target["start"]] for p in positions)
if positions != list(range(37, 232)) or sequence != expected or set(ca.chain_id) != {"A"}:
    raise ValueError("Unexpected numbering, chain or residue identity")
out = pipeline / "data/targets/il7ra/rfd4-reference"
if out.exists():
    raise ValueError("Use a fresh directory; refusing to overwrite audited reference inputs")
out.mkdir(parents=True)
cif = CIFFile()
set_structure(cif, atoms, data_block="il7ra_reference")
cif.write(out / "target.cif")
reread = get_structure(CIFFile.read(out / "target.cif"), model=1, use_author_fields=False)
reca = reread[reread.atom_name == "CA"]
if (reca.res_id.tolist() != positions or reca.res_name.tolist() != ca.res_name.tolist()
        or reca.chain_id.tolist() != ca.chain_id.tolist()
        or not np.allclose(reread.coord, atoms.coord, atol=0.001, rtol=0)):
    raise ValueError("CIF round trip changed numbering/sequence/coordinates")
hotspots = [100, 101, 102, 158, 159, 161, 211, 212, 213, 214]
write_json(out / "conditions.json", {"il7ra": {
    "input": "target.cif", "contig": "60, /0, A37-231",
    "conditions": {
        "C_CRDGRP": {"1": [{"select": "sel('A/*/*/[N,CA,C,O]')"}]},
        "C_SEQ": {"true": [{"select": "sel('A')"}]},
        "C_HOT": {"true": [{"select": "sel('A/*/[" + ",".join(map(str, hotspots)) + "]')"}]},
    },
}})
write_json(out / "audit.json", {
    "target_id": "il7ra", "role": "reference_rehearsal_only",
    "source_sha256": digest(source), "source_provenance": source_audit["provenance_limit"],
    "label_seq_id_equals_uniprot_position": True, "reference_chain": "A",
    "positions": positions, "reference_sequence": sequence, "identity_mismatches": [],
    "missing_official_positions": source_audit["missing_official_positions"],
    "binder_length": 60, "hotspots_uniprot": hotspots,
    "coordinates_and_identities_round_trip_checked": True,
    "native_input_cleanup": "RFD4 raw-input preparation may add missing heavy atoms; reference coordinates are retained here without repair.",
    "files": {name: digest(out / name) for name in ("target.cif", "conditions.json")},
})
print("Prepared canonical-identity, numbered IL7RA reference conditions; not yet a generation result", flush=True)
