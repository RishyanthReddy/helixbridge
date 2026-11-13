"""Check metric definitions and the handling of unknown outcomes."""
import importlib.util
from pathlib import Path
import unittest

try:
    import pandas as pd
except ImportError:
    pd = None


@unittest.skipIf(pd is None, "benchmark analysis requires the isolated pandas environment")
class BenchmarkAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "scripts" / "analyze-screen-benchmark.py"
        spec = importlib.util.spec_from_file_location("benchmark_analysis", path)
        cls.analysis = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.analysis)

    def test_binary_metrics_with_ties(self):
        result = self.analysis.binary_metrics([1, 0, 1, 0], [0.8, 0.8, 0.7, 0.1])
        self.assertAlmostEqual(result["auroc"], 0.625)
        self.assertAlmostEqual(result["average_precision"], 7 / 12)

    def test_unknown_is_selected_before_outcome_is_revealed(self):
        result = self.analysis.operational_top_k(
            [None, 1, 0, 1], [0.99, 0.95, 0.8, 0.7], k=2
        )
        self.assertEqual(result["selected_positive_expected"], 1)
        self.assertEqual(result["selected_unknown_expected"], 1)
        self.assertEqual(result["known_fraction"], 0.5)
        self.assertEqual(result["observed_positive_fraction"], 0.5)
        self.assertEqual(result["possible_positive_upper_fraction"], 1)

    def test_cutoff_ties_are_fractional_and_conserve_count(self):
        result = self.analysis.operational_top_k(
            [1, None, 0, 1], [1.0, 0.5, 0.5, 0.5], k=2
        )
        self.assertAlmostEqual(result["selected_positive_expected"], 4 / 3)
        self.assertAlmostEqual(result["selected_negative_expected"], 1 / 3)
        self.assertAlmostEqual(result["selected_unknown_expected"], 1 / 3)
        self.assertAlmostEqual(result["known_fraction"], 5 / 6)
        self.assertAlmostEqual(result["possible_positive_upper_fraction"], 5 / 6)


if __name__ == "__main__":
    unittest.main()
