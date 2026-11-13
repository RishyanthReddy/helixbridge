import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from binder_campaign.targets import prepare_targets


class TargetTests(unittest.TestCase):
    def prepare(self, isoform="Displayed", last="G"):
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); root=Path(temp.name)
        config={"rules_reviewed":"2026-11-01","targets":[{"id":"fixture","uniprot":"TEST-1","start":1,"end":3,"first":"M","last":last}]}
        entry={"sequence":{"value":"MAG"},"comments":[{"commentType":"ALTERNATIVE PRODUCTS","isoforms":[{"isoformIds":["TEST-1"],"isoformSequenceStatus":isoform}]}]}
        (root/'sources').mkdir(); (root/'sources/TEST.json').write_text(json.dumps(entry))
        (root/'config.json').write_text(json.dumps(config))
        return root

    def test_requested_isoform_must_be_displayed_and_endpoints_must_match(self):
        for root in [self.prepare(isoform="Described"),self.prepare(last="V")]:
            with self.assertRaises(ValueError):
                prepare_targets(root/'config.json',root)

    def test_sequence_hash_is_distinct_from_fasta_hash(self):
        root=self.prepare(); records=prepare_targets(root/'config.json',root)
        self.assertEqual(records[0]['sequence_sha256'],hashlib.sha256(b'MAG').hexdigest())
        self.assertNotEqual(records[0]['sequence_sha256'],records[0]['fasta_sha256'])
