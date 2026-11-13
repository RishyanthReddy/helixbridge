#!/usr/bin/env bash
#SBATCH --job-name=cj-recovery-audit
#SBATCH --account=lsfm-edu-icls-grp-default
#SBATCH --partition=earth-3
#SBATCH --qos=earth-3.test
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --chdir=/cfs/earth/scratch/mekalris/changjiang-2026/src/pipeline
#SBATCH --output=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.out
#SBATCH --error=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.err
set -euo pipefail
export TASK_ROOT=/cfs/earth/scratch/mekalris/changjiang-2026
"$TASK_ROOT/src/BindCraft2/.venv/bin/python" scripts/audit-stage-recovery.py "$@"
