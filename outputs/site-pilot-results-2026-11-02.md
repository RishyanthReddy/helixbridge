# Executed IL7Ra site-diversity experiment

All six planned designs completed generation, full-target ESMFold2 and Boltz
refolding, common scoring, independent pose checks and target-context review.
None earned the predeclared additional robustness run. This is a completed
experiment with held candidates, not a demonstrated failure to bind in the lab.

## What was tested

The original RFD4-Proteina target-only recipe was retained: a new 60-residue
binder, target residues 37–231, thinking_high, ten conditioning hotspots per arm,
generation seeds 201 and 202. The control reproduced the existing region;
patch139 and patch72 explored alternatives. Evaluation used the complete official
sequence interval 1–236, target MSA only, no binder MSA or templates, prediction
seed 0 and the previously pinned adapters/checkpoints. Source/reference and
assay-construct limitations were retained.

| Design | ESM ipTM | Boltz ipTM | ESM / Boltz minimum directional ipSAE | Generator-to-refold binder shift, ESM / Boltz (Å) | Cross-refold binder RMSD (Å) |
|---|---:|---:|---:|---:|---:|
| Control 201 | 0.863 | 0.519 | 0.480 / 0.012 | 0.61 / 7.21 | 7.35 |
| Control 202 | 0.268 | 0.272 | 0 / 0 | 19.3 / 18.6 | 8.86 |
| Patch139 201 | 0.229 | 0.350 | 0 / 0 | 57.7 / 58.9 | 3.08 |
| Patch139 202 | 0.351 | 0.770 | 0 / 0.219 | 59.9 / 61.6 | 18.39 |
| Patch72 201 | 0.437 | 0.664 | 0 / 0.112 | 30.9 / 27.5 | 5.82 |
| Patch72 202 | 0.378 | 0.578 | 0 / 0.053 | 31.5 / 32.8 | 4.18 |

Target-aligned comparisons use the same reference core 37–231. Scores remain
separate model outputs, not calibrated probabilities or affinities. Boltz's
relatively high ipTM for Patch139 202 does not override the lost intended pose,
ESM disagreement or geometric flags.

## Why we held the designs

Native generated structures contacted 8–10 of the 10 requested hotspots. Thus,
the adapter did condition on the intended sites. Independent refolds of the
alternative arms contacted none of those requested hotspots. Their resulting
interfaces also overlapped existing lead interfaces, rather than establishing a
consistent new binding region.

Patch139 retained its intrinsic binder shape: binder-only self-fit RMSD was
about 0.47–0.92 Å, despite roughly 58–62 Å target-aligned pose displacement.
That points to an interface/pose problem in these predictions. Patch72 also
changed intrinsic binder shape, with self-fit RMSDs about 2.4–4.4 Å. These
diagnostics do not establish experimental nonbinding or a general generator
failure rate from two seeds per arm.

The additional-run rule required a genuinely different predicted contact region
(maximum Jaccard overlap <0.30 against the four existing leads in both models),
zero heavy-atom pairs below 2 Å in both refolds, and cross-refold binder RMSD
≤3 Å. No case passed. The thresholds were not relaxed after observing results.
All six are format-valid and distinct; the limited public comparison found no
exact or >90%-contiguous overlap flags across 1,684 public rows. That is not a
global novelty certificate. All six remain rehearsal-only.

## Verification and resource use

Eight one-L40S GPU jobs completed with exit code zero: 1104140, 1104141,
1104801 and 1104803–1104807. They consumed **2,023 allocated GPU-seconds
(33.72 minutes)**, with at most two simultaneous GPUs. The implementation gate
passed before the remaining four designs were released. Staged ESM used the
unchanged scientific request and model adapter; it solved shared-filesystem
startup cost without changing the scientific protocol.

The independent final audit checked 1,236 source hashes, 63 output hashes,
12 score rows, six cases, an empty submission shortlist and rejection of a
changed-artifact negative control. Numerical review JSON and CSV outputs
reproduced byte-for-byte under a different Python hash seed. Raw alignment logs
contain path/timing differences and are not claimed byte-identical.

## Resulting decision

Keep seed43 as the cleaner existing research baseline and seed101/103/105 as
the previously identified follow-ups with their existing caveats. These six new
designs add no finalist. Stop extending this RFD4 site sweep. A separately
declared one-case BoltzGen reserve qualification follows within the original
resource cap; it does not alter this six-case comparison or prove the reserve
better. No design is promoted to an official entry by these computations.

Evidence: `site-pilot-review-2026-11-02-v1/review.json`,
`site-pilot-final-verification-2026-11-02.json`,
`site-pilot-intrinsic-shape-audit-2026-11-02.json` and
`site-pilot-gate-audit-2026-11-02.json`.
