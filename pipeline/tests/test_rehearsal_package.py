"""Protect source-state validation used by the rehearsal review package."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


class RehearsalPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "scripts" / "assemble-rehearsal-package.py"
        spec = importlib.util.spec_from_file_location("rehearsal_package", path)
        cls.package = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.package)

    def test_state_hash_must_match_file_and_be_unambiguous(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "metrics.json"
            source.write_text('{"value": 1}')
            state = {"outputs": {"/remote/prediction/metrics.json": self.package.sha256(source)}}
            self.package.verify_state_file(state, "outputs", "/prediction/metrics.json", source)
            source.write_text('{"value": 2}')
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                self.package.verify_state_file(state, "outputs", "/prediction/metrics.json", source)
            state["outputs"]["/other/prediction/metrics.json"] = self.package.sha256(source)
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                self.package.verify_state_file(state, "outputs", "/prediction/metrics.json", source)


if __name__ == "__main__":
    unittest.main()
