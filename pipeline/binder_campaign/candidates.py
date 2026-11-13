"""Import BC2 tables without turning generator scores into official affinity."""
import csv
import json
from pathlib import Path
from .runner import digest, write_json

ALPHABET = set("ACDEFGHIKLMNPQRSTVWY")


def import_rfd4(audit_path, target_manifest, output):
    """Import one verified rehearsal output without promoting it to an entry."""
    audit_path = Path(audit_path)
    audit = json.loads(audit_path.read_text())
    target = json.loads(Path(target_manifest).read_text())
    reference = audit['reference_audit']
    if reference['role'] != 'reference_rehearsal_only' or reference['target_id'] != target['id']:
        raise ValueError('Audited rehearsal target does not match candidate target')
    structure = Path(audit['generated_structure'])
    if digest(structure) != audit['generated_sha256']:
        raise ValueError('Generated structure changed after its mapping/identity check')
    sequence = audit['binder_sequence']
    reasons = []
    if not sequence or set(sequence) - ALPHABET:
        reasons.append('invalid_alphabet_or_multichain')
    if not target['min_length'] <= len(sequence) <= target['max_length']:
        reasons.append('wrong_length')
    if target['format'] != 'minibinder':
        reasons.append('format_and_framework_review_pending')
    identity = digest(audit_path)[:12]
    record = {
        'candidate_id': target['id'] + '-rfd4-' + identity,
        'target_id': target['id'], 'sequence': sequence, 'format': target['format'],
        'generator': 'RFD4-Proteina', 'generator_revision': audit['code_revision'],
        'campaign_kind': 'reference_rehearsal', 'generator_audit': audit,
        'generator_structure': str(structure.resolve()), 'generator_structure_sha256': digest(structure),
        'generator_target_chain': audit['target_chain'], 'generator_binder_chain': audit['binder_chain'],
        'backbone_family_id': target['id'] + '-rfd4-seed' + str(audit['seed']) + '-' + identity,
        'source_audit': str(audit_path.resolve()), 'source_sha256': digest(audit_path),
        'qc_reasons': reasons, 'screen_status': 'not_run', 'independent_prediction_status': 'not_run',
        'novelty_review': 'pending', 'submission_eligible': False,
    }
    write_json(output, {'candidates': [record], 'count': 1,
                        'note': 'Reference rehearsal import only; independent prediction and review pending'})
    return [record]


def import_bc2(table_path, target_manifest, output, revision, campaign_kind):
    table = Path(table_path)
    target = json.loads(Path(target_manifest).read_text())
    metadata_path = table.parent.parent / "campaign_metadata.json"
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else None
    if campaign_kind not in ("reference_rehearsal", "competition_campaign"):
        raise ValueError("Explicit campaign kind required")
    with table.open(newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or "Binder_Sequence" not in reader.fieldnames:
            raise ValueError("BC2 table lacks Binder_Sequence")
        rows = list(reader)
    seen, records = set(), []
    for index, row in enumerate(rows):
        sequence = row["Binder_Sequence"].strip()
        reasons = []
        if not sequence or set(sequence)-ALPHABET:
            reasons.append("invalid_alphabet_or_multichain")
        if not target["min_length"] <= len(sequence) <= target["max_length"]:
            reasons.append("wrong_length")
        if sequence in seen:
            reasons.append("exact_duplicate")
        seen.add(sequence)
        if target["format"] == "VHH":
            reasons.append("framework_CDR_and_scaffold_provenance_review_pending")
        design=row.get('design','')
        possible=[table.parent/'Complexes'/(design+'.cif'),table.parent/(design+'.cif')]
        structures=[p for p in possible if p.is_file()]
        if len(structures)!=1:
            reasons.append('generator_structure_missing_or_ambiguous')
        records.append({"candidate_id":target["id"]+"-"+str(index+1).zfill(5),
                        "target_id":target["id"],"sequence":sequence,"format":target["format"],
                        "generator":"BindCraft2","generator_revision":revision,"campaign_kind":campaign_kind,
                        "generator_campaign_metadata":metadata,
                        "metadata_sha256":digest(metadata_path) if metadata is not None else None,
                        "generator_design_id":design,"backbone_family_id":design.rsplit('_candidate',1)[0],
                        "generator_structure":str(structures[0].resolve()) if len(structures)==1 else None,
                        "generator_structure_sha256":digest(structures[0]) if len(structures)==1 else None,
                        "source_table":str(table.resolve()),"source_sha256":digest(table),"source_row":index+2,
                        "generator_metrics":row,"qc_reasons":reasons,
                        "screen_status":"not_run","independent_prediction_status":"not_run",
                        "novelty_review":"pending","submission_eligible":False})
    write_json(output,{"candidates":records,"count":len(records),"note":"Generator table import only; no official admission or experimental claims"})
    return records


def export_draft(records_path, output, selected_ids):
    records = json.loads(Path(records_path).read_text())["candidates"]
    selected = [r for r in records if r["candidate_id"] in selected_ids]
    if len(selected) != len(set(selected_ids)) or not selected:
        raise ValueError("Select existing unique candidate IDs")
    tracks = {}
    for row in selected:
        tracks.setdefault(row["target_id"], []).append(row)
        if row["qc_reasons"] or row["campaign_kind"] != "competition_campaign":
            raise ValueError("Invalid or rehearsal candidate cannot enter a submission draft")
        if row["novelty_review"] != "passed" or row["independent_prediction_status"] != "reviewed":
            raise ValueError("Required novelty/structure review is incomplete")
        if row["screen_status"] not in ("approximation_reviewed", "official_protocol_reviewed"):
            raise ValueError("Admission evaluation review is incomplete")
    if any(len(rows)>20 or len({r["sequence"] for r in rows}) != len(rows) for rows in tracks.values()):
        raise ValueError("Per-track count or exact duplicate violation")
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["candidate_id","target_id","sequence"])
        writer.writeheader()
        writer.writerows({k:r[k] for k in writer.fieldnames} for r in selected)
    write_json(str(output)+".metadata.json", {"status":"internal_draft_only","official_csv_schema":"unconfirmed",
               "candidate_ids":[r["candidate_id"] for r in selected],"sha256":digest(output)})
