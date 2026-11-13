"""Download public UniProt targets, retaining exact official intervals and hashes."""
import json
import hashlib
from pathlib import Path
from urllib.request import urlopen, Request
from .runner import digest, write_json


def download(url, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path
    with urlopen(Request(url, headers={"User-Agent":"Changjiang-research-pipeline/0.1"}), timeout=60) as response:
        payload = response.read()
    if not payload:
        raise ValueError("Empty source: " + url)
    temporary = path.with_suffix(path.suffix + ".incoming")
    temporary.write_bytes(payload)
    temporary.replace(path)
    return path


def prepare_targets(config_path, destination):
    config = json.loads(Path(config_path).read_text())
    destination = Path(destination)
    records = []
    for target in config["targets"]:
        base = target["uniprot"].split("-")[0]
        url = "https://rest.uniprot.org/uniprotkb/" + base + ".json"
        source = download(url, destination / "sources" / (base + ".json"))
        entry = json.loads(source.read_text())
        if "-" in target["uniprot"]:
            isoforms = [i for c in entry.get("comments", []) if c.get("commentType") == "ALTERNATIVE PRODUCTS" for i in c.get("isoforms", [])]
            if not any(target["uniprot"] in i["isoformIds"] and i["isoformSequenceStatus"] == "Displayed" for i in isoforms):
                raise ValueError("Requested isoform not verified as displayed: " + target["uniprot"])
        sequence = entry["sequence"]["value"][target["start"]-1:target["end"]]
        if len(sequence) != target["end"]-target["start"]+1 or sequence[0] != target["first"] or sequence[-1] != target["last"]:
            raise ValueError("Official range/endpoint mismatch: " + target["id"])
        folder = destination / target["id"]
        folder.mkdir(parents=True, exist_ok=True)
        fasta = folder / "official.fasta"
        fasta.write_text(">" + target["id"] + "|" + target["uniprot"] + "|" + str(target["start"]) + "-" + str(target["end"]) + "\n" + sequence + "\n")
        record = {**target, "sequence":sequence, "sequence_sha256":hashlib.sha256(sequence.encode()).hexdigest(), "fasta_sha256":digest(fasta),
                  "source_url":url, "source_sha256":digest(source), "entry_audit":entry.get("entryAudit"),
                  "construct_status":"official_sequence_range; experimental_processing_unconfirmed"}
        write_json(folder / "manifest.json", record)
        records.append(record)
    write_json(destination / "manifest.json", {"rules_reviewed":config["rules_reviewed"], "targets":records})
    return records
