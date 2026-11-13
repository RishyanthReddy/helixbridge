# Changjiang Cup pipeline: plan and TODO

Created November 1, 2026. **Status: ACTIVE. Phases 1–3 verified. Phase 4's local screening pilot passed; exact organizer equivalence remains an open question. Phase 5's bounded rehearsal is complete. Later branches, ranking validation and campaigns remain open.**

This document is the working checklist. The user subsequently authorized implementation, cluster work and bounded pilots. Update tasks with evidence; a completed planning document is not a completed pipeline. Submission still requires user review. See the execution log at the end.

## Goal and scope

Build a reproducible, resumable binder-design pipeline on one NVIDIA L40S with 48 GB VRAM. Support the seven competition tracks through two molecule-format branches and a shared evaluation/export process. Deliver up to twenty eligible, diverse candidates per chosen track, with traceable design records and a design summary for human review.

The recommended execution order is IL-7Rα first, TL1A second, then one VHH track after its own successful rehearsal. Support for seven tracks does not commit us to running seven campaigns. Expanding campaign scope remains a user decision.

The published deadline is November 30, 2026; its hour/timezone and submission-locking behavior remain unresolved. The [November 1 rules audit](changjiang-revealed-brief-2026-11-01.md) is the current source of competition requirements.

## Planned architecture

```text
Official target + format manifest
  ├─ Minibinder: IL-7Rα / TL1A → BindCraft2 baseline
  └─ VHH: other five targets → VHH-specific generator after pilot
       ↓
Shared records + format/novelty checks + deduplication
       ↓
Separate complex prediction + interface/pose/sequence QC
       ↓
ESMFold2 + ipSAE admission-screen approximation
       ↓
Finalist review: context, required function, diversity
       ├─ Optional Mol-1 structural second opinion
       └─ Optional narrow off-target counter-screen
       ↓
Up to 20 candidates per chosen track
       ↓
Validated official CSV + design summary + user review
       ↓
Official submission and experimental selection
```

User steering, November 2: when an approach fails, diagnose the failure and keep evaluating current alternatives rather than abandoning the pipeline. Promote alternatives through bounded pilots and common independent evaluation. Define accuracy against public experimental outcomes with held-out target/family splits; predicted confidence alone is not proof of better binding prediction. This does not authorize unbounded GPU sweeps or submission.

GPU stages initially ran sequentially. On November 2 the user authorized parallel jobs; up to two independent jobs may now run concurrently, each with its own Slurm-allocated L40S and 48 GB VRAM, subject to shared-cluster limits. A shared record links every stage; failures remain visible. No confidence score is labeled experimental KD, selectivity or agonism.

## Planning completed

- [x] Review the revealed official targets, rules and FAQ; document conflicting or absent details.
- [x] Define minibinder/VHH branches, common evaluation and optional checks.
- [x] Create this ordered TODO with completion checks and explicit start gate.

## Phase 0 — Start gate

- [x] **Receive the user's explicit instruction to start execution.** Authorized in this chat November 1; active goal created.

Nothing below starts before this gate. Account changes, external messages, submission, deployments and scope expansion require their own applicable authorization; a start command is not blanket permission for those actions.

## Phase 1 — Freeze requirements and inspect the workspace

Dependencies: phase 0.

- [x] Inspect applicable AGENTS.md instructions, existing files and Git status/diff before implementation; preserve user changes. Research folder had no Git repository; new implementation is isolated in `pipeline/` with its own Git repository.
- [x] Refresh official requirements and maintain an open-question log. Evidence: `pipeline/config/requirements-status.json`; TinyFish source snapshot under `work/implementation-research-2026-11-01.json`.
- [x] Confirm initial campaign scope; IL-7Rα first under the authorized TODO. Other tracks remain staged.
- [x] Record Earth working location, storage, Slurm access and resource requirements. Evidence: guide supplied by user, live quota/partition inspection and GPU job 1079583.
- [x] Resolve implementation route. No Antigravity tools were available; implementation proceeds directly under the user's start instruction.

**Complete when:** a versioned requirements record distinguishes confirmed facts, assumptions and blockers. Organizer questions may be drafted; sending them needs explicit authorization. Only dependent tasks wait on unresolved details.

## Phase 2 — Exact target manifests

Dependencies: phase 1.

- [x] Create manifests for all seven official targets and download/check UniProt intervals and displayed isoforms. Evidence: `pipeline/config/targets.json`, `pipeline/data/targets/manifest.json` and per-target source hashes.
- [x] Prepare first target sequence and reference structure mapping using DBREF plus an independent SIFTS check. Evidence: `pipeline/data/targets/il7ra/mapping.json`.
- [x] Record context concerns and separate the reference rehearsal from the official target. 3DI3 supplies 193 mapped residues, lacks 43 positions of the official 236-residue interval, and differs at UniProt position 66 (T in structure versus I in current sequence). No mutation/missing coordinate was silently repaired. TfR1 remains unverified and disabled for execution.
- [x] Document EGFR pH 6.0 and GLP-1R agonism requirements without importing other competitions' objectives.

**Complete when:** target inputs have checksums, explicit numbering and reviewed mappings. No silent trimming, guessed structure substitution or unknown assembly is presented as official.

## Phase 3 — Minimal execution and data foundation

Dependencies: phases 1–2; implementation route resolved.

- [x] Choose a thin Slurm runner for the baseline; pinned BC2 already resumes campaigns, avoiding another orchestration dependency in the first rehearsal.
- [x] Define task/candidate records, raw generator metadata and source hashes; preserve evaluation/review status explicitly. Implementation: `pipeline/binder_campaign/`.
- [x] Implement bounded Slurm jobs and task resume checks; one GPU process initially, separate CPU/RAM requests. Hardware check completed; model inference remains a later phase.
- [x] Install/pin BC2 environment on scratch. Source b6fb3ae15ab6a702f1156cffc11bcc3323c2fd06; install job 1079584 passed, package freeze saved, 27 checkpoint files hashed in CPU job 1079585. Other model environments are created only in their respective phases.
- [x] Validate output schemas/finite metrics, exit codes, stale output refusal, matching-hash resume, timeouts and signal interruption. Eighteen meaningful tests passed locally and on Earth Python 3.12.15, including explicit partial-output hash guards for native resume. Actual BC2 partial-campaign restart remains a Phase 5 check. An interruption cleanup defect was fixed before inference.

**Complete when:** a small fixture traverses the record/runner workflow and interruption, malformed output and failed subprocess handling are demonstrated without a large campaign.

## Phase 4 — Test the official-screen path early

Dependencies: phase 3; exact reproduction additionally needs organizer configuration.

- [ ] Identify the actual ESMFold2 implementation/checkpoint and ipSAE code/settings used by the organizer. Exact organizer choice/settings remain unconfirmed. Public canonical Biohub checkpoint 69869f737beffec5294845ede23db5fc0b4f509e and its bundled ESMC backbone audited successfully in job 1079590; isolated esm installation 1079586 passed. ipSAE reference pinned to 6174cf9e71cb1bd660cc805856a18c4871a6dec3. These are explicitly a local approximation.
- [x] Configure one seed, one sample, no template, target-only MSA and no partner MSA for the control; record remaining protocol differences. MMseqs2 CPU job 1079588 produced 1,024 target-only MSA rows. Model execution is a separate unchecked item.
- [x] Run a compatible first-track control on L40S. Initial 1079589 failed on Python headers; repair 1079591 passed; full prediction 1079592 completed and its actual resume check reused validated files. Resource-instrumented 1079593 also completed. For the 388-residue natural-ligand control: fold 24.4–32.5 s, peak reserved VRAM 27,272 MiB, self-reported peak host RSS 35,528 MiB, 32.68 user CPU seconds and 13.84 system CPU seconds in the instrumentation run. Overall jobs took 1:55–2:06 including startup. These are control measurements, not all-target throughput guarantees.
- [x] Validate mapping and ipSAE input conventions: exact 236/152-residue chain sequences, finite 388×388 PAE, three directional/symmetric-max rows and artifact hashes checked independently after download. Both successful runs and the initial failure are retained under `outputs/execution-evidence/`. Auxiliary pLDDT-based ipSAE-script metrics are excluded from interpretation.
- [x] Document the official-equivalence limitation and fallback: public Biohub ESMFold2 plus pinned reference ipSAE is a working local approximation. Organizer checkpoint/settings/cutoffs/aggregation remain unknown; no official admission-score claim is made. No alternative platform is needed for this tested input.

**Complete when:** there is a measured screening path or an explicit, evidenced blocker and fallback assessment. No substitute model is claimed to reproduce the official screen.

## Phase 5 — First real end-to-end rehearsal

Dependencies: phases 2–4; unresolved official details can remain documented where they do not block a rehearsal.

- [x] Install and pin BindCraft2; start with a supplied reference example and one worker, then a bounded IL-7Rα rehearsal. PD-L1 control 1079594 completed with two trajectories and ten refolded redesigns, none accepted. Initial IL-7Rα reference 1079595 completed with both trajectories rejected at the screen. Input/settings diagnosis is recorded; focused WT-reference revision 1079597 completed in 6:29 with the same two-trajectory bound and unchanged confidence filters: one failed hardening and one failed the initial screen, with zero redesigns or accepted sequences. These failures are preserved; no BC2 candidate acceptance is claimed.
- [x] Add and exercise hard checks for the current minibinder rehearsal: sequence alphabet/length and format, exact duplicates across the four candidate records, provenance hashes, and prohibited known-positive starting points. The target-only recipe plus a new 60-residue segment was audited and the seed-43/44 jobs matched that recipe byte-for-byte. This is recipe-specific; general novelty, cross-team duplicates and future VHH formats remain open in later phases.
- [x] Add separate complex prediction with preserved PAE/structures. Boltz control 1079602 and real RFD4 candidate predictions 1079604/1079605 passed execution/mapping checks. Boltz natural-ligand control confidence was poor; execution is not screening-accuracy validation.
- [x] Calculate raw interface confidence, target-aligned binder pose, contacts/clashes and sequence composition/motifs on actual outputs. Independent Bio.PDB audit reproduced the geometry. Our explicit geometric flags are not binderqc or calibrated energy filters; binderqc was not used. The medium candidate changed pose by ~30 Å, while the controlled high-recycling candidate stayed within ~0.65 Å but retains composition/clash concerns.
- [x] Produce a provisional shortlist, admission-screen record and an internal draft export for the rehearsal. `rehearsal-review-2026-11-02-v3/` contains one **rehearsal-only follow-up lead**, three held designs, both directional local screen records, and an empty submission shortlist. An independent audit verified 103 source hashes, five output hashes and CSV round trips. The organizer's actual CSV schema remains unconfirmed; no entry is submission-eligible.
- [x] Evaluate the predeclared two-seed high-recycling RFD4 diagnostic on the same IL-7Rα reference, retaining both outcomes and running the common screens. Generation 1079617/1079618 and predictor jobs 1079619–1079622 passed, using at most two GPUs concurrently. CPU reviews 1079623/1079624 produced initial reports but failed the independent pose audit because Bio.PDB was absent from the chosen environment; recovery jobs 1079626/1079625 completed using the Boltz environment and retained the failures. Context audits 1079627/1079628 report sequon proximity without modeling glycans. This is a small diagnostic, not evidence of binding.
- [x] Interrupt and resume a real pipeline-stage audit: 1079607 intentionally terminated after saving a partial journal; 1079608 recovered and reused generator/ESM/Boltz states with unchanged hashes and zero inference reruns. This verifies stage-level recovery, not BC2 native partial-trajectory recovery, which remains unqualified.

**Complete when:** at least one candidate has a complete input-to-export record, all failures are accounted for, and L40S resource use is measured. If no candidate survives, report that outcome and revise before scaling; computational success is not confirmed binding.

**Rehearsal completion evidence:** `initial-goal-completion-audit-2026-11-02.md`. This closes the initial rehearsal gate only; it does not validate the competition construct, establish binding, or authorize a submission.

## Phase 6 — Add only justified branches

Dependencies: successful phase 5; selected additional track scope confirmed.

- [ ] Prepare a bounded TL1A rehearsal with reviewed assembly/context.
- [x] Assess the user-proposed LocalFold AF2-Multimer backend as an optional additional check. Three Mac M3/Node-Dawn diagnostic complexes passed export and chain/PAE mapping checks, but a matched-feature native comparison missed the predeclared numerical gate. Its scores are excluded from ranking; optional inspection remains available. This qualifies neither browser UI nor L40S throughput. See `localfold-qualification-2026-11-02.md`.
- [x] Run the authorized bounded Mosaic minibinder pilot with disclosed inputs and compute; use a separate predictor because Boltz is in the design objective. Install 1079629, smoke 1079630, design 1079631, import 1079632, ESMFold2/Boltz 1079633/1079634 and review 1079635 all completed successfully. The candidate is held: ~21/24 Å generator-to-refold pose shifts and weak directional interface scores. Recipe production promotion is deferred. GPU time was 0.40 hours, maximum two concurrent allocations. `generator-comparison-2026-11-02-v3/` contains the comparison. This is not a matched-budget generator success-rate experiment; that remains required before a generator-wide superiority claim.
- [ ] Pilot BC2's existing VHH modality first, or mBER if justified; verify complete framework/CDRs, numbering, length and permitted scaffold provenance before a VHH campaign. A separate generator is not automatically required for VHHs.
- [ ] Pilot Mol-1 on a small finalist/reference set; compare predicted interfaces and measure L40S cost. Request its full confidence/PAE outputs and verify token mapping before downstream scoring.
- [ ] Keep external MSA services and local/precomputed inputs explicit; avoid silently changing the binder-MSA policy.
- [ ] Retain PXDesign, Complexa and BoltzGen as alternatives, promoting one only if pilot results justify the added cost and complexity.

**Complete when:** every enabled branch has valid mapped outputs and measured cost. Optional branches can be marked deferred with a reason; they are not prerequisites for the first campaign.

## Phase 7 — Ranking and candidate selection

Dependencies: phase 5; optional phase 6 branches only if promoted.

- [ ] Check ranking behavior against public experimental datasets, separating unknown/failed/censored results and related sequences/targets. Keep same-target known positives out of optimization starting inputs. **Partial:** `execution-evidence/grouped-screen-validation-v2/REPORT.md` covers 674 lineage/sequence representatives, ten primary-endpoint held-target folds, separate vendor endpoints and unresolved-outcome bounds. Consensus showed no average primary-endpoint gain over ESMFold2 alone (paired 95% interval −0.02 to +0.02), and no reliable vendor-specific improvement. This is internal validation on previously inspected, preselected data; a truly external dataset remains a future check.
- [ ] Separate official-screen approximation from independent structural/biological evidence; preserve raw metrics instead of hiding them in an arbitrary weighted score.
- [x] Complete the bounded sequence/context diagnostic for the four existing research follow-ups. Locally compared 1,684 pinned public sequence rows (1,683 unique, including 90 IL7Rα designs) and the 17-design internal pool; no exact or strict >90% contiguous-overlap flag. Seed101 alone has Cys25 and two N-linked sequons; its interface/solvent geometry is recorded. This is a limited diagnostic, not global novelty, measured developability or competition eligibility.
- [x] Complete seed101's bounded two-model prediction-seed robustness check. The original ESMFold2 timeouts remain preserved. CPU staging qualification1088572 and one sequential L40S job1093453 recovered ESMFold2 seeds1/2 using unchanged scientific requests, adapter and weights. All six predictions have verified PAE/mapping and independent geometry: shared-core binder differences at most1.30Å, contact Jaccard at least0.90, no <2Å interchain heavy-atom pairs. Whole-target alignment can differ by16.55Å because the low-confidence N-terminal region varies substantially; both conventions and regional differences are retained. New GPU use214seconds within900seconds. This closes the bounded sampling assessment only; sequence/context flags and submission gates remain open. See `esm-recovery-review-2026-11-02-v2/REVIEW.md`.
- [ ] Cluster by sequence, fold and binding site, preserving trajectory/backbone provenance and avoiding a shortlist dominated by close variants. **Partial, expanded:** all16RFD4 baseline structures now have240within-predictor US-align comparisons and complete-link/contact sensitivity analyses. The four follow-ups have distinct predicted shapes but overlapping sites (Jaccard~0.60–0.83). At TM>=0.5 and80% coverage there are11 descriptive structural groups per predictor; this is not formal fold taxonomy. Site connected components can merge through bridges; greedy complete-link groups at Jaccard0.5 number3/4 across the full pool. Two alternative surface regions and one reserve are proposed; broader site coverage remains untested. See `il7ra-diversity-checkpoint-2026-11-02.md`.
- [ ] Apply required task-specific review; keep GLP-1R agonism unresolved until supported by the relevant evidence/official clarification.
- [ ] Add limited, biologically relevant off-target checks only when justified by budget. Treat SelectBench as a methodological reference, not a protein-binder evaluator.

**Complete when:** selection is reproducible, diversity is visible and each retained/rejected candidate has a recorded reason. Computational confidence is never converted into an unsupported affinity or functional claim.

## Phase 8 — Controlled campaigns

Dependencies: phases 5 and 7; phase 6 for additional formats/tracks.

- [x] Complete the specifically authorized 12-design IL-7Rα **reference** campaign after seed-43 robustness and LocalFold assessment. Seeds 101–112 all have complete common reviews; original seed 43 plus new 101/103/105 are provisional research follow-ups. The whole follow-up goal used 70.72 of 90 authorized GPU-minutes with maximum two GPUs. This closes the bounded rehearsal checkpoint, while target/assay confirmation and a larger competition campaign retain their gates.
- [ ] Set per-track GPU-hour/storage budgets from measured pilot throughput and actual queue access.
- [ ] Run the initial chosen track, reviewing failure rates and diverse viable outputs before increasing scale.
- [ ] Expand to TL1A or a VHH track only after its rehearsal and scope decision.
- [ ] Evaluate finalists under the closest available official settings; retain additional robustness runs separately.

**Complete when:** each active track has a reviewed pool sufficient for a defensible shortlist, or a documented no-go. Never fill twenty slots with invalid candidates merely to reach the limit.

## Phase 9 — Reviewable submission package

Dependencies: phase 8 and confirmed portal format.

- [ ] Choose up to twenty eligible candidates per active track; recheck length, alphabet, molecular format, novelty and duplicate/CDR rules.
- [ ] Export exactly the official CSV schema and write the design summary using actual methods/settings and observed results.
- [ ] Validate a CSV round trip, sequence-to-record mapping and absence of tags/fusions, credentials or unsupported experimental claims.
- [ ] Resolve confirmation locking, deadline timezone and update/priority behavior; prepare versioned packages and receipt recording.
- [ ] Present the concrete package and checks to the user for final review.
- [ ] Submit only with explicit user authorization and retain the official receipt/version.

**Complete when:** files and evidence are reviewable; actual submission is separately marked complete only after a verified receipt. Wet-lab testing and ranking are organizer actions, not milestones we can claim ourselves.

## Planning calendar

Internal targets, subject to the eventual start date, queue access and measured throughput:

| Window | Intended milestone |
|---|---|
| November 1–3 | Requirements, targets, execution foundations and screen identification |
| November 4–7 | Measured L40S screen pilot and complete first rehearsal |
| November 8–20 | Controlled campaigns; justified optional branches |
| November 21–26 | Finalist screening and selection |
| November 27–29 | Reviewed submission package and submission buffer |
| November 30 | Published deadline; exact time still requires confirmation |

If the start is delayed, revise this calendar before committing resources. Implementation readiness, official-screen admission and experimental success are distinct outcomes.

## Execution evidence log

November 1 evidence:

- Phase 1: live SSH/Slurm/quota checks succeeded. Scratch root `/cfs/earth/scratch/mekalris/changjiang-2026`; no existing project was modified.
- Phase 2: all seven UniProt ranges/endpoints/isoforms checked; IL-7Rα reference limitations recorded explicitly. This closes preparation bookkeeping, not resolution of the organizer's missing assay-construct details.
- Phase 3: GPU hardware job **1079583** completed, showing one L40S, 46,068 MiB, driver 610.57.04 and CUDA UMD 13.3. CPU install **1079584** completed with BC2 dependency self-check. CPU checkpoint audit **1079585** completed.
- Tests: `python3 -m unittest discover -s tests -v` locally and the same suite with the Earth BC2 Python: **18 passed** after native-resume tests were added. Bash syntax and staged diff whitespace checks passed. Tests include missing/NaN/header-only outputs, failure-code preservation, changed inputs/outputs, exact duplicate/invalid candidate handling, rehearsal-export refusal, timeout, actual process interruption, incorrect target endpoints and unsupported isoforms.
- Evidence copied locally under `outputs/execution-evidence/`; source and open questions are versioned in `pipeline/config/`.
- At the initial foundation checkpoint, no model inference had run. Subsequent screen/design evidence is recorded below and in the execution status; no large campaign or submission has run.
- A public-context Capy review was requested before the user's step-order reminder; it is advisory and does not satisfy any TODO verification step. No further optional review work is being started ahead of the core phases.
- Phase 4 details and scheduler IDs are tracked in [pipeline-execution-status.md](pipeline-execution-status.md). Do not start Phase 5 until the screen pilot passes or its blocker/fallback is explicitly recorded.
- Phase 4 local pilot passed and was audited November 1. The user-pasted Protein Design for Africa post is a later review reference, not validation data or a reason to add pH/mouse objectives to our tracks. Optional branches remain deferred.
- Phase 5 diagnostic revision: the shipped BC2 IL-7Rα structure has 195 residues numbered 37–231 and zero identity mismatches against the current official sequence. A separate audited configuration uses this reference plus its shipped hotspot/coldspot focus; the original variant-containing run and its failures remain intact. This changes both reference and epitope conditioning, so it is not a causal ablation of either variable.

## User-authorized conditional fallback — November 1 update

The user specifically suggested `nvidia/rfd4-proteina-space` and permitted alternative algorithms if needed. Following the two unsuccessful small baseline campaigns, evaluate **RFD4-Proteína** as the first conditional complementary generator. This amendment does not complete the baseline or authorize a large campaign; it makes the fallback explicit rather than silently drifting from the TODO.

- [x] Read the canonical model card and Space source. Current documented paired release October 19; model bundle about 1.74 GB; model card explicitly lists L40S among tested GPUs. Space generates structures without refolding metrics. Its hosted GPU model is not proof of any specific L40S workload's memory fit.
- [x] Inspect and pin native code, paired bundle and generation-only interface: code `ddd934f7e6b86f7582ce487d5b19f6c526c644b5`, package 0.0.3, HF revision `621b785abf9d61dd24f4b81ae4dbd1330728f030`, bundle/config hashes from the release manifest. This revision still contains the documented October 19 release pair; an October 30 antibody filename is listed but its compatibility/qualification has not been established. Anonymous access only; no token read or transferred. CPU install/hash audit 1079599 completed successfully; model/config hashes agree with the pinned upstream release manifest.
- [x] Run one supplied-example pilot with compilation and external metrics disabled: 1079601 passed, one 60-aa PD-L1 control binder, exact target identity and finite coordinates, 2,190 MiB peak reserved VRAM, 1:44 total Slurm duration (89.2 s adapter generation/model setup). IL-7Rα reference CIF round trip preserves coordinates, canonical identities and numbering 37–231. This completes control/input preparation only; the separate one-design IL-7Rα GPU task 1079603 is queued behind Boltz control 1079602.
- [x] Route resulting sequences through full-target independent prediction, ESMFold2/ipSAE approximation, format checks, failure records and selection review. All four RFD4 rehearsals have complete common reviews; a generated structure alone is not a passing candidate.
- [x] Record the RFD4 alternative decision using measured cost and common evaluation: retain it as the current generation baseline, with seed 43 a provisional rehearsal follow-up lead. No submission promotion. The subsequently authorized Mosaic comparison is complete and deferred; Mol-1 and selectivity extras retain their original gates.

November 2 continuation: focused BC2 1079597 completed with zero accepted designs. Boltz install 1079596 passed. Weight fetch 1079598 failed because the Boltz environment lacks HF Hub; corrected 1079600 uses the existing audited ESM download environment. RFD4 generation-only install/hash audit 1079599 is running. GPU stages remain sequential and bounded. Subsequent RFD4 control/generation and common evaluations completed; see the execution-status report for the held candidate and controlled high-recycling revision.

November 2 diagnostic result: first RFD4 IL-7Rα candidate completed generation, both full-target refolds, interface/pose/sequence review and a checked rehearsal-only CSV. High confidence did not preserve the generated pose (about 30 Å binder displacement), so no candidate was shortlisted. The independently verified alternate refolds and acidic composition are documented. Same-input/seed high-recycling comparison 1079606 completed and its common evaluations 1079609/1079610 are in progress. See [accuracy validation plan](accuracy-validation-plan-2026-11-02.md) for the later experimental-data benchmark; no accuracy claim or model training has run.

Controlled high-recycling comparison completed: 1079606 generation, 1079609 ESMFold2 and 1079610 Boltz. Pose consistency improved to ~0.65 Å in this example; acidic composition and a Boltz atomic clash remain unresolved, so no shortlist promotion. CPU 1079611 fetches only pinned experimental benchmark tables/docs as preparation for the existing accuracy-validation gate. Mosaic current source (October 29 Mol-1 integration) was inspected read-only; no extra generator install or campaign was started.

Subsequent authorized follow-up completed: target/family-separated benchmark validation
with vendor sensitivities, public construct/glycan review and one Mosaic pilot plus
common evaluation. See `next-stage-completion-audit-2026-11-02.md`. BoltzGen and
PXDesign were refreshed as reserves, without installation or extra GPU campaigns.
Phases 6–9 as a whole remain open; other targets/formats, external accuracy
validation, controlled campaigns and an official submission package are not complete.

Subsequent approved checkpoint: the robustness/LocalFold/12-design reference goal
completed. `controlled-campaign-review-2026-11-02-v4/` contains all 12 new reviews,
four original baselines, separate robustness evidence, four explicitly selected
research follow-ups and an empty submission shortlist. The 29 tests and final
569-source/five-output hash audit passed; all outputs reproduced byte-for-byte
under a different Python hash seed. See `robustness-localfold-campaign-completion-2026-11-02.md`.

Next bounded validation checkpoint assessed: four new seed101 allocations used
1,139 GPU-seconds (18.98 minutes), peak concurrency two. Boltz seeds1/2 completed;
ESMFold2 seeds1/2 were interrupted by the bounded job signals before producing
structures. All failures and scheduler evidence remain under
`execution-evidence/lead101-validation-v1/` and the per-predictor directories.
The complete two-model robustness gate remains open. Seed43 remains the cleaner
repeat-tested research baseline; seed101 stays a research follow-up with explicit
Cys25/sequon review. No submission promotion. The limited public sequence/context
review completed for all four follow-ups; no candidate sequence was uploaded.
See `lead101-checkpoint-2026-11-02-v2/REVIEW.md` and the checkpoint completion note.

ESMFold2 operational recovery subsequently completed: CPU-only packaging and
path/content qualification1088572, then GPU1093453 (214seconds, one L40S) produced
the two missing seed101 predictions. The pinned model, MSA, unchanged prediction
adapter and exact scientific request bytes were preserved. Local files and
imports were verified; all six predictor/seed outputs were independently checked.
The previous639-source checkpoint remains unchanged. The final recovery package
and its separate verification record contain the current robustness evidence.
Seed101 still requires Cys/sequon/context review; no submission eligibility is
claimed. Broader binding-region/fold diversity and external accuracy validation
remain open. See `esm-startup-recovery-completion-2026-11-02.md`.

Next CPU-only diversity checkpoint completed:240structure alignments, sixteen
baseline contact sets per predictor and threshold sensitivity analyses; source
reference compared with experimental3DI3. Prepared three unexecuted pilot arms
(control/patch139/patch72), ten hotspots each, paired seeds201/202, six designs
proposed with a90GPU-minute envelope. Patch171 is a context-sensitive reserve.
No GPU work or candidate generation ran in this checkpoint. Adapter/input review
and the pilot's implementation gate remain before execution. See
`il7ra-diversity-checkpoint-2026-11-02.md` and
`il7ra-next-site-pilot-2026-11-02/plan.json`.

## Executed site-diversity pilot — November 2

The preceding "unexecuted" statement describes the earlier preparation
checkpoint. The six-case pilot has now executed, with its original inputs,
paired generation seeds, gates, resource cap and decision rule preserved.

- [x] Independently review the target-only adapter and all three arm inputs;
  retain identical target coordinates and ten hotspots per arm.
- [x] Complete control201 and patch139/201 implementation gate, including both
  refolds, raw metrics/PAE, chain mappings and independently checked geometry.
- [x] Complete the remaining four generation cases and both refolds for each.
- [x] Compare all six against the sixteen original candidates and four existing
  research follow-ups, keeping site, fold, pose, sequence and context evidence
  separate.
- [x] Audit resource use and reproduce numerical review/CSV outputs; preserve
  every design and all failure/held outcomes.
- [x] Apply the predeclared additional-run rule: no qualifying case, so no
  conditional robustness run. Do not relax the rule after observing results.
- [x] Finish the separately declared BoltzGen reserve qualification and record
  its common evaluations or actual operational failure within the original cap.

Six pilot candidates are held. Seed43 remains the cleaner existing research
baseline; seed101/103/105 retain their previous follow-up status and caveats.
No new candidate is submission eligible. The six-case portion consumed 2,023
GPU-seconds, maximum concurrency two. See
`site-pilot-results-2026-11-02.md` and the independently verified review package.

Phases 6–9 remain open overall. Outstanding work includes independently justified
candidate improvement, external accuracy validation, assay-construct/context
uncertainties, other target/format gates, and a reviewed official-format package.
BoltzGen is an adaptive engineering qualification, not a completed campaign or
an assumption that a different generator improves experimental success.

BoltzGen follow-through completed: one design and both common refolds; no new
research finalist. Combined resource use is 2,425 GPU-seconds (40.42 minutes),
maximum concurrency two. See `boltzgen-reserve-results-2026-11-02.md`.
Engineering availability is established for this workload; improved binding
prediction accuracy is not. The seven new designs remain held, and the original
six-case decision rule and frozen package are unchanged.

## Optional LiteFold evaluation — November 2

- [x] Test the authorized API using a public natural IL7–IL7Rα complex and
  save both provider structures, settings, confidence metrics, and costs.
- [x] Compare LiteFold Boltz and Protenix to experimental 3DI3 with
  independently checked structural alignment.
- [ ] Benchmark a wider set of public experimental positives and negatives,
  investigate server model/MSA settings and reconcile actual credit usage
  before treating hosted predictions as a trusted ranking signal.
- [ ] Continue the predeclared local lead101 repair experiment and unchanged
  common screens; do not promote candidates on the basis of hosted control
  predictions alone. Organizer assay settings remain unknown.

The public-control comparison and limitations are in
`litefold-public-control-results-2026-11-02.md`; no candidate was sent to the
service during this qualification.

## Controlled lead101 repair — November 2

- [x] Freeze the two-arm repair protocol before seeing variant scores.
- [x] Verify CPU preparation and native model inputs, preserve all32 samples,
  and select the two unique variants without resampling.
- [x] Run both common predictors at seed0 and apply every frozen gate.
- [x] Prioritize the passing triple repair and compare prediction seeds1/2
  against matched parent outputs; verify hashes, PAE and independent geometry.
- [x] Audit limited experimental glycan-fragment overlays and GPU accounting,
  including failed bookkeeping and its continuation.
- [ ] Continue experimental accuracy/novelty/diversity validation and resolve
  organizer-only assay/screen information when available.

Outcome: provisional repaired research follow-up, with no submission promotion.
See `lead101-repair-results-2026-11-02.md`; phases6–9 remain open overall.

## Follow-through on repair/context uncertainty

- [x] Compare repairs with the saved public sequence corpus and all original
  candidate records; preserve the limited scope of the novelty conclusion.
- [x] Record same-family identity and contact overlap so near-parent repairs
  are not counted as independent scaffold/epitope diversity.
- [x] Test natural-control sampling sensitivity with unchanged local Boltz
  seeds1/2 and experimental-reference alignment; retain both outcomes.
- [x] Complete the separately frozen public-natural-IL7 MSA sensitivity test
  after the CPU alignment search and input verification.
- [ ] Resolve exact organizer-only assay/screen details and broaden externally
  validated accuracy/diversity evidence. No submission eligibility is implied.

## Six-control actual-screen validation — November 2

- [x] Freeze score-independent selection and family grouping before inference;
  preserve the pre-execution resource-wording correction.
- [x] Complete all six public IL7Rα controls in each common predictor,
  retaining vendor labels and exact raw outputs as evaluation-only data.
- [x] Independently verify provenance, model/MSA identity, sequences, finite
  PAE, raw score rows and vendor source records; audit777GPU-seconds.
- [x] Preserve high-confidence non-binder counterexamples and exploratory
  pose/glycan-context checks without fitting a threshold or promoting a rule.
- [x] Map the source's193-residue/T66 computational construct and distinguish
  the vendors' assay-reference annotations from our input and organizer unknowns.
- [ ] Broaden experimental-accuracy evaluation with predeclared grouping and
  construct sensitivity; retain the repaired candidate as provisional research.

All12 predictions passed operational checks; six controls are insufficient to
validate a binding classifier. See `il7ra-public-screen-pilot-results-2026-11-02.md`.

## Competition access and rules follow-up — November 2

- [x] Verify the public sponsor-platform offer and identify the tools advertised
  in AsterFire's public catalog; competition-specific access remains unverified.
- [x] Record the official statement about publication of selected sequences
  and experimental results, including failures.
- [ ] Resolve conflicting official guidance on whether confirmed submissions
  can be changed; do not infer portal behavior from the public page or attempt a
  test submission. See `competition-access-and-rules-audit-2026-11-02.md`.

## Interpretation audit — November 2

- [x] Independently recheck the saved ten-predictor fold aggregates and record
  the limits of the resampling interval and unresolved outcome labels. The
  audit did not run models or alter the original results. See
  `ten-predictor-interpretation-audit-2026-11-02.md`.
