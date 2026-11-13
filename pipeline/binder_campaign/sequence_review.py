"""Transparent sequence diagnostics without an inferred binding/developability score."""
from collections import Counter
import math
import re

ALPHABET = set('ACDEFGHIKLMNPQRSTVWY')


def longest_common_substring(left, right):
    """Length and deterministic first locations of the longest exact contiguous overlap."""
    previous = [0] * (len(right) + 1)
    best = (0, 0, 0)
    for i, a in enumerate(left):
        current = [0] * (len(right) + 1)
        for j, b in enumerate(right):
            if a == b:
                length = current[j + 1] = previous[j] + 1
                if length > best[0]:
                    best = (length, i - length + 1, j - length + 1)
        previous = current
    return best


def overlap_diagnostic(left, right):
    if not left or not right or (set(left) | set(right)) - ALPHABET:
        raise ValueError('Require nonempty standard amino-acid sequences')
    length, left_start, right_start = longest_common_substring(left, right)
    return {'longest_identical_contiguous_length': length,
            'left_start_1based': left_start + 1 if length else None,
            'right_start_1based': right_start + 1 if length else None,
            'left_coverage': length / len(left), 'right_coverage': length / len(right),
            'exact_duplicate': left == right,
            'over_90pct_contiguous_in_either_direction': length * 10 > 9 * min(len(left), len(right))}


def sequence_diagnostic(sequence):
    if not 40 <= len(sequence) <= 100 or set(sequence) - ALPHABET:
        raise ValueError('Require a standard 40–100-residue minibinder')
    counts = Counter(sequence)
    def motif(pattern):
        return [{'position': m.start() + 1, 'motif': m.group(1)}
                for m in re.finditer('(?=(' + pattern + '))', sequence)]
    return {'length': len(sequence), 'composition': dict(sorted(counts.items())),
            'cysteine_positions': [i + 1 for i, a in enumerate(sequence) if a == 'C'],
            'cysteine_count_odd': counts['C'] % 2 == 1,
            'N_glycosylation_sequons': motif('N[^P][ST]'),
            'Asn_Gly_motifs': motif('NG'), 'Asp_Pro_motifs': motif('DP'),
            'DE_fraction': sum(counts[a] for a in 'DE') / len(sequence),
            'KR_fraction': sum(counts[a] for a in 'KR') / len(sequence),
            'hydrophobic_AVILMFWY_fraction': sum(counts[a] for a in 'AVILMFWY') / len(sequence),
            'longest_identical_run': max(len(m.group()) for m in re.finditer(r'(.)\1*', sequence)),
            'whole_sequence_shannon_entropy_bits': -sum(c / len(sequence) * math.log2(c / len(sequence))
                                                       for c in counts.values()),
            'scope': 'Descriptive counts/motifs only; no pI, aggregation, glycan occupancy, expression or binding prediction'}
