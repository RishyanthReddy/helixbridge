# Lead101 constrained repair results

The predeclared experiment produced a provisional repaired research follow-up,
`lead101repair-766ca9c35448`. It removes the parent's Cys25 and both N-X-S/T
sequence motifs at18/29 through changes restricted to the three declared sites.
This establishes sequence-feature removal with preserved computational
consistency; expression, stability, glycan occupancy and binding remain unmeasured.

Both repair arms generated16 samples but only one unique sequence per arm.
Both unique variants passed every frozen seed0 score/pose/contact/clash gate.
The protocol prioritized the passing triple arm for seeds1/2 in both models.
There was no resampling, threshold relaxation or retrospective winner selection.

| Predictor | Seed | Parent min directional ipSAE | Triple repair | Change |
|---|---:|---:|---:|---:|
| ESMFold2 | 0 | 0.859180 | 0.851113 | −0.008067 |
| ESMFold2 | 1 | 0.857069 | 0.850717 | −0.006352 |
| ESMFold2 | 2 | 0.860838 | 0.857800 | −0.003038 |
| Boltz | 0 | 0.798500 | 0.803643 | +0.005143 |
| Boltz | 1 | 0.772264 | 0.784712 | +0.012448 |
| Boltz | 2 | 0.767729 | 0.780077 | +0.012348 |

The displayed parent seed0 values were frozen in the protocol to five decimal
places. Raw directional values remain in the original metrics. These confidence
changes are descriptive and are not measured affinity gains.

For the triple variant, target-core-aligned binder RMSDs to the original generated
parent pose span0.89–1.37Å across the six predictions; ESM/Boltz agreement spans
0.73–1.22Å. Same-model matched-parent target-contact Jaccards span0.90–1.00.
All six predictions have zero interchain heavy-atom pairs below2Å.
Full-target alignments are retained separately: Boltz terminal-region variation
changes the matched-parent binder RMSD up to3.01Å under whole-target fitting,
despite preserved core pose. Do not silently treat whole-target and core fitting
as equivalent.

The limited overlay of three observed3DI3 disaccharide fragments found no
<2Å overlap in the eight repaired seed0/robustness poses. This is one rigid,
incomplete experimental fragment configuration, not a glycan ensemble or proof
of compatibility. Reference T66 differs from canonical I66. Organizer assay
processing and glycan occupancy remain unknown.

All comparisons preserve full target1–236, target-only MSA, no templates,
one sample, scientific adapter hashes and pinned models. Seeds1/2 differ only
in prediction seed from the repaired seed0 request. The reviewer checked input
hashes, output artifact hashes, exact chain sequences, model/MSA identity,
finite296×296 PAE and ESM raw/JSON PAE equality; alignments agree between
Bio.PDB and independent SVD. The repository's35 unittest tests passed.

Generation and prediction allocations consumed717 GPU-seconds (11.95minutes),
maximum concurrency two, including the89-second failed bookkeeping job.
Jobs1104845/46 generated;1104847 evaluated both seed0 ESM requests;1104848
completed Cys-only Boltz then failed an orchestration metadata check;1104849
evaluated only the remaining triple Boltz request;1104850/51 completed the
additional-seed ESM/Boltz requests. Failures and successful outputs are retained.
Peak model-reported reserved memory was26316MiB for ESM and4478MiB for Boltz;
the latter reflects adapter-process accounting and should not be taken as the
separate native Boltz subprocess's true peak GPU memory.

Evidence:
- `lead101-repair-protocol-2026-11-02.md`: frozen plan and thresholds.
- `lead101-repair-selection-2026-11-02-v1.json`: all32 samples and selection.
- `lead101-repair-refolds-2026-11-02-v1/seed0-review.json`: all seed0 gates.
- `lead101-repair-robustness-2026-11-02-v1/matched-seed-review.json`: matched
  parent/repair values, geometry and source hashes.
- `lead101-repair-glycan-fragments-2026-11-02.json`: limited context sensitivity.

The triple variant joins research follow-ups with explicit qualifications;
seed43 remains the cleaner existing baseline. No official-format candidate or
submission shortlist was promoted. Broader experimental accuracy validation,
diversity/novelty review and organizer-only assay/screen details remain open.
