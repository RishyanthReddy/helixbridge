#!/usr/bin/env bash
#SBATCH --job-name=cj-seed-review
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
seed="${1:?Pass seed 43 or 44}"
case "$seed" in
  43|44) ;;
  *) echo "Unexpected seed" >&2; exit 2 ;;
esac
campaign="rfd4-il7ra-high-s${seed}"
result="$TASK_ROOT/results/${campaign}-v1"
review="$TASK_ROOT/results/${campaign}-review-v1"
test ! -e "$review"
test -s "$result/starting-input-audit.json"
"$TASK_ROOT/env/rfd4/bin/python" -c \
  'import json, sys; states=[json.load(open(p)) for p in sys.argv[1:]]; assert all(s["status"] == "success" and s["exit_code"] == 0 for s in states), "A predictor stage failed"' \
  "$TASK_ROOT/results/${campaign}-esmfold2-v1/task-state.json" \
  "$TASK_ROOT/results/${campaign}-boltz-v1/task-state.json"
"$TASK_ROOT/env/rfd4/bin/python" scripts/review-rehearsal.py \
  "$review" "$result/candidates.json" "$campaign" > "$result/review.log" 2>&1
"$TASK_ROOT/env/boltz/bin/python" scripts/audit-pose-fit.py "$campaign" \
  > "$result/independent-pose.log" 2>&1
cp -n "$result/starting-input-audit.json" "$review/starting-input-audit.json"
test -s "$review/review.json"
test -s "$review/independent-pose-audit.json"
test -s "$review/starting-input-audit.json"
echo "Seed $seed: common review and independent pose audit complete"
