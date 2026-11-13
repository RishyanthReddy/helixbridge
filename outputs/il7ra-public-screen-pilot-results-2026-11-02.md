# Six public de novo controls: actual local-screen pilot

All twelve predictions completed and passed provenance/structure/PAE checks.
The pilot reveals high-confidence non-binders under our competition-style
input regime. It does not establish calibrated accuracy or a general model
winner: this is a deliberately balanced six-control sample from a previously
examined, preselected public release, with differing assay/model constructs.

| Control | Both vendor calls | ESM min directional ipSAE | Boltz min directional ipSAE |
|---|---|---:|---:|
| 01 | binder | 0.872 | 0.741 |
| 02 | binder | 0.833 | 0.813 |
| 03 | binder | 0.846 | 0.810 |
| 04 | non-binder | 0.844 | 0.846 |
| 05 | non-binder | 0.872 | 0.848 |
| 06 | non-binder | 0.605 | 0.381 |

Among the nine positive-negative pairings, the positive scored higher six
times with ESMFold2 and three with Boltz; neither had ties. These are descriptive
counts, not prospective precision, confidence intervals or population accuracy.
All twelve predictions have zero interchain heavy-atom pairs below2Å, so that
simple clash check does not distinguish the high-scoring non-binders04/05.
Their ipTM values are also high (ESM0.958/0.970, Boltz0.962/0.955).

We selected three vendor-concordant positives and three negatives by a fixed
UUID hash, with distinct conservative lineage/sequence families. Prediction
score columns were not read for selection. All six had reported expression at
both vendors; source vendor labels/sequences/titers were checked independently
against the pinned table. No threshold, consensus rule or ranker was fitted.
The controls remain evaluation-only and are never generator starting points or
submission candidates.

The canonical full target1–236, target-only MSA, seed0, one sample and original
scientific adapters/settings were retained. Model/MSA identities, input/output
hashes, raw directional score rows, exact predicted sequences, finite PAE and
ESM raw/JSON PAE equality were checked. ESM used the qualified byte-verified
node-local runtime. Both Slurm jobs succeeded:1104855 used303GPU-seconds,
1104856 used474, total777seconds (12.95minutes), maximum concurrency two.
New repair/control/pilot work totals1746GPU-seconds (29.1minutes), including
prior failures; the earlier site-pilot ledger remains separate and unchanged.

Source computational models used193-residue receptor37–229 with T66, while
our screen uses canonical1–236 with I66. Vendor antigen records carry an
extracellular21–239 reference annotation, not an exact measured reagent
sequence; Twist also uses bivalent Fc-fused designs. See
`il7ra-public-benchmark-context-2026-11-02.md` for primary-source details.

Implication: keep confidence and geometric consistency as computational
evidence, not measured affinity or a validated probability of binding. Our
repaired candidate remains a provisional research follow-up. Next, examine
construct/glycan sensitivity and broaden evaluation on fixed public controls
before proposing any new filtering rule. Exploratory diagnostics must not be
retrospectively advertised as a validated classifier. Organizer-only assay
details remain unresolved.

Evidence: `il7ra-public-screen-pilot-2026-11-02-v1/review.json`,
`predictions-vs-vendors.csv`, all raw outputs and Slurm accounting. Frozen plan:
`il7ra-public-screen-pilot-protocol-2026-11-02.md`.
