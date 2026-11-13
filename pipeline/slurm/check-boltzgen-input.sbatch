#!/usr/bin/env bash
#SBATCH --job-name=cj-bg-input
#SBATCH --partition=earth-3
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:20:00
#SBATCH --chdir=/cfs/earth/scratch/mekalris/changjiang-2026/src/pipeline
#SBATCH --output=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.out
#SBATCH --error=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.err
set -euo pipefail
export TASK_ROOT=/cfs/earth/scratch/mekalris/changjiang-2026
export HF_HUB_DISABLE_IMPLICIT_TOKEN=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
"$TASK_ROOT/env/boltzgen/bin/python" scripts/prepare-boltzgen-input.py
