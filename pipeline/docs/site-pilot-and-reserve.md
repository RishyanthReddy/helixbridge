# Executed IL7Ra site pilot and adaptive reserve

This is a bounded research rehearsal, not an official submission workflow.
Use Python 3.12. The macOS system Python may lack tarfile extraction filters;
the isolated validation environment is the supported local test runtime.

The six-case RFD4 experiment is control/patch139/patch72 × seeds201/202, new
60-aa binders, ten hotspots/arm, target reference37–231, thinking_high. The
original adapters were preserved; `rfd4-site-pilot.py` changes only allowed seeds
and diagnostic labels from `rfd4-il7ra-seed.py`. Inputs and tasks are prepared by
`prepare-site-pilot-execution.py`. The first two cases form an implementation
gate. `prepare-site-esm-batch.py` and `site-pilot-stage-esm.py` use the qualified
immutable ESM runtime with one fresh prediction process per sequence.

`review-site-batch.py` runs the existing common review and independent Bio.PDB
pose/context audits. `assemble-site-pilot-review.py`, `diagnose-site-pilot.py`
and `audit-site-pilot-package.py` produce and independently check the complete
local comparison. The predeclared additional-run rule is frozen in execution
evidence. No case qualified; all outcomes remain visible.

The adaptive BoltzGen case is separate. Source6472b44, HF weights c1be29e and
chemical dataset c3d36fd are pinned in `assets.json`, alongside independent
upstream hashes. `install-boltzgen-reserve.sbatch` creates a separate environment;
`check-boltzgen-input.sbatch` checks native parser mapping before GPU submission.
`boltzgen-reserve-native.py` calls the upstream native task executor/configs,
without the full CLI pipeline's extra refold-weight download. It retains native
sampling schedules and records resolved configs. `run-boltzgen-reserve.py`
bounds native design/sequence tasks. The exported sequence passes through
`import-boltzgen-reserve.py`, both existing model adapters, and the common review.
The import retains raw files and creates an explicitly backbone-only generator
derivative, because inverse-fold sidechain placeholders are not packed atoms.

`prepare-boltzgen-evaluation.py`/`boltzgen-stage-esm.py` reuse the qualified ESM
archives. `review-boltzgen-reserve.py` performs canonical output transfer and
common/independent audits. `assemble-boltzgen-review.py` checks recorded task
hashes, raw PAE matrices, coordinate/sequence identity, scores, context, public
sequence overlap, reproduction and aggregate resource accounting.

Earth root is `/cfs/earth/scratch/mekalris/changjiang-2026`; source resides at
`src/pipeline`, raw evidence at `results/`. Source code is project-specific and
expects these audited inputs. Existing directories must not be reused as fresh
attempts. Native/model task JSONs and runner states, including exact commands,
are retained in the local `outputs/execution-evidence/` archive outside this
source repository. Do not rerun prepared tasks or reinitialize the ledger.

All GPU admissions used `submit-budgeted.py --ledger
.../results/site-diversity-pilot-v1/gpu-budget.json`, one L40S per job, maximum
two concurrently, 5,400 total GPU-seconds. The reserve had an additional 1,800
second bound. Actual combined use: 2,425 seconds; reserve402. Slurm allocated
duration includes setup and failures, rather than counting only kernel time.

The six-case local review uses a frozen original ledger snapshot. The reserve
stores the expanded final ledger separately as `gpu-budget-final.json`; this
preserves the original package's source hashes. Scheduler accounting covers all
eleven GPU jobs. No campaign was silently omitted from the total.

Checks run in the local isolated environment:

```sh
../work/validation-env/bin/python -m unittest discover -s tests -v
../work/validation-env/bin/python -m compileall -q scripts binder_campaign
```

Run independent package assemblers only into fresh versioned directories, with
`--workspace` pointing to the parent containing `pipeline`, `outputs` and `work`.
The seven new candidates are held. Existing research follow-ups remain
unchanged. Model confidence is not an affinity, experimental binding result,
glycan-tolerance result, global novelty certificate or official admission.
