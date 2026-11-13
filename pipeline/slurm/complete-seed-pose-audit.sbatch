#!/usr/bin/env bash
#SBATCH --job-name=cj-pose-retry
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
test -s "$review/review.json"
test -s "$review/export-audit.json"
test -s "$review/REHEARSAL_ONLY.csv"
test -s "$result/starting-input-audit.json"
test ! -e "$review/independent-pose-audit.json"
test ! -e "$review/starting-input-audit.json"
test ! -e "$result/independent-pose-retry.log"
"$TASK_ROOT/env/boltz/bin/python" scripts/audit-pose-fit.py "$campaign" \
  > "$result/independent-pose-retry.log" 2>&1
cp -n "$result/starting-input-audit.json" "$review/starting-input-audit.json"
test -s "$review/independent-pose-audit.json"
test -s "$review/starting-input-audit.json"
echo "Seed $seed: independent pose audit completed using existing prediction/review artifacts"
