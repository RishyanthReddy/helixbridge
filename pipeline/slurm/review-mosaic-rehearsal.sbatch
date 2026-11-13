#!/usr/bin/env bash
#SBATCH --job-name=cj-mosaic-review
#SBATCH --partition=earth-3
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=00:30:00
#SBATCH --chdir=/cfs/earth/scratch/mekalris/changjiang-2026/src/pipeline
#SBATCH --output=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.out
#SBATCH --error=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.err

set -euo pipefail
TASK_ROOT=/cfs/earth/scratch/mekalris/changjiang-2026
export TASK_ROOT
campaign=mosaic-il7ra
result="$TASK_ROOT/results/mosaic-il7ra-design-v1"
review="$TASK_ROOT/results/${campaign}-review-v1"
test ! -e "$review"
"$TASK_ROOT/env/rfd4/bin/python" -c \
  'import json, sys; states=[json.load(open(p)) for p in sys.argv[1:]]; assert all(s["status"] == "success" and s["exit_code"] == 0 for s in states), "A predictor stage failed"' \
  "$TASK_ROOT/results/${campaign}-esmfold2-v1/task-state.json" \
  "$TASK_ROOT/results/${campaign}-boltz-v1/task-state.json"
"$TASK_ROOT/env/rfd4/bin/python" scripts/review-rehearsal.py \
  "$review" "$result/candidates.json" "$campaign" > "$result/review.log" 2>&1
"$TASK_ROOT/env/boltz/bin/python" scripts/audit-pose-fit.py "$campaign" "$result/candidates.json" \
  > "$result/independent-pose.log" 2>&1
"$TASK_ROOT/env/boltz/bin/python" scripts/audit-il7ra-target-context.py "$campaign" "$result/candidates.json" \
  > "$result/target-context.log" 2>&1
test -s "$review/review.json"
test -s "$review/independent-pose-audit.json"
test -s "$review/target-context-audit.json"
echo "Mosaic common review, independent pose audit and target-context audit complete"
