# Predeclared seed101 repair experiment

Freeze this protocol before generation or examining any variant scores. Parent:
our own de novo RFD4 candidate `il7ra-rfd4-6b3ca40a31bb`, 60 aa. This is
sequence optimization of our own computational design, with no experimentally
known binder sequence supplied. Its raw generator complex is the sole design
backbone. Existing target/reference and full-target evaluator limitations remain.

The parent contains Cys25 and overlapping N-glycosylation motifs NLS18 and
NIS29. These are sequence features, not proof of incorrect folding, glycan
occupancy or failed expression. A comparison can establish their removal while
preserving predicted complex behavior; only experiments establish actual binding
and developability.

Two controlled arms, native SolubleMPNN at temperature0.1, seed401, 16 samples
per arm, one generated sequence per sample:

1. **Cys-only:** redesign binder position25, prohibit C there, keep all other
   binder residues and all target residues fixed.
2. **Triple:** redesign binder positions18,25,29; prohibit N at18 and29 and C
   at25, keep all other binder residues and all target residues fixed.

Use the pinned upstream SolubleMPNN weights, unmodified native implementation and
explicit PDB chain/position mapping checked against coordinates and sequences.
Preserve every sequence and native confidence/statistics; exact duplicates are
collapsed only for downstream refolding, never deleted from records. Exclude any
candidate that violates its allowed positions, target identity or canonical
60-aa format. For triple, additionally require no C or N-X-[S/T] motif anywhere
in the binder. Rank unique sequences **within each arm** by native MPNN
overall_confidence, highest first, then sequence lexicographically; select at
most the first two unique format-valid sequences per arm for common evaluation.
If an arm has fewer than two unique outputs, record the shortfall rather than
silently resampling. MPNN confidence is used only to choose among samples; it is
not interpreted as measured affinity or the official screen score.

For every selected variant run the same ESMFold2 and Boltz full-target1–236,
target-MSA-only, no-template, seed0, one-sample protocol used on the parent.
Retain directional ipSAE values separately, both full target alignment and shared
reference core37–231 alignment, and independent geometry/context checks.

A **provisional repaired research follow-up** must pass all checks below, as a
predeclared consistency screen, not a validated experimental threshold:

- The appropriate sequence features are removed and changes are restricted to
  the arm's allowed sites; no pre-existing candidate is exactly duplicated.
- Directional-minimum ipSAE is at least0.82918 for ESM and0.76850 for Boltz,
  i.e. within0.03 of each parent's seed0 score (0.85918 and0.79850 respectively).
- Each predictor's target-core-aligned binder CA RMSD to the parent's generated
  pose ≤2.5 Å, and the predictor-to-predictor binder RMSD using the same core
  ≤3.0 Å. Each model's target-contact Jaccard vs the same-model parent ≥0.70.
- Zero interchain heavy-atom pairs below2 Å in both predictions.

If one or more variants pass seed0, prioritize the triple-arm variant with the
highest ESM minimum directional ipSAE; break ties by Boltz minimum ipSAE then
lexicographic sequence. If no triple passes, the same ordering may prioritize a
Cys-only variant. Run the selected variant at prediction seeds1 and2 in both
models, compare matched-seed results to the existing parent robustness runs, and
report each value and pose separately. Do not describe reduced motif counts as
measured expression, or increased confidence as measured affinity. No submission
promotion follows from this experiment alone.

The decisive primary sources and controls are the native LigandMPNN/SolubleMPNN
code at github.com/dauparas/LigandMPNN, parent audited candidate/reviews, and
official IL7Ra full-target specification. Exact official ESMFold2/ipSAE settings,
assay processing and glycans remain unknown. Store all attempts, including install
failures and candidates that fail geometry or confidence gates.
