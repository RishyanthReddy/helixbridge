#!/usr/bin/env bash
#SBATCH --job-name=cj-mosaic-smoke
#SBATCH --account=lsfm-edu-icls-grp-default
#SBATCH --partition=earth-4
#SBATCH --qos=earth-4.8h
#SBATCH --gres=gpu:l40s:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=01:00:00
#SBATCH --chdir=/cfs/earth/scratch/mekalris/changjiang-2026/src/pipeline
#SBATCH --output=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.out
#SBATCH --error=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.err
set -euo pipefail
TASK_ROOT=/cfs/earth/scratch/mekalris/changjiang-2026
export TASK_ROOT
export MOSAIC_CACHE_DIR="$TASK_ROOT/env/cache/mosaic"
export XDG_CACHE_HOME="$TASK_ROOT/env/cache"
export HF_HUB_DISABLE_IMPLICIT_TOKEN=1
export WANDB_MODE=disabled
export OMP_NUM_THREADS=8
export XLA_PYTHON_CLIENT_PREALLOCATE=false
export PYTHONUNBUFFERED=1
"$TASK_ROOT/env/mosaic-boltz2/bin/python" scripts/mosaic-il7ra.py \
  --mode smoke --output "$TASK_ROOT/results/mosaic-il7ra-smoke-v1"
