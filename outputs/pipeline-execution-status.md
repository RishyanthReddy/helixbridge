# Pipeline execution status

Updated November 2, 2026. Active goal: first reproducible IL-7Rα rehearsal on one L40S. The ordered [TODO](pipeline-plan-and-todo.md) is the source of task status.

## Verified foundation — Phases 1–3

- User-authorized Earth access works via `earth-hpc`. A separate scratch project was created at `/cfs/earth/scratch/mekalris/changjiang-2026`; existing projects were preserved.
- GPU preflight job **1079583** completed: one NVIDIA L40S, 46,068 MiB visible VRAM, driver 610.57.04, CUDA UMD 13.3, compute capability 8.9. This checks hardware, not model inference.
- All seven public target ranges, boundary amino acids and requested displayed isoforms were checked against UniProt. FASTA and source/sequence hashes are retained in `pipeline/data/targets/`.
- For 3DI3 chain B, DBREF and SIFTS agree on UniProt mapping. The usable reference has 193 mapped residues, lacks 43 positions from the declared 236-residue interval and has T at position 66 where current UniProt has I. The reference is explicitly restricted to rehearsal use. No coordinates or mutations were silently repaired.
- New local implementation lives in its own `pipeline/` Git repository. Source is recorded in local commit `ec3311f`; it has not been published. Upstream source trees were not modified.
- BC2 source pinned at **b6fb3ae15ab6a702f1156cffc11bcc3323c2fd06**. CPU installation **1079584** passed dependency/checkpoint self-check. CPU audit **1079585** hashed 27 checkpoint files; package freeze and hashes are copied into `execution-evidence/`.
- **18 tests passed locally and on Earth**, covering stale/missing/NaN/header-only outputs, input/output hash changes, exit codes, timeout, actual signal interruption, candidate duplicates/invalid sequences, rehearsal-export refusal, target endpoint validation and isoform validation. Bash syntax and staged whitespace checks passed.

These checks validate infrastructure, not binding or candidate quality. Official assay-construct details remain unresolved in the requirements record.

## Verified local screening pilot — Phase 4

- [Canonical Biohub ESMFold2](https://github.com/Biohub/esm) was located through TinyFish; the exact organizer checkpoint and scoring configuration are not published in the reviewed rules.
- Isolated `esm==3.4.1.post1` installation **1079586** completed. Its input classes and fold API were inspected on Earth. A CPU-node message about missing `libcuda.so.1` did not make the import check fail; CUDA execution still needs the GPU pilot.
- ESMFold2 resolved revision **69869f737beffec5294845ede23db5fc0b4f509e** was downloaded and audited: 11 files, approximately 24.9 GiB. Inspection of its config showed the ESMC backbone is already bundled. The redundant separate-backbone fetch in **1079587** was stopped without deleting cached data; replacement audit **1079590** completed successfully. The loader uses the bundled backbone.
- Target-only MMseqs2 search **1079588** completed: **1,024 real MSA rows** retained for the public official IL-7Rα sequence. No candidate sequence was sent for MSA generation. Ticket, query hash, MSA hash and raw archive are retained.
- ESMFold2 natural IL-7/IL-7Rα control **1079589** loaded the model and reached folding, then failed because Triton's generated C extension could not find `Python.h`. It ended with a recorded nonzero status; sampled memory reached about 26 GiB, which is not a complete inference memory benchmark. Logs/state are preserved in `execution-evidence/esmfold2-control-v1/`.
- CPU repair **1079591** installed matching CPython 3.12.15 headers under project scratch and passed a compiler check. The common stage launcher supplies that include path through CPATH. Rerun **1079592** passed; an independent local audit verified the finite 388×388 PAE, exact 236/152-residue chain mapping, artifact hashes and three ipSAE rows. A real resume audit reused the successful artifacts without another inference.
- Resource-instrumented control **1079593** also passed. It measured 24.4 s folding, 5.15 s model loading, 27,272 MiB peak reserved VRAM, 35,528 MiB peak host RSS and 32.68/13.84 user/system CPU seconds; full Slurm duration was 1:55. The earlier passing job took 2:06 with 32.5 s folding. Slurm's batch MaxRSS was not credible for the model process, so the second run measured RSS inside that process. Same-seed numerical predictions differ slightly; neither run was selected by higher score. These measurements cover one 388-residue control, not every target.
- That control uses one seed, one sample, no template/pocket conditioning, target-only MSA and the complete declared IL-7Rα sequence interval. Unspecified organizer settings are recorded as local choices. A natural ligand is an evaluation control, not a competition entry or an optimization starting point.
- ipSAE reference code pinned at **6174cf9e71cb1bd660cc805856a18c4871a6dec3**. The adapter retains raw directional and symmetric-max rows at explicitly labeled local cutoffs. It does not claim these conventions are the organizer's one-score definition.

## Phase 5 rehearsal findings

Three bounded BC2 runs have completed with zero accepted designs; this is a failed candidate pilot, not an infrastructure failure:

| Job | Input | Outcome |
|---|---|---|
| 1079594 | Supplied PD-L1 software control, fixed 60 aa, seed 42, two trajectories | One trajectory reached ten MPNN redesigns; all ten refolds failed default filters. |
| 1079595 | Mapped 3DI3 IL-7Rα reference, two trajectories | Both rejected at initial screen; no redesigns. |
| 1079597 | Shipped current-sequence IL-7Rα reference plus epitope focus, two trajectories | First failed sequence hardening, second initial screen; no redesigns; duration 6:29. |

The focused reference has 195 residues numbered 37–231 and no sequence mismatches against current UniProt. Its experimental/predicted origin is not established from the ATOM-only file, and it still lacks 41 official-interval residues. BC2 forced targeting lysinates off-epitope positions during design. This diagnostic conditioning is recorded; any eventual sequence must be evaluated against the full, unmodified 236-residue target. Confidence filters were not relaxed. No larger BC2 budget has been started.

Boltz 2.2.1 installation **1079596** passed in its own environment. The adapter explicitly requests target-only precomputed MSA, one seed/sample, full PAE, no templates/pocket constraints, and no affinity properties. Checkpoint fetch **1079598** failed immediately because that environment lacks HF Hub; corrected CPU job **1079600** completed using the existing ESM download environment. The public Boltz weights are pinned at `6fdef46d763fee7fbb83ca5501ccceff43b85607`; GPU control **1079602** completed: finite 388×388 PAE, exact chains, ipTM 0.2802 and ipSAE 0.0, 4,144 MiB peak reserved VRAM, 54.1 s adapter prediction and 1:26 total job time. This verifies execution/mapping, but poor recognition of the natural interaction is a screening-accuracy concern. It contrasts with the ESMFold2 control and does not justify a hard agreement filter.

## User-authorized RFD4 alternative

The user suggested [NVIDIA's RFD4-Proteína Space](https://huggingface.co/spaces/nvidia/rfd4-proteina-space) and current HF alternatives. Following the unsuccessful BC2 pilots, the TODO explicitly admits one bounded complementary-generator evaluation. Other optional generators, larger campaigns and submission remain deferred.

The [native code](https://github.com/RosettaCommons/RFD4-Proteina) is pinned at `ddd934f7e6b86f7582ce487d5b19f6c526c644b5` (package 0.0.3), with the public [model](https://huggingface.co/nvidia/RFD4-Proteina) at `621b785abf9d61dd24f4b81ae4dbd1330728f030`. The current documented base bundle is the October 19 matched flow/autoencoder pair, 32 latent dimensions and 147 residue classes. The API also lists an October 30 antibody checkpoint, but listing alone does not establish its compatibility or VHH performance; it is not enabled. No HF token was read, printed or transferred.

The source documentation explicitly lists L40S as tested hardware. That is not evidence our particular workload fits; a one-design, 60-aa supplied PD-L1 control will measure it, with compilation and external metrics disabled. CPU install/hash audit **1079599** completed; an independent local check matched its model/config hashes to the pinned upstream manifest. The paired 1.74 GB safetensors bundle/config are checked against the upstream release manifest; training data and optional refolding environments are not requested. The hosted Space has not been used for generation or input uploads.

No model metric is experimental KD, confirmed selectivity or agonism. Phase 5 has now demonstrated one diagnostic input-to-export path, but no candidate is shortlisted or submission-eligible. Candidate quality and promotion remain under review; details follow.

## External review

The user-authorized Capy request used only public challenge/context information. It was automatically rerouted from Opus 5.5; any resulting advice is advisory and must be independently checked. It does not complete any TODO verification item. No further optional review work is being started ahead of the ordered core phases.

## Evidence

See `execution-evidence/local-tests.txt`, `earth-tests.txt`, `gpu-preflight-1079583.out`, `bc2-install-1079584.out`, `bc2-freeze.txt`, `bc2-checkpoint-sha256.txt`, `esmfold2-install-1079586.out`, `esmfold2-freeze.txt`, `esmfold2-checkpoints.json`, `python-headers-1079591.out`, `esmfold2-control-v1/`, `esmfold2-control-v2/`, `esmfold2-control-v3/` and `il7ra-reference-summary.json`. Scheduler IDs are retained so pending/running work can be checked without duplicate submission.

## User-pasted comparator post

Protein Design for Africa describes a separate Adaptyv/Anthropic TfR1 task with pH release and mouse binding, using multiple generators and independent Boltz refolding. Its authors explicitly report no wet-lab data. We retain it as a workflow reference rather than performance evidence. The current [Changjiang TfR1 brief](https://aiprotein.sjtu.edu.cn/targets) requires VHHs and lists no pH/mouse requirement. [PROPKA](https://github.com/jensengroup/propka) predicts pKa values from structures; that is not a direct measured binding-release result. No new objective or optional tool was added to the active campaign from this post.

## First complete diagnostic candidate path

RFD4 control **1079601** passed (60-aa supplied PD-L1 software example; 2,190 MiB peak reserved VRAM; 1:44 total). IL-7Rα generation **1079603** also passed (60-aa binder, exact 195-residue reference identity; 2,564 MiB peak reserved; 1:49 total). Public anonymous model access succeeded; no HF credential was required.

The sequence was imported into common records, then predicted against the complete official 236-residue interval with target-only MSA, no templates or pocket constraints:

| Evidence | ESMFold2 1079604 | Boltz-2 1079605 |
|---|---:|---:|
| ipTM | 0.8772 | 0.9305 |
| ipSAE target→binder / binder→target | 0.5543 / 0.7034 | 0.7186 / 0.7849 |
| Generator-target core fit RMSD, Å | 0.564 | 0.802 |
| Target-aligned binder CA RMSD vs generator, Å | 30.395 | 29.651 |

These are local computational measurements, not official admission or affinity. An independent Bio.PDB alignment reproduced the large binder displacement. Both refolds agree better with each other (2.94 Å binder CA RMSD after fitting the fixed 195-residue core), suggesting an alternate predicted pose; this is not proof that the generated pose is realized or that the binder binds. Whole-target alignment is confounded by the 41 extra terminal residues and is retained separately. Generator/refold residue-pair contact overlap is only about 4.8%. The sequence is 50% D/E and has a KR-minus-DE count of −24; those are composition flags, not measured pI, nonspecificity or expression.

Decision: **hold, no shortlist promotion**. Full report and diagnostic CSV: `execution-evidence/rfd4-il7ra-review-v1/`. The CSV round trip passed and is explicitly marked rehearsal-only; the strict submission-draft exporter still refuses this candidate. No competition entry was created.

A bounded diagnostic **1079606** changed only RFD4's medium→high recycling schedule, keeping seed 42, input, binder length, weights and common evaluators fixed. It completed in 2:00. Both evaluations completed: **1079609** (ESMFold2, 1:50) and **1079610** (Boltz, 1:18). No acceptance filters were relaxed.

Real pipeline-stage recovery was audited on completed generator/ESM/Boltz outputs: CPU job **1079607** intentionally received SIGTERM after saving one completed-stage audit; **1079608** recovered, revalidated all declared output hashes and reused all three original model states unchanged, with zero neural inference reruns. This verifies recovery between completed stages; it does not claim checkpointing an in-progress neural trajectory or qualify BC2 native partial-campaign recovery.

The user requested continued current-method research after failures. The [accuracy validation plan](accuracy-validation-plan-2026-11-02.md) records the next experimental-data validation gate. Public HF data include experimental results and ten predictor outputs, but summary scores are best-of-five and final labels include model adjudication: they must not be used as unqualified one-seed ground truth. No statistical accuracy result has been claimed.

## Controlled recycling comparison result

The high-recycling candidate has a much more consistent generated/refolded pose: independent Bio.PDB audits report 0.656 Å (ESMFold2) and 0.635 Å (Boltz) target-aligned binder CA RMSD, with 77%/75% residue-pair contact overlap. The two refolds agree to 0.856 Å on the fixed reference core. ESMFold2 ipTM is 0.9207 (directional ipSAE 0.7001/0.7990); Boltz ipTM is 0.8910 (0.5015/0.6889). These are one-example computational observations; they do not establish a population-level benefit or a measured binder.

It remains **rehearsal-only and under review**: 55% D/E composition, unconfirmed expression/processing/selectivity, and one Boltz interchain clash at 1.491 Å between target Tyr212 O and binder Arg12 NH2. ESMFold2 has no <2 Å interchain heavy-atom pair under the same geometric definition. The clash is not excused by high confidence. No candidate is submission-eligible or officially shortlisted.

All four candidate refold outputs (two generation settings × two predictors) were independently checked after local download: finite 296×296 PAE and matching artifact hashes. Both diagnostic CSV exports passed round-trip checks. See `execution-evidence/rfd4-il7ra-high-review-v1/` for the revised candidate and independent pose audit.

Current-method refresh: Mosaic source at `5937f37164bcb28bc6f1000f10134145438e5971`, October 29, adds a Mol-1/JAX backend and already includes RFD4 integration. It is read-only under `work/vendor/mosaic`; no Mosaic installation/campaign has started. Its all-backend dependency stack is large, so a future pilot needs a deliberately scoped environment. The live Diffusers 0.42.1 documentation also exposes RFD4 support, despite the pinned native source's older warning about an unreleased integration; this is alternate packaging of the same model, not evidence for a better algorithm.

CPU **1079611** fetched pinned public benchmark tables/docs; no structures corpus, generator inputs or classifier training were used. CPU **1079616** completed a descriptive, human/synthetic-target analysis of 1,080 designs, including vendor-specific and concordant endpoints and a top-20 analysis that selects before revealing outcomes. The paired improvement of a two-model rank combination over ESMFold2 alone was uncertain. See `execution-evidence/screen-benchmark-audit-v4/report.md` and the updated validation plan; this is not a calibrated ranking rule.

The initial local package `rehearsal-review-2026-11-02-v2/` preserved two held candidates. Its successor `rehearsal-review-2026-11-02-v3/` verifies 103 source files and five package files, contains four rehearsal candidates and their directional screen results, and records one research follow-up lead but zero submission-eligible entries. An independent hash and CSV audit passed. The 48 GB L40S measurements for this candidate size were 2,564 MiB peak reserved for RFD4, 26,316 MiB for ESMFold2 and 4,478 MiB for Boltz. The current test suite passed 22 tests on Earth after the benchmark additions (the three pandas-dependent checks are skipped by the system Python locally). The bounded initial rehearsal is complete; later TODO phases remain open.

Next bounded Phase 5 diagnostic: high-recycling RFD4 seeds **43 and 44**, same target-only recipe, model and 60-residue length as the earlier seed-42 high-recycling run. The purpose was to check whether the unusually acidic compositions recur across seeds. Generation **1079617/1079618** completed, and both candidates passed target-identity/provenance/exact-duplicate checks. Seed 43 has 18.3% D/E and seed 44 has 33.3% (versus 55% for seed 42 high). Seed 43's full-target ESMFold2 **1079619** and Boltz **1079620**, and seed 44's ESMFold2 **1079621** and Boltz **1079622**, completed. Per the user's later authorization, two independent one-L40S jobs ran concurrently; each was separately allocated.

CPU reviews **1079623/1079624** wrote their primary reports but failed during the independent pose audit because the RFD4 Python environment lacks Bio.PDB. The failure and partial reports are retained. Recovery jobs **1079626** (seed 43) and **1079625** (seed 44) completed using the already-installed Boltz environment containing Biopython; they reused the existing prediction/review artifacts and wrote separate retry logs. The review launcher was corrected for future use.

Seed 43 is the provisional **rehearsal-only follow-up lead**: ESMFold2/Boltz generator-aligned binder RMSDs 1.49/0.89 Å, refold-to-refold core-aligned RMSD 0.87 Å, and zero interchain heavy-atom pairs below 2 Å in either model. Its local directional ipSAE values were 0.801/0.825 and 0.775/0.781 respectively. Seed 44's Boltz pose moved 17.87 Å relative to the generator and remains on hold despite ESMFold2 pose agreement. These are predicted structures, not measured binding or official admission.

Context jobs **1079627/1079628** found six N-X-S/T target motifs. For seed 43, Asn182 ND2 is 10.44 Å (ESMFold2) and 10.58 Å (Boltz) from the nearest binder heavy atom; an independent Bio.PDB parser reproduced both values. Glycan occupancy and geometry were not modeled, so this is a review flag, not a calculated glycan clash. The 195-residue generator reference, target processing and official screen settings remain unresolved.
