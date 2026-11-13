#!/usr/bin/env python3
"""Target-held-out rule selection with conservative sequence/lineage grouping.

Evaluation only. No binder sequences are exported or used in generation.
"""
import argparse
import importlib.util
import json
from pathlib import Path

from Bio.Align import PairwiseAligner
import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location('audit', Path(__file__).with_name('analyze-screen-benchmark.py'))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
RULES = ('ef2full_seed0', 'boltz2_seed0', 'consensus_mean_seed0', 'consensus_min_seed0')


def build_families(frame, provenance, steps):
    """Connect shared lineage tokens or >=80% LCS similarity of the longer sequence.

    LCS is deliberately permissive; it is not a structural-fold or evolutionary
    family definition. Missing ancestry cannot be reconstructed from these tables.
    """
    uuids = frame.uuid.tolist()
    parent = {key: key for key in uuids}

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left, right):
        left, right = find(left), find(right)
        if left != right:
            parent[max(left, right)] = min(left, right)

    owners = {}
    def connect(uuid, token):
        if pd.isna(token) or not str(token).strip() or str(token).lower() in ('none', 'nan', 'unknown'):
            return
        token = str(token)
        if token in owners:
            union(uuid, owners[token])
        else:
            owners[token] = uuid

    for row in provenance.itertuples(index=False):
        if row.uuid in parent:
            connect(row.uuid, row.uuid)
            if hasattr(row, 'full_name'):
                connect(row.uuid, row.full_name)
    for row in provenance.itertuples(index=False):
        if row.uuid not in parent:
            continue
        for field in ('prov_root_backbone_id', 'prov_parent_design_id'):
            connect(row.uuid, getattr(row, field))
    for row in steps.itertuples(index=False):
        if row.uuid in parent:
            connect(row.uuid, row.ancestor_design_id)

    aligner = PairwiseAligner(mode='global', match_score=1, mismatch_score=0,
                             open_gap_score=0, extend_gap_score=0)
    sequence_links = 0
    sequences = frame.sequence.tolist()
    for i, left in enumerate(sequences):
        for j in range(i):
            right = sequences[j]
            longest = max(len(left), len(right))
            if min(len(left), len(right)) < 0.8 * longest:
                continue
            if aligner.score(left, right) >= 0.8 * longest:
                union(uuids[i], uuids[j])
                sequence_links += 1
    groups = pd.DataFrame({'uuid': uuids, 'family': [find(key) for key in uuids]})
    return groups, sequence_links


def fold_split(frame, target):
    held = frame[frame.target == target].copy()
    held_families = set(held.family)
    train = frame[(frame.target != target) & ~frame.family.isin(held_families)].copy()
    if set(train.target) & {target} or set(train.family) & held_families:
        raise ValueError('Target/family leakage in split')
    return train, held


def evaluate_rules(frame, endpoint='vendor_concordant'):
    result = []
    column, positive, negative = audit.ENDPOINTS[endpoint]
    for target, group in frame.groupby('target'):
        # Rank before outcomes are revealed; unknowns remain in the selected set.
        labels = group[column].map({positive: 1., negative: 0.})
        if not labels.notna().any():
            continue
        for rule in RULES:
            metrics = audit.operational_top_k(labels, audit.score_for_analysis(group, rule), 20)
            known = labels.notna()
            binary = audit.binary_metrics(labels[known], audit.score_for_analysis(group, rule)[known])
            result.append({'target': target, 'endpoint': endpoint, 'rule': rule, **metrics, **binary})
    return pd.DataFrame(result)


def held_target_folds(representatives, endpoint):
    folds = []
    for target in sorted(representatives.target.unique()):
        train, held = fold_split(representatives, target)
        development = evaluate_rules(train, endpoint)
        test = evaluate_rules(held, endpoint)
        if test.empty:
            folds.append({'held_target': target, 'endpoint': endpoint,
                          'status': 'no_evaluable_endpoint', 'train_n': len(train), 'held_n': len(held)})
            continue
        means = development.groupby('rule').observed_positive_fraction.mean()
        selected = sorted(RULES, key=lambda rule: (-means[rule], RULES.index(rule)))[0]
        scores = test.set_index('rule')
        folds.append({'held_target': target, 'endpoint': endpoint, 'status': 'evaluated', 'chosen_rule': selected,
                      'train_n': len(train), 'held_n': len(held),
                      'purged_family_overlap_n': int(((representatives.target != target)
                                                     & representatives.family.isin(set(held.family))).sum()),
                      'development_target_count': int(development.target.nunique()),
                      'test_confirmed_lower_fraction': float(scores.loc[selected, 'observed_positive_fraction']),
                      'test_known_fraction': float(scores.loc[selected, 'known_fraction']),
                      'test_possible_upper_fraction': float(scores.loc[selected, 'possible_positive_upper_fraction']),
                      'baseline_ef2_lower_fraction': float(scores.loc['ef2full_seed0', 'observed_positive_fraction']),
                      'baseline_boltz_lower_fraction': float(scores.loc['boltz2_seed0', 'observed_positive_fraction'])})
    return pd.DataFrame(folds)


def summarize_folds(folds):
    valid = folds[folds.status == 'evaluated']
    if valid.empty:
        return {'evaluated_targets': 0}
    delta = (valid.test_confirmed_lower_fraction - valid.baseline_ef2_lower_fraction).to_numpy()
    rng = np.random.default_rng(20261102)
    boot = rng.choice(delta, size=(5000, len(delta)), replace=True).mean(axis=1)
    return {'evaluated_targets': len(valid), 'rule_choices': valid.chosen_rule.value_counts().to_dict(),
            'mean_held_target_confirmed_lower_fraction': float(valid.test_confirmed_lower_fraction.mean()),
            'mean_held_target_possible_upper_fraction': float(valid.test_possible_upper_fraction.mean()),
            'paired_delta_vs_ef2_lower_fraction': float(delta.mean()),
            'target_bootstrap_delta_ci95': np.quantile(boot, [.025, .975]).tolist()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError('Use a fresh output directory')
    hashes = audit.validate_inputs(args.data_root)
    frame, _ = audit.load_scores(args.data_root)
    frame = frame[~frame.target.isin(audit.EXCLUDED_NONHUMAN_TARGETS)].copy()
    provenance_path = args.data_root / 'data/tables/insilico/provenance_summary.parquet'
    steps_path = args.data_root / 'data/tables/insilico/provenance_steps.parquet'
    provenance = pd.read_parquet(provenance_path)
    steps = pd.read_parquet(steps_path)
    for path in (provenance_path, steps_path):
        hashes[str(path.relative_to(args.data_root))] = {'sha256': audit.digest(path), 'bytes': path.stat().st_size}
    if set(provenance.uuid) != set(pd.read_parquet(args.data_root / 'data/tables/design_summary.parquet').uuid):
        raise ValueError('Provenance UUID set differs from design table')
    families, links = build_families(frame.merge(
        pd.read_parquet(args.data_root / 'data/tables/design_summary.parquet')[['uuid', 'sequence']],
        on='uuid', validate='one_to_one'), provenance, steps)
    frame = frame.merge(families, on='uuid', validate='one_to_one')
    # One score-blind representative per family and target prevents variant inflation.
    representatives = frame.sort_values('uuid').drop_duplicates(['target', 'family']).copy()
    # Recompute percentiles in the family-representative selection pool.
    for model in ('ef2full', 'boltz2'):
        representatives[model + '_seed0_target_rank'] = representatives.groupby('target')[model + '_seed0'].rank(method='average', pct=True)
    rank_columns = ['ef2full_seed0_target_rank', 'boltz2_seed0_target_rank']
    representatives['consensus_mean_seed0'] = representatives[rank_columns].mean(axis=1)
    representatives['consensus_min_seed0'] = representatives[rank_columns].min(axis=1)
    folds_by_endpoint = {endpoint: held_target_folds(representatives, endpoint) for endpoint in audit.ENDPOINTS}
    summaries = {endpoint: summarize_folds(folds) for endpoint, folds in folds_by_endpoint.items()}
    summary = {'status': 'evaluation_only', 'source_hashes': hashes,
               'sequence_grouping': 'shared lineage OR global LCS >= 80% of longer sequence; connected components',
               'sequence_similarity_links': links, 'design_count': len(frame),
               'family_count': int(families.family.nunique()), 'representative_count': len(representatives),
               'endpoints': summaries,
               'limits': ['Small and preselected dataset; unknown predictor-training overlap.',
                          'Shared ancestry may be incomplete; LCS groups are not fold families.',
                          'Human analyst has already inspected these data; this is internal resampling, not a pristine external test.',
                          'No calibrated probability or transferable score cutoff is established.']}
    args.output_dir.mkdir(parents=True)
    frame[['uuid', 'target', 'family']].to_csv(args.output_dir / 'family-assignments.csv', index=False)
    pd.concat(list(folds_by_endpoint.values()), ignore_index=True).to_csv(args.output_dir / 'held-target-folds.csv', index=False)
    pd.concat([evaluate_rules(representatives, endpoint) for endpoint in audit.ENDPOINTS], ignore_index=True).to_csv(
        args.output_dir / 'per-target-rule-metrics.csv', index=False)
    audit.write_json(args.output_dir / 'summary.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
