#!/usr/bin/env bash
#SBATCH --job-name=cj-target-context
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
"$TASK_ROOT/env/boltz/bin/python" scripts/audit-il7ra-target-context.py "rfd4-il7ra-high-s${seed}"
