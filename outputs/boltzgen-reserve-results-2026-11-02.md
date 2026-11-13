# BoltzGen reserve: executed and held

One IL7Ra patch139 design completed native generation, SolubleMPNN sequence
design, full-target ESMFold2 and Boltz refolding, common scoring, independent
geometry/context review and limited public sequence comparison. Engineering
qualification passed; this candidate is held for poor interface evidence. One
case cannot establish comparative generator accuracy.

| Measure | ESMFold2 | Boltz |
|---|---:|---:|
| ipTM | 0.375 | 0.363 |
| Minimum directional ipSAE | 0 | 0 |
| Target-aligned generator-to-refold binder RMSD | 62.29 Å | 77.59 Å |
| Binder-only self-fit RMSD | 0.440 Å | 0.480 Å |
| Requested hotspots contacted in refold | 0/10 | 0/10 |
| Heavy-atom pairs below 2 Å | 1 | 1 |

Cross-refold binder RMSD after shared target-core alignment is 19.27 Å. Intrinsic
binder shape is preserved, but the intended interface is not. Refold contacts
include positions outside the generation reference and the unresolved
N-terminal assay-processing region. Generated target CA self-fit RMSD to input
is 0.108 Å; near-exact parser input preservation is a different measurement.

The native binder backbone contacts five requested hotspots. SolubleMPNN does
not pack sidechains: native CIF/NPZ remain untouched, while a labeled
backbone-only derivative removes 240 unmodeled binder sidechain atoms before
geometry analysis. Target atoms remain. Its native contact counts therefore
cannot be directly compared with full-sidechain RFD4/refold counts. Boltz-family
generation/refolding share lineage; ESM evidence remains separate.

The 60-aa sequence has no cysteine or N-glycosylation sequon, DE fraction 0.117,
KR fraction 0.217 and an N-terminal DP motif. These are descriptive flags, not
expression/aggregation/affinity measurements. The sequence differs from the
existing pool; the 1,684-row public corpus produced no exact or >90%-contiguous
overlap flags. That is not global novelty certification.

## Configuration and evidence

Code `HannesStark/boltzgen` is pinned at
`6472b44e8072187e6eaa51271ae6838245206013` (package 0.3.2); adherence weights at HF
`c1be29e1f82ffcc72264f64b993c43fb4e0d17f0`; chemical dataset at
`c3d36fd276e9caf098c75d4113c6d5eb320b1a4c`; original SolubleMPNN 48_020 weights.
Required assets were downloaded anonymously and checked against upstream hashes.
A fresh source commit does not mean new model weights.

Separate Python 3.12/torch 2.11.0+cu130 environment; existing environments were
not modified. Native configs retain 500 design steps, three recycling steps,
one design/sample, seed 301, sequence temperature 0.1, optional kernels disabled.
Resolved configs are saved. Ten hotspots were explicitly renumbered to the
195-residue reference; CPU parsing checked all 1,601 provided target atoms,
sequence, design mask and binding annotations before GPU use.

Common refolds used the full target 1–236, seed 0, target MSA only, no template
or binder MSA. Exact organizer-screen equivalence remains unresolved. No
training or extra generation seed sweep occurred.

CPU jobs 1104810/1104816/1104820/1104823 and GPU jobs
1104819/1104821/1104822 completed with exit code zero. Generation plus sequence
design used 186 allocated GPU-seconds; refolds used 73 and 143. Reserve total:
**402 seconds (6.70 GPU-minutes)**. Peak reserved VRAM: generation 3,600 MiB,
sequence design 168 MiB, ESM 26,316 MiB, Boltz 4,478 MiB. These are workload
measurements, not general target-size guarantees.

Combined with the six-case RFD4 pilot: **2,425 GPU-seconds (40.42 minutes), at
most two simultaneous one-L40S jobs**, below the original 90-minute cap and the
reserve's additional 30-minute cap. Unused budget does not justify more
low-evidence designs.

Review JSON and CSV reproduce byte-for-byte under a different Python hash seed;
the package checks 75 source hashes. Raw predictions, native files, resolved
configs, task states, logs and scheduler records are saved locally under
`execution-evidence/`. See `boltzgen-reserve-review-2026-11-02-v1/`.

Decision: retain BoltzGen as an operational reserve, hold this candidate, and
do not claim improved accuracy or launch a larger campaign from one case.
Existing seed43/101/103/105 priorities are unchanged. No submission entry or
experimentally validated binder is claimed.
