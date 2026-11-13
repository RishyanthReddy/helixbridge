#!/usr/bin/env bash
#SBATCH --job-name=cj-rfd4-coordinate
#SBATCH --partition=earth-3
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=01:15:00
#SBATCH --chdir=/cfs/earth/scratch/mekalris/changjiang-2026/src/pipeline
#SBATCH --output=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.out
#SBATCH --error=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.err
set -euo pipefail
export TASK_ROOT=/cfs/earth/scratch/mekalris/changjiang-2026
"$TASK_ROOT/env/rfd4/bin/python" scripts/coordinate-controlled-campaign.py
