import itertools
import unittest
from binder_campaign.sequence_review import overlap_diagnostic, longest_common_substring, sequence_diagnostic


class SequenceReviewTests(unittest.TestCase):
    def test_contiguous_overlap_matches_exhaustive_oracle(self):
        words = [''.join(x) for n in range(1, 5) for x in itertools.product('AC', repeat=n)]
        for left in words:
            for right in words:
                oracle = max([0] + [j - i for i in range(len(left)) for j in range(i + 1, len(left) + 1)
                                    if left[i:j] in right])
                length, i, j = longest_common_substring(left, right)
                self.assertEqual(length, oracle)
                self.assertEqual(left[i:i + length], right[j:j + length])

    def test_strict_90pct_boundary_and_terminal_truncation(self):
        self.assertFalse(overlap_diagnostic('ACDEFGHIKL', 'ACDEFGHIKM')['over_90pct_contiguous_in_either_direction'])
        self.assertTrue(overlap_diagnostic('ACDEFGHIKL', 'ACDEFGHIKLMM')['over_90pct_contiguous_in_either_direction'])
        self.assertFalse(overlap_diagnostic('ACDEFGHIKL', 'ACDEMFGHIKL')['over_90pct_contiguous_in_either_direction'])
        with self.assertRaises(ValueError):
            overlap_diagnostic('ACDX', 'ACDA')

    def test_overlapping_sequons_and_single_cysteine_are_retained(self):
        result = sequence_diagnostic('NNSSTC' + 'A' * 34)
        self.assertEqual([r['position'] for r in result['N_glycosylation_sequons']], [1, 2])
        self.assertTrue(result['cysteine_count_odd'])
        self.assertEqual(result['cysteine_positions'], [6])
