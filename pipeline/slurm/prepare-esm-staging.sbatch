#!/usr/bin/env bash
#SBATCH --job-name=cj-esm-stage-cpu
#SBATCH --account=lsfm-edu-icls-grp-default
#SBATCH --partition=earth-3
#SBATCH --qos=earth-3.8h
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:30:00
#SBATCH --chdir=/cfs/earth/scratch/mekalris/changjiang-2026/src/pipeline
#SBATCH --output=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.out
#SBATCH --error=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.err
set -euo pipefail
export TASK_ROOT=/cfs/earth/scratch/mekalris/changjiang-2026
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export PYTHONUNBUFFERED=1
"$TASK_ROOT/env/rfd4/bin/python" scripts/prepare-esm-staging.py
"$TASK_ROOT/env/rfd4/bin/python" scripts/stage-esm-runtime.py qualify
