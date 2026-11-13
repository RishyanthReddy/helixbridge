#!/usr/bin/env bash
#SBATCH --job-name=cj-robust-review
#SBATCH --partition=earth-3
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=00:15:00
#SBATCH --chdir=/cfs/earth/scratch/mekalris/changjiang-2026/src/pipeline
#SBATCH --output=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.out
#SBATCH --error=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.err
set -euo pipefail
export TASK_ROOT=/cfs/earth/scratch/mekalris/changjiang-2026
records="$TASK_ROOT/results/rfd4-il7ra-high-s43-v1/candidates.json"
for seed in 1 2; do
  campaign="rfd4-il7ra-high-s43-eval-s${seed}"
  "$TASK_ROOT/env/rfd4/bin/python" -c \
    'import json,sys; s=[json.load(open(p)) for p in sys.argv[1:]]; assert all(r["status"]=="success" and r["exit_code"]==0 for r in s)' \
    "$TASK_ROOT/results/${campaign}-esmfold2-v1/task-state.json" \
    "$TASK_ROOT/results/${campaign}-boltz-v1/task-state.json"
  "$TASK_ROOT/env/rfd4/bin/python" scripts/review-rehearsal.py \
    "$TASK_ROOT/results/${campaign}-review-v1" "$records" "$campaign"
  "$TASK_ROOT/env/boltz/bin/python" scripts/audit-pose-fit.py "$campaign" "$records"
done
