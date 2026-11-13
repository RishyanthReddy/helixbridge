#!/usr/bin/env bash
#SBATCH --job-name=cj-fetch-boltz
#SBATCH --account=lsfm-edu-icls-grp-default
#SBATCH --partition=earth-3
#SBATCH --qos=earth-3.8h
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=01:00:00
#SBATCH --chdir=/cfs/earth/scratch/mekalris/changjiang-2026
#SBATCH --output=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.out
#SBATCH --error=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.err
set -euo pipefail
TASK_ROOT=/cfs/earth/scratch/mekalris/changjiang-2026
export TASK_ROOT
export XDG_CACHE_HOME="$TASK_ROOT/env/cache"
export HF_HOME="$TASK_ROOT/data/weights/huggingface"
export HF_HUB_DISABLE_IMPLICIT_TOKEN=1
# Reuse the audited download runtime: Boltz itself does not depend on HF Hub.
"$TASK_ROOT/env/esmfold2/bin/python" "$TASK_ROOT/src/pipeline/scripts/fetch-boltz.py"
