# Recent alternatives for molecular modelling and binder analysis

Reviewed 13 November 2026 with Exa and TinyFish. The user's final recency requirement is a primary shortlist of releases or substantial updates within 14 October–13 November 2026. Launch dates, paper dates and code updates are distinguished below. This is research and a proposed qualification order. No new model was installed or run on our candidates during this review.

## 1. BioEmu2 — first candidate for an additional dynamics analysis

Microsoft Research's public preview was announced on 20 October 2026 by team members, including Frank Noé. Code and model weights are available under MIT terms. Its current repository supports multi-component molecular systems, equilibrium conformational sampling, structure prediction, time-lagged propagation, contact conditioning and steering. It exposes Python and CLI interfaces and exports topology CIF plus trajectory XTC files.

This extends the analysis capabilities available to our workflow. Mokda provides a graphical environment around modelling and simulation tools. BioEmu2 supplies a learned model for structure and dynamics that could be called from our own pipeline.

Hardware needs qualification. The current repository lists L40S among GPUs meeting the CUDA-extra architecture requirements and describes batch-size, precision and memory-saving controls. It explicitly says eligible GPUs beyond its tested list are not end-to-end verified. The HF model card says the smallest tested device was an 80 GB A100, while the current repository lists a broader tested set. Treat that as documentation inconsistency. Neither statement establishes memory fit or quality for our IL7Rα–minibinder workload on one 48 GB L40S. Context parallelism requires at least four GPUs, so that route is outside the earlier two-allocation operating limit unless separately authorized.

The model card excludes quantitative binding-affinity prediction and warns that sampled state frequencies are uncalibrated. An ensemble that retains an interface cannot be treated as proof of binding, a measured KD, or a calibrated binding probability. Compatibility with standard residues, engineered binder inputs and target-only MSA conventions must be checked at a pinned version.

Sources

- [Team lead's 20 October announcement](https://www.linkedin.com/posts/frank-noe-73bb4650_introducing-bioemu2-activity-7518238500098510848-gZJ4)
- [Repository and system requirements](https://github.com/microsoft/bioemu2)
- [Model card](https://huggingface.co/microsoft/bioemu2)
- [Speed and capacity controls](https://github.com/microsoft/bioemu2/blob/main/docs/speed-and-capacity.md)

## 2. Chaperone — recent protein-design orchestration framework

The preprint is dated 20 October 2026. The code is currently public. This date establishes the paper release, not necessarily the first public code release.

The repository describes interoperable design, sequence, prediction and analysis blocks, with Slurm orchestration, lineage tracking, chunking and caching. Listed blocks include RFdiffusion variants, ProteinMPNN, BoltzGen, ESMFold2, Boltz2, RF3, Protenix v2, Chai1 and interface/geometry metrics. Some block containers or weights need upstream downloads or access agreements.

Its role would be workflow integration and scaling. A framework's availability does not establish a more accurate binder classifier. Its paper reports token/GPU savings and a small-molecule binder campaign, which cannot be transferred to our IL7Rα minibinders. Our existing pipeline already has several orchestration functions, so adoption would require a specific demonstrated benefit rather than an immediate rewrite.

Sources

- [20 October preprint](https://pmc.ncbi.nlm.nih.gov/articles/PMC13738521/)
- [Repository](https://github.com/RosettaCommons/chaperone)

## 3. LocalFold — substantial November updates, requiring requalification

The GitHub commit API verifies 9 November 2026 updates including WebGL2 handling of Boltz2, Protenix-v2, Mol-1 and RoseTTAFold3, with further input-kind and default-seed corrections. This is an update to an existing project.

The current README describes browser-local folding, multi-chain inputs, confidence/PAE exports and optional ColabFold MSA retrieval. These are relevant to interactive inspection and portable prediction checks.

Our previous pinned AF2-Multimer backend test from 2 November did not meet its numerical-equivalence gate. That historical result applies to the tested backend/revision and does not resolve the current build. Requalify a new pinned backend and its exported confidence mapping before including its scores in candidate selection.

Sources

- [Current repository](https://github.com/sokrypton/localfold)
- [9 November multi-model update](https://github.com/sokrypton/localfold/commit/442a3c8aafc730e05a8450ce607f2f92314515eb)
- [9 November default-seed corrections](https://github.com/sokrypton/localfold/commit/5ea3d42c911949700401b54003cb28c557fcf2a6)
- [Our historical qualification](localfold-qualification-2026-11-02.md)

## Proposed order

First qualify BioEmu2 on fixed public diagnostic complexes, measuring actual resource use and checking outputs. Keep diagnostic controls separate from later held-out evaluation of any proposed ranking signal. Address the revised IL7Rα target input before attributing differences to a new method.

Revisit LocalFold only at a recorded new version and with explicit output/parity checks. Evaluate Chaperone if orchestration is limiting throughput or reproducibility. None of these sources establishes a blanket accuracy advantage over Mokda or a measured improvement for our candidates.

## Operational status

The user redirected the task from testing Mokda to researching recent alternatives. No Mokda installation or successful login was observed. A native-browser download attempt timed out. A subsequent filtered Downloads listing found no Mokda package or partial Chrome download. AsterFire/Mokda benefits application submission was already confirmed in the earlier browser task. Its activation and credits remain unverified.
