# Changjiang campaign runner

Internal research workflow for one L40S. Competition facts and open questions are in `../outputs/changjiang-revealed-brief-2026-11-01.md`; task status is in `../outputs/pipeline-plan-and-todo.md`.

## Current boundaries

The core runner uses the standard library and supports Python 3.9+. Model and benchmark-analysis scripts use their isolated Earth environments. BindCraft2 is pinned independently; no upstream code has been modified. The VHH preset already exists in BC2, but framework/CDR and scaffold-policy validation is still required. After three unsuccessful bounded BC2 pilots, the user authorized an RFD4-Proteína fallback evaluation in Phase 5. Other optional generators remain deferred.

All seven target sequence ranges are checked against UniProt, including verification that requested `-1` isoforms are displayed sequences. This does not verify laboratory terminal processing or assembly.

The initial IL-7Rα structure is a **reference rehearsal**: chain B of 3DI3, mapped through DBREF and independently checked against SIFTS. Missing residues and identity differences are recorded. The extracted structure is not represented as the complete, exact official assay target. Rehearsal sequences are refused by the submission-draft exporter.

The ESMFold2/ipSAE official settings are only partly specified by the organizer. There is no claim that a local model produces the official score. The local ESMFold2 control, Boltz independent-predictor adapter and RFD4 generator control ran on L40S; exact organizer equivalence remains unresolved. See the execution status for actual evidence and limitations.

Four RFD4 IL-7Rα rehearsals now have both full-target refolds, target-aligned pose/sequence review and checked diagnostic CSVs. Seed 43 is a provisional research follow-up lead; the other three are held. The hash-verified review package under `../outputs/rehearsal-review-2026-11-02-v3/` has an empty submission shortlist. The lead's unmodeled target glycan context and reference construct require review. This is a diagnostic path, not a submission-ready candidate pool. See `../outputs/pipeline-execution-status.md` and `../outputs/accuracy-validation-plan-2026-11-02.md`.

The current adapters/configs are bounded research pilots for this Earth project and IL-7Rα. Other target formats and large batches still need their own reviewed inputs and measured runs.

## Local checks

```bash
cd pipeline
python3 -m unittest discover -s tests -v
python3 -m binder_campaign prepare-targets
python3 -m binder_campaign run path/to/task.json
```

`prepare-targets` downloads public UniProt JSON records and retains checksums, entry dates and full official FASTA intervals. Cached source records are reused intentionally; refreshes should use a separate data directory to preserve prior evidence.

Task specs use argv lists, explicit working directories, tool revisions, input files, expected output validators and timeouts. Resume requires matching task/input hashes and unchanged validated output hashes. An exit code of zero alone is insufficient. Existing partial outputs and stale locks require explicit inspection, rather than automatic deletion. Timeout and interruption propagate to the subprocess process group. Task success means validated task artifacts, not experimental binding or a passing candidate.

For a tool with a verified native resume protocol, a spec may explicitly set `native_resume: true` before its first attempt. After a recorded failure, partial outputs must match their recorded hashes and all inputs/settings must remain unchanged. The failed attempt is archived before another attempt. This policy is intended for BC2 trajectory/candidate reuse; it does not imply checkpointing an in-progress neural-network optimization step. ESMFold2 control tasks do not opt into partial resume.

Environment variables in specs are recorded; never put credentials or tokens there. Credential-bearing environment values inherited by a process are not dumped into manifests.

## Earth project

Scratch root: `/cfs/earth/scratch/mekalris/changjiang-2026`.

* `src/BindCraft2`: pinned upstream source and its `.venv`.
* `src/pipeline`: this runner, configs and target inputs.
* `data/weights`: model checkpoints, kept out of the small home filesystem.
* `env`: environment tools, package/cache directories and package freeze.
* `results`: task records and actual model outputs.
* `logs/slurm`: scheduler stdout/stderr.

The scripts in `slurm/` request resources explicitly. Installation uses CPU partition earth-3; GPU preflight and inference use one L40S on earth-4. The first design rehearsal is capped at two trajectories and one hour. Use fresh campaign/task directories after material input changes. Do not resubmit a running job or manually set `CUDA_VISIBLE_DEVICES` over Slurm's allocation.

## Candidate records and export

`candidates.import_bc2` reads `Binder_Sequence` from real BC2 tables, preserving raw metrics, source hashes and rejected rows. VHHs remain flagged for complete framework/CDR review. Generator confidence is not reclassified as independent prediction, admission success or affinity.

`export_draft` requires explicit selected IDs, completed review fields and at most twenty non-duplicate sequences per target. Rehearsal candidates are blocked. Its CSV is **internal only**: the organizer's actual CSV schema is still unconfirmed. Final portal export and submission require later TODO completion and user review.
