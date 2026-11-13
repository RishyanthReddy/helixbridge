#!/usr/bin/env bash
#SBATCH --job-name=cj-mosaic-import
#SBATCH --partition=earth-3
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --chdir=/cfs/earth/scratch/mekalris/changjiang-2026/src/pipeline
#SBATCH --output=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.out
#SBATCH --error=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.err

set -euo pipefail
export TASK_ROOT=/cfs/earth/scratch/mekalris/changjiang-2026
"$TASK_ROOT/env/rfd4/bin/python" scripts/prepare-mosaic-evaluation.py
