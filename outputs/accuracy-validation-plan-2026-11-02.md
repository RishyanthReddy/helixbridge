# Accuracy validation and fallback policy

User steering November 2: continue after failures and evaluate current alternatives. This supplements the ordered TODO; it does not mark any later phase complete.

## What we will measure

The useful endpoint is enrichment for experimentally supported binding among the few candidates we can submit. Official-screen admission, predicted complex confidence, expression, and experimental binding are separate endpoints. We cannot establish a universally “best” pipeline from one generated design or from author benchmark claims.

The first real control already demonstrates the issue: natural IL-7/IL-7Rα scored approximately 0.78 ipTM with ESMFold2 but 0.28 with Boltz-2, with zero Boltz ipSAE at our local 10/10 cutoffs. Both adapters executed and validated their structures/PAE. This does not validate a hard consensus filter: it could discard a known interaction. Diagnose protocol/construct sensitivity and measure predictive performance before promoting either model's cutoff into a binding rule.

## Public experimental validation data found

[Anthropic/claude-protein-binder-design](https://huggingface.co/datasets/Anthropic/claude-protein-binder-design), pinned revision `9e1b81696da46835e9e9cde9a3da976e0abc92ab`, was last modified August 18, 2026 according to the HF API reviewed November 2. It contains 1,440 designs for 16 targets, two vendors' assays, ten predictors, and provenance. It is a recent public validation resource, not a newly released November model. Its tables and documentation have been fetched for evaluation only; no model has been trained on them.

The release's [in-silico documentation](https://huggingface.co/datasets/Anthropic/claude-protein-binder-design/blob/9e1b81696da46835e9e9cde9a3da976e0abc92ab/data/docs/INSILICO.md) explains that summary scores select the best of five seeds. The per-seed table is needed to assess a one-seed policy. Its ESMFold2 fast mode uses single sequences, while full mode uses target MSA; neither mode name alone establishes equivalence to our protocol. Chain order also differs across predictors. Match software, weights, construct, stoichiometry, input order, MSA, sampling settings and score definitions before transferring thresholds.

The release's [wet-lab documentation](https://huggingface.co/datasets/Anthropic/claude-protein-binder-design/blob/9e1b81696da46835e9e9cde9a3da976e0abc92ab/data/docs/WETLAB.md) and data notes must be read alongside labels. The combined final call includes Claude's adjudication, so primary vendor results and QC should be the main measured endpoints, with the adjudicated call as a sensitivity analysis. Vendor assay formats differ, including Fc fusion/avidity. Inconclusive, not-tested, failed-expression and censored measurements are not interchangeable negative labels; incompatible affinities must not be pooled without qualification.

[Proteinbase](https://proteinbase.com/competitions) and [BenchBB](https://www.adaptyvbio.com/blog/benchbb) are additional primary sources. BenchBB is a benchmark specification; it is not by itself a completed labeled dataset or evidence that a specific model wins.

## Phase 7 acceptance plan

1. Start with public non-pathogen benchmark targets. Record source revision, assay/QC definitions and missingness. Keep benchmark sequences outside generator inputs; competition-target experimentally positive binders must not become optimization starting points.
2. Separate measured binding among evaluable constructs from end-to-end expression-and-binding yield. Preserve unknown, censored and conflicting results. Check vendor-specific results and agreement separately.
3. Group related sequences, shared backbones and campaign families before splitting. Hold out whole targets as well as families where data support it. Tune on training/development groups only. Public model training overlap may be unknown; these splits do not prove independence from model training.
4. Compare ESMFold2 and Boltz separately, then their agreement/disagreement and pose consistency. Evaluate any added predictor under the same inputs and compute budget. Do not assume adding more models improves accuracy.
5. Report precision at the planned shortlist size, precision-recall performance relative to prevalence, per-target results and uncertainty intervals based on grouped resampling. If a probabilistic ranker is trained, assess calibration on held-out data. Affinity ranking is a separate analysis restricted to compatible measured values.
6. Test an explicit abstention/review policy for disagreements. Retain raw bidirectional ipSAE; the official aggregation remains unknown. Dataset `ipsae_min`, our directional minimum, and official admission must not be silently equated.
7. Promote a method only for demonstrated improvement on held-out experimental endpoints at acceptable L40S cost. Otherwise retain it as a diagnostic or defer it.

## When an approach fails

Preserve the failed run; distinguish execution, input mapping, generation, refolding, and experimental-prediction failures. Check current primary releases and choose the next bounded test based on the diagnosed failure. Change one interpretable setting at a time where possible, retain identical common evaluations, and record the resulting compute cost. Large campaigns follow successful rehearsals and a measured selection policy.

Current example: three small BC2 campaigns produced no accepted designs. The user-authorized RFD4 alternative passed its supplied-example and IL-7Rα generation controls on the L40S. Two independently refolded RFD4 rehearsals remain on hold because of pose/composition/clash concerns. Other new algorithms remain candidates for later bounded comparisons, not automatic additions.

## First descriptive result and provisional policy

CPU job **1079616** analyzed the 1,080 designs on 12 human/synthetic targets, using pinned per-seed prediction rows. For the primary endpoint, 219 were called binders by both vendors and 565 non-binders by both; other outcomes were not relabeled as negatives. Each target was ranked separately. A first audit incorrectly called the top 20 among only evaluable designs a prospective precision; the revised report labels it conditional and additionally ranks all designs before revealing outcomes, reporting observed positives and unresolved bounds.

The fixed two-model rank combinations had numerically higher conditional top-20 precision than individual one-seed models, but paired target-bootstrap intervals included zero. Excluding IL-7Rα, EGFR and TNFα did not remove the uncertainty. Source designs were preselected, the local ESMFold2 settings differ, and the dataset's Adaptyv IL-7 control did not bind in that experiment. The audit is exploratory; it does not establish a general winner, calibrated cutoff or held-out performance.

Until further validation, keep both models' directional scores and structural checks visible. Treat disagreement as a review flag rather than an automatic failure or promotion. Do not transfer the dataset's raw score cutoffs to the organizer screen. Full tables, assumptions and source hashes: `execution-evidence/screen-benchmark-audit-v4/`. Benchmark sequences were not used as optimization inputs.

## Grouped follow-up

The subsequent local validation groups shared backbone/ancestor IDs and conservative
sequence-similarity links before taking one score-blind representative per target/group.
This leaves 674 representatives from 1,080 designs. A ranking rule is selected using
other targets only, then tested on the held target. Any shared group is purged across
the split (none crossed targets in this subset). Ten targets have the primary endpoint.
The selected rule's average confirmed-positive lower fraction at top 20 equals the
ESMFold2 baseline; the paired target-bootstrap 95% interval is −0.02 to +0.02.
No hard consensus rule is promoted. Details and source hashes are in
`execution-evidence/grouped-screen-validation-v2/`. Separate Adaptyv and Twist
held-target checks also showed no reliable consensus gain. This is internal resampling after
prior analyst inspection, not a pristine external validation or calibrated probability.
