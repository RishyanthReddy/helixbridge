#!/usr/bin/env python3
"""Descriptive wet-lab audit for the one-seed complex-prediction screen.

This script is deliberately evaluation-only. It does not fit a classifier, tune a
threshold, or expose benchmark sequences as generator inputs. Scores are compared
within target because the source documentation says they are not comparable across
targets, stoichiometries, or predictors.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


REVISION = "9e1b81696da46835e9e9cde9a3da976e0abc92ab"
EXPECTED = {
    "data/tables/design_summary.parquet": {
        "sha256": "3e796869b8dc0c90d7ab0e12daf25308c0cf272d04c6a5e27281f903ecd18744",
        "rows": 1440,
    },
    "data/tables/insilico/cofold_predictions.parquet": {
        "sha256": "ba48010610daa9b9d184aa1ddb419beebdf728ccf745f5a8f3b48e4041e1a87d",
        "rows": 113550,
    },
    "data/tables/wetlab/summary.parquet": {
        "sha256": "f80c3cfce67cb7da53576a020d476c5b74efed44e61c6fceaec9ee7de5722f88",
        "rows": 1440,
    },
}
MODELS = ("ef2full", "boltz2")
DESIGN_STOICHIOMETRIES = ("1to1", "1to2", "1to3", "rnp")
ENDPOINTS = {
    "vendor_concordant": ("vendor_agreement", "both_bind", "neither_bind"),
    "adaptyv": ("adaptyv_binding", "binder", "non_binder"),
    "twist": ("twist_binding", "binder", "non_binder"),
}
COMPETITION_OVERLAP_TARGETS = ("EGFR", "IL-7Ra", "TNFa")
# Follow the initial non-pathogen-target scope; the source retains other targets.
EXCLUDED_NONHUMAN_TARGETS = ("BHRF1", "Nipah-G", "Cas9", "MBP")
PAIRED_COMPARISONS = (
    ("consensus_min_seed0", "ef2full_seed0"),
    ("consensus_mean_seed0", "ef2full_seed0"),
    ("ef2full_seed0", "boltz2_seed0"),
)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(clean(value), indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def clean(value):
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if pd.isna(value) if not isinstance(value, (dict, list, tuple)) else False:
        return None
    return value


def binary_metrics(labels, scores):
    frame = pd.DataFrame({"label": labels, "score": scores}).dropna()
    frame["label"] = frame["label"].astype(int)
    positives = int(frame["label"].sum())
    negatives = int(len(frame) - positives)
    result = {
        "n": int(len(frame)),
        "positives": positives,
        "negatives": negatives,
        "prevalence": positives / len(frame) if len(frame) else float("nan"),
        "auroc": float("nan"),
        "average_precision": float("nan"),
    }
    if not positives or not negatives:
        return result

    ranks = frame["score"].rank(method="average")
    positive_rank_sum = float(ranks[frame["label"] == 1].sum())
    result["auroc"] = (
        positive_rank_sum - positives * (positives + 1) / 2
    ) / (positives * negatives)

    grouped = (
        frame.groupby("score", sort=True)["label"]
        .agg(["sum", "count"])
        .sort_index(ascending=False)
    )
    true_positive = grouped["sum"].cumsum()
    false_positive = (grouped["count"] - grouped["sum"]).cumsum()
    recall = true_positive / positives
    prior_recall = true_positive.shift(fill_value=0) / positives
    precision = true_positive / (true_positive + false_positive)
    result["average_precision"] = float(((recall - prior_recall) * precision).sum())
    return result


def tie_adjusted_precision_at_k(labels, scores, k=20):
    frame = pd.DataFrame({"label": labels, "score": scores}).dropna()
    if frame.empty:
        return {"k_requested": k, "k_effective": 0, "precision": float("nan")}
    effective = min(k, len(frame))
    cutoff = float(frame["score"].sort_values(ascending=False).iloc[effective - 1])
    above = frame["score"] > cutoff
    tied = frame["score"] == cutoff
    needed_from_tie = effective - int(above.sum())
    expected_positive = float(frame.loc[above, "label"].sum())
    expected_positive += needed_from_tie * float(frame.loc[tied, "label"].mean())
    return {
        "k_requested": k,
        "k_effective": int(effective),
        "cutoff": cutoff,
        "cutoff_tie_count": int(tied.sum()),
        "precision": expected_positive / effective,
    }


def operational_top_k(labels, scores, k=20):
    """Select before revealing labels; treat missing/discordant labels as unknown.

    When the selection cutoff is tied, counts are expectations under random tie
    resolution. The lower and upper fractions are identification bounds, not
    confidence intervals or estimates of the true hit rate.
    """
    frame = pd.DataFrame({"label": labels, "score": scores}).dropna(subset=["score"])
    if not len(frame):
        raise ValueError("Cannot select from an empty score set")
    if not frame["label"].dropna().isin([0, 1]).all():
        raise ValueError("Labels must be 0, 1, or unknown")
    effective = min(k, len(frame))
    cutoff = float(frame["score"].sort_values(ascending=False).iloc[effective - 1])
    above = frame["score"] > cutoff
    tied = frame["score"] == cutoff
    needed = effective - int(above.sum())
    tie_weight = needed / int(tied.sum())

    def selected_count(mask):
        return float((above & mask).sum()) + tie_weight * float((tied & mask).sum())

    positive = selected_count(frame["label"].eq(1))
    negative = selected_count(frame["label"].eq(0))
    unknown = selected_count(frame["label"].isna())
    if not np.isclose(positive + negative + unknown, effective):
        raise ValueError("Selected counts do not sum to k")
    known = positive + negative
    return {
        "k_effective": int(effective),
        "cutoff_tie_count": int(tied.sum()),
        "selected_positive_expected": positive,
        "selected_negative_expected": negative,
        "selected_unknown_expected": unknown,
        "known_fraction": known / effective,
        "observed_positive_fraction": positive / effective,
        "possible_positive_upper_fraction": (positive + unknown) / effective,
        "positive_fraction_among_known": positive / known if known else float("nan"),
    }


def macro_bootstrap(per_target, metric, repeats, rng):
    values = per_target[["target", metric]].dropna()[metric].to_numpy(dtype=float)
    if not len(values):
        return {"n_targets": 0, "mean": None, "ci95": [None, None]}
    draws = rng.choice(values, size=(repeats, len(values)), replace=True).mean(axis=1)
    return {
        "n_targets": int(len(values)),
        "mean": float(values.mean()),
        "ci95": [float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))],
        "bootstrap_repeats": repeats,
    }


def summarize_macro(per_target, repeats, rng):
    rows = []
    for (endpoint, scorer), group in per_target.groupby(["endpoint", "scorer"], sort=True):
        row = {"endpoint": endpoint, "scorer": scorer}
        for metric in ("auroc", "average_precision", "precision_at_20_tie_adjusted"):
            row[metric] = macro_bootstrap(group, metric, repeats, rng)
        rows.append(row)
    return rows


def paired_target_bootstrap(per_target, endpoint, left, right, metric, repeats, rng):
    selected = per_target[per_target["endpoint"] == endpoint]
    wide = selected.pivot(index="target", columns="scorer", values=metric)
    paired = wide[[left, right]].dropna()
    differences = (paired[left] - paired[right]).to_numpy(dtype=float)
    if not len(differences):
        return {"n_targets": 0, "mean_difference": None, "ci95": [None, None]}
    draws = rng.choice(
        differences, size=(repeats, len(differences)), replace=True
    ).mean(axis=1)
    return {
        "n_targets": int(len(differences)),
        "mean_difference": float(differences.mean()),
        "ci95": [float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))],
        "bootstrap_repeats": repeats,
    }


def validate_inputs(root):
    evidence = {}
    for relative, expected in EXPECTED.items():
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = digest(path)
        if actual != expected["sha256"]:
            raise ValueError("Source hash mismatch: " + relative)
        evidence[relative] = {
            "sha256": actual,
            "bytes": path.stat().st_size,
            "expected_rows": expected["rows"],
        }
    return evidence


def load_scores(root):
    designs = pd.read_parquet(root / "data/tables/design_summary.parquet")
    cofold = pd.read_parquet(
        root / "data/tables/insilico/cofold_predictions.parquet",
        columns=[
            "uuid",
            "target",
            "cofolding_model",
            "stoichiometry",
            "target_form",
            "seed",
            "ipsae_min",
        ],
    )
    wetlab = pd.read_parquet(
        root / "data/tables/wetlab/summary.parquet", columns=["uuid"]
    )
    if len(designs) != EXPECTED["data/tables/design_summary.parquet"]["rows"]:
        raise ValueError("Unexpected design_summary row count")
    if len(cofold) != EXPECTED["data/tables/insilico/cofold_predictions.parquet"]["rows"]:
        raise ValueError("Unexpected cofold_predictions row count")
    if len(wetlab) != EXPECTED["data/tables/wetlab/summary.parquet"]["rows"]:
        raise ValueError("Unexpected wetlab summary row count")
    if designs["uuid"].duplicated().any() or wetlab["uuid"].duplicated().any():
        raise ValueError("UUIDs are not unique in summary tables")
    if set(designs["uuid"]) != set(wetlab["uuid"]):
        raise ValueError("Design and wet-lab UUID sets differ")

    filtered = cofold[
        cofold["cofolding_model"].isin(MODELS)
        & cofold["target_form"].fillna("").eq("")
        & cofold["stoichiometry"].isin(DESIGN_STOICHIOMETRIES)
    ].copy()
    filtered["seed"] = filtered["seed"].astype(str)
    expected_rows = len(designs) * len(MODELS) * 5
    if len(filtered) != expected_rows:
        raise ValueError(f"Expected {expected_rows} design-stoichiometry rows, got {len(filtered)}")
    keys = ["uuid", "cofolding_model", "seed"]
    if filtered.duplicated(keys).any():
        raise ValueError("Duplicate design/model/seed rows")
    group_sizes = filtered.groupby(["uuid", "cofolding_model"]).size()
    if not group_sizes.eq(5).all():
        raise ValueError("Every design/model must have exactly five seeds")
    if set(filtered["seed"]) != {"0", "1", "2", "3", "4"}:
        raise ValueError("Expected the five published seeds 0–4")
    if not np.isfinite(filtered["ipsae_min"]).all():
        raise ValueError("Non-finite ipSAE score in source rows")

    labels = designs[
        [
            "uuid",
            "target",
            "adaptyv_binding",
            "twist_binding",
            "vendor_agreement",
        ]
    ].copy()
    target_check = filtered.merge(
        labels[["uuid", "target"]], on="uuid", suffixes=("", "_label")
    )
    if not target_check["target"].eq(target_check["target_label"]).all():
        raise ValueError("Target labels disagree between score and design tables")

    wide = labels.copy()
    for model in MODELS:
        model_rows = filtered[filtered["cofolding_model"] == model]
        seed_zero = model_rows[model_rows["seed"] == "0"][["uuid", "ipsae_min"]]
        if len(seed_zero) != len(designs):
            raise ValueError(model + " does not have seed 0 for every design")
        best_five = model_rows.groupby("uuid", as_index=False)["ipsae_min"].max()
        summary_column = "ipsae_min_" + model
        best_check = best_five.merge(
            designs[["uuid", summary_column]], on="uuid", validate="one_to_one"
        )
        if not np.allclose(
            best_check["ipsae_min"],
            best_check[summary_column],
            rtol=0,
            atol=1e-7,
            equal_nan=True,
        ):
            raise ValueError(model + " best-of-five does not reproduce design_summary")
        wide = wide.merge(
            seed_zero.rename(columns={"ipsae_min": f"{model}_seed0"}), on="uuid", validate="one_to_one"
        )
        wide = wide.merge(
            best_five.rename(columns={"ipsae_min": f"{model}_best5"}), on="uuid", validate="one_to_one"
        )

    for variant in ("seed0", "best5"):
        for model in MODELS:
            wide[f"{model}_{variant}_target_rank"] = wide.groupby("target")[
                f"{model}_{variant}"
            ].rank(method="average", pct=True)
    wide["consensus_mean_seed0"] = wide[
        ["ef2full_seed0_target_rank", "boltz2_seed0_target_rank"]
    ].mean(axis=1)
    wide["consensus_min_seed0"] = wide[
        ["ef2full_seed0_target_rank", "boltz2_seed0_target_rank"]
    ].min(axis=1)
    scorers = [
        "ef2full_seed0",
        "boltz2_seed0",
        "consensus_mean_seed0",
        "consensus_min_seed0",
        "ef2full_best5",
        "boltz2_best5",
    ]
    return wide, scorers


def endpoint_frame(frame, endpoint):
    column, positive, negative = ENDPOINTS[endpoint]
    selected = frame[frame[column].isin([positive, negative])].copy()
    selected["label"] = selected[column].eq(positive).astype(int)
    return selected


def score_for_analysis(frame, scorer):
    rank_column = scorer + "_target_rank"
    return frame[rank_column] if rank_column in frame.columns else frame[scorer]


def analyze(frame, scorers, repeats, random_seed):
    per_target_rows = []
    pooled_rows = []
    rng = np.random.default_rng(random_seed)
    for endpoint in ENDPOINTS:
        endpoint_data = endpoint_frame(frame, endpoint)
        for scorer in scorers:
            scores = score_for_analysis(endpoint_data, scorer)
            pooled = binary_metrics(endpoint_data["label"], scores)
            pooled.update({"endpoint": endpoint, "scorer": scorer})
            pooled_rows.append(pooled)
            for target, target_frame in endpoint_data.groupby("target", sort=True):
                target_scores = score_for_analysis(target_frame, scorer)
                metrics = binary_metrics(target_frame["label"], target_scores)
                precision = tie_adjusted_precision_at_k(
                    target_frame["label"], target_scores, 20
                )
                per_target_rows.append(
                    {
                        "endpoint": endpoint,
                        "scorer": scorer,
                        "target": target,
                        **metrics,
                        "precision_at_20_tie_adjusted": precision["precision"],
                        "top20_k_effective": precision["k_effective"],
                        "top20_cutoff_tie_count": precision.get("cutoff_tie_count"),
                    }
                )

    per_target = pd.DataFrame(per_target_rows)
    pooled = pd.DataFrame(pooled_rows)
    macro = summarize_macro(per_target, repeats, rng)
    non_overlap = per_target[~per_target["target"].isin(COMPETITION_OVERLAP_TARGETS)]
    macro_non_overlap = summarize_macro(non_overlap, repeats, rng)
    paired = []
    for endpoint in ENDPOINTS:
        for left, right in PAIRED_COMPARISONS:
            row = {"endpoint": endpoint, "left": left, "right": right}
            for metric in ("auroc", "average_precision", "precision_at_20_tie_adjusted"):
                row[metric] = paired_target_bootstrap(
                    per_target, endpoint, left, right, metric, repeats, rng
                )
            paired.append(row)
    return per_target, pooled, macro, macro_non_overlap, paired


def operational_analysis(frame, scorers):
    rows = []
    for endpoint, (column, positive, negative) in ENDPOINTS.items():
        for scorer in scorers:
            for target, group in frame.groupby("target", sort=True):
                labels = group[column].map({positive: 1.0, negative: 0.0})
                metrics = operational_top_k(labels, score_for_analysis(group, scorer), 20)
                rows.append({"endpoint": endpoint, "scorer": scorer, "target": target, **metrics})
    return pd.DataFrame(rows)


def predictor_agreement(frame):
    rows = []
    for target, group in frame.groupby("target", sort=True):
        ef_rank = group["ef2full_seed0"].rank(method="average")
        boltz_rank = group["boltz2_seed0"].rank(method="average")
        correlation = float(ef_rank.corr(boltz_rank))
        stable = group.sort_values("uuid")
        ef_top = set(stable.nlargest(min(20, len(stable)), "ef2full_seed0")["uuid"])
        boltz_top = set(stable.nlargest(min(20, len(stable)), "boltz2_seed0")["uuid"])
        union = ef_top | boltz_top
        rows.append(
            {
                "target": target,
                "n": len(group),
                "spearman_seed0": correlation,
                "top20_jaccard_stable_tiebreak": len(ef_top & boltz_top) / len(union),
                "top20_overlap": len(ef_top & boltz_top),
            }
        )
    return pd.DataFrame(rows)


def render_report(source, frame, pooled, macro, macro_non_overlap, paired, agreement, operational):
    primary = [item for item in macro if item["endpoint"] == "vendor_concordant"]
    primary.sort(
        key=lambda item: (
            item["precision_at_20_tie_adjusted"]["mean"] or -1,
            item["average_precision"]["mean"] or -1,
        ),
        reverse=True,
    )
    lines = [
        "# One-seed screen benchmark audit",
        "",
        "This is a descriptive evaluation, not a fitted model or a transferable cutoff. "
        "Benchmark sequences were not used as generator inputs.",
        "",
        "## Data and endpoint",
        "",
        f"- Source: `Anthropic/claude-protein-binder-design` at `{REVISION}`.",
        f"- Analysis: {len(frame):,} human/synthetic-target designs across {frame['target'].nunique()} targets, "
        "from the 1,440-design source. BHRF1, Nipah-G, Cas9 and MBP are excluded from this initial scope.",
        "- Primary endpoint: only vendor-concordant calls (`both_bind` versus `neither_bind`).",
        "- Sensitivity endpoints: Adaptyv binder/non-binder and Twist binder/non-binder; "
        "unknown, untested, inconclusive and failed-expression states are excluded, not relabeled negative.",
        "- Scores are evaluated within target. The source explicitly says raw confidence is not comparable "
        "across targets, stoichiometries, or predictors.",
        "- `seed0` represents the one-seed policy. `best5` is reported only as an optimistic reference.",
        "",
        "## Vendor-concordant results among evaluable designs",
        "",
        "These metrics remove unknown/discordant labels before ranking; they describe an evaluable subset "
        "and must not be read as the expected precision of an actual prospective shortlist.",
        "",
        "| Scorer | AUROC (95% target bootstrap CI) | Average precision (95% CI) | Conditional precision@20 (95% CI) |",
        "|---|---:|---:|---:|",
    ]

    def format_metric(item):
        mean = item["mean"]
        low, high = item["ci95"]
        if mean is None:
            return "NA"
        return f"{mean:.3f} ({low:.3f}–{high:.3f})"

    for row in primary:
        lines.append(
            "| {scorer} | {auroc} | {ap} | {p20} |".format(
                scorer=row["scorer"],
                auroc=format_metric(row["auroc"]),
                ap=format_metric(row["average_precision"]),
                p20=format_metric(row["precision_at_20_tie_adjusted"]),
            )
        )
    primary_non_overlap = [
        item for item in macro_non_overlap if item["endpoint"] == "vendor_concordant"
    ]
    primary_non_overlap.sort(
        key=lambda item: item["precision_at_20_tie_adjusted"]["mean"] or -1,
        reverse=True,
    )
    lines.extend(
        [
            "",
            "## Transfer sensitivity: competition-overlap targets excluded",
            "",
            "IL-7Rα, EGFR, and TNFα are removed here before comparing methods; this reduces same-target "
            "policy selection but does not resolve unknown model-training overlap.",
            "",
            "| Scorer | Average precision (95% CI) | Conditional precision@20 (95% CI) |",
            "|---|---:|---:|",
        ]
    )
    for row in primary_non_overlap:
        lines.append(
            "| {scorer} | {ap} | {p20} |".format(
                scorer=row["scorer"],
                ap=format_metric(row["average_precision"]),
                p20=format_metric(row["precision_at_20_tie_adjusted"]),
            )
        )

    primary_paired = [item for item in paired if item["endpoint"] == "vendor_concordant"]
    lines.extend(
        [
            "",
            "## Paired target-level differences",
            "",
            "Positive values favor the method on the left. A 95% interval spanning zero is not evidence "
            "of a reliable improvement across targets.",
            "",
            "| Comparison | Δ average precision (95% CI) | Δ conditional precision@20 (95% CI) |",
            "|---|---:|---:|",
        ]
    )

    def format_difference(item):
        mean = item["mean_difference"]
        low, high = item["ci95"]
        if mean is None:
            return "NA"
        return f"{mean:+.3f} ({low:+.3f}–{high:+.3f})"

    for row in primary_paired:
        lines.append(
            "| {left} − {right} | {ap} | {p20} |".format(
                left=row["left"],
                right=row["right"],
                ap=format_difference(row["average_precision"]),
                p20=format_difference(row["precision_at_20_tie_adjusted"]),
            )
        )
    operational_primary = operational[operational["endpoint"] == "vendor_concordant"]
    operational_macro = operational_primary.groupby("scorer", sort=True)[
        ["known_fraction", "observed_positive_fraction", "possible_positive_upper_fraction"]
    ].mean()
    lines.extend(
        [
            "",
            "## Prospective-style top-20 accounting",
            "",
            "Rank all designs first, then reveal vendor-concordant outcomes. The lower fraction counts "
            "confirmed concordant binders; the upper fraction additionally treats every discordant or "
            "unmeasured selection as a hypothetical positive. These are descriptive bounds, not confidence "
            "intervals. Target averages include two GDF-8 targets with no concordant vendor data.",
            "",
            "| Scorer | Mean known outcome fraction | Confirmed positive fraction | Possible upper fraction |",
            "|---|---:|---:|---:|",
        ]
    )
    for scorer, row in operational_macro.iterrows():
        lines.append(
            f"| {scorer} | {row['known_fraction']:.3f} | {row['observed_positive_fraction']:.3f} "
            f"| {row['possible_positive_upper_fraction']:.3f} |"
        )
    concordant = endpoint_frame(frame, "vendor_concordant")
    lines.extend(
        [
            "",
            f"Primary endpoint rows: {len(concordant):,} "
            f"({int(concordant['label'].sum())} positive, {int((1-concordant['label']).sum())} negative).",
            "",
            "## Predictor agreement",
            "",
            f"Across targets, mean seed-0 rank correlation was {agreement['spearman_seed0'].mean():.3f}; "
            f"mean top-20 Jaccard overlap was {agreement['top20_jaccard_stable_tiebreak'].mean():.3f}. "
            "The top-20 overlap uses UUID as a stable tie break and is descriptive only.",
            "",
            "## Interpretation limits",
            "",
            "- The source designs were preselected by earlier design pipelines, so prevalence and enrichment "
            "do not represent arbitrary generated candidates.",
            "- Best-of-five scores are optimistic relative to a one-seed run.",
            "- The benchmark ESMFold2-full version/settings differ from our local ESMFold2 adapter. "
            "Boltz-2.2.1 is a closer protocol match, but construct and MSA details still matter.",
            "- Target-grouped intervals quantify target-to-target variation in this dataset; they do not prove "
            "independence from model training data or future competition targets.",
            "- The Adaptyv IL-7 positive control expressed but did not bind in its IL-7Rα experiment; "
            "interpret that target's assay results with care.",
            "- No threshold, binding probability, affinity, selectivity, expression, or functional claim is inferred.",
            "",
            "Files `metrics.json`, `per-target.csv`, `per-target-operational.csv`, "
            "`pooled-within-target-rank.csv`, and `predictor-agreement.csv` preserve the detailed results and source hashes.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--bootstrap-repeats", type=int, default=2000)
    parser.add_argument("--random-seed", type=int, default=20261102)
    args = parser.parse_args()
    if args.bootstrap_repeats < 100:
        raise ValueError("At least 100 bootstrap repeats are required")

    source = validate_inputs(args.data_root)
    frame, scorers = load_scores(args.data_root)
    source_designs = len(frame)
    source_targets = frame["target"].nunique()
    if not set(EXCLUDED_NONHUMAN_TARGETS).issubset(set(frame["target"])):
        raise ValueError("Expected excluded targets are missing from source")
    frame = frame[~frame["target"].isin(EXCLUDED_NONHUMAN_TARGETS)].copy()
    per_target, pooled, macro, macro_non_overlap, paired = analyze(
        frame, scorers, args.bootstrap_repeats, args.random_seed
    )
    agreement = predictor_agreement(frame)
    operational = operational_analysis(frame, scorers)

    args.output_dir.mkdir(parents=True, exist_ok=False)
    per_target.to_csv(args.output_dir / "per-target.csv", index=False)
    pooled.to_csv(args.output_dir / "pooled-within-target-rank.csv", index=False)
    agreement.to_csv(args.output_dir / "predictor-agreement.csv", index=False)
    operational.to_csv(args.output_dir / "per-target-operational.csv", index=False)
    result = {
        "analysis": "descriptive_no_training_no_threshold_tuning",
        "benchmark_revision": REVISION,
        "source_files": source,
        "input_counts": {
            "source_designs": source_designs,
            "source_targets": source_targets,
            "analysis_designs": len(frame),
            "analysis_targets": frame["target"].nunique(),
            "excluded_nonhuman_targets": list(EXCLUDED_NONHUMAN_TARGETS),
            "models": list(MODELS),
            "seeds_per_design_model": 5,
        },
        "endpoints": {
            name: {
                "source_column": values[0],
                "positive": values[1],
                "negative": values[2],
                "excluded_are_not_negatives": True,
            }
            for name, values in ENDPOINTS.items()
        },
        "score_policy": {
            "primary_runtime_policy": "seed0",
            "optimistic_reference_only": "best5",
            "best5_reproduces_published_design_summary": True,
            "cross_target_comparison": "within_target_percentile_rank",
            "consensus_mean": "mean of two within-target percentile ranks",
            "consensus_min": "minimum of two within-target percentile ranks",
            "conditional_metrics": "unknown and discordant calls excluded before selection",
            "operational_top20": "rank all designs before outcomes; report unresolved bounds",
        },
        "macro_target_bootstrap": macro,
        "competition_overlap_targets": list(COMPETITION_OVERLAP_TARGETS),
        "macro_target_bootstrap_excluding_competition_overlap": macro_non_overlap,
        "paired_target_bootstrap_differences": paired,
    }
    write_json(args.output_dir / "metrics.json", result)
    (args.output_dir / "report.md").write_text(
        render_report(
            source, frame, pooled, macro, macro_non_overlap, paired, agreement, operational
        )
    )
    print(json.dumps({"status": "ok", "output_dir": str(args.output_dir), "designs": len(frame)}))


if __name__ == "__main__":
    main()
