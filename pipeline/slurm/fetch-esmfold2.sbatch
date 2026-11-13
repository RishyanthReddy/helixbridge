#!/usr/bin/env bash
#SBATCH --job-name=cj-fetch-esm
#SBATCH --account=lsfm-edu-icls-grp-default
#SBATCH --partition=earth-3
#SBATCH --qos=earth-3.8h
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --chdir=/cfs/earth/scratch/mekalris/changjiang-2026
#SBATCH --output=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.out
#SBATCH --error=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.err
set -euo pipefail
export TASK_ROOT=/cfs/earth/scratch/mekalris/changjiang-2026
export HF_HOME="$TASK_ROOT/data/weights/huggingface"
export HF_HUB_DISABLE_IMPLICIT_TOKEN=1
export PYTHONUNBUFFERED=1
"$TASK_ROOT/env/esmfold2/bin/python" "$TASK_ROOT/src/pipeline/scripts/fetch-esmfold2.py"
