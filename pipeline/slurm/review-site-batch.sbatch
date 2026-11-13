#!/usr/bin/env bash
#SBATCH --job-name=cj-site-review
#SBATCH --partition=earth-3
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=00:20:00
#SBATCH --chdir=/cfs/earth/scratch/mekalris/changjiang-2026/src/pipeline
#SBATCH --output=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.out
#SBATCH --error=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.err
set -euo pipefail
export TASK_ROOT=/cfs/earth/scratch/mekalris/changjiang-2026
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
"$TASK_ROOT/env/rfd4/bin/python" scripts/review-site-batch.py "${1:?Pass gate or main}"
