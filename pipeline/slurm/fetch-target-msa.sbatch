#!/usr/bin/env bash
#SBATCH --job-name=cj-target-msa
#SBATCH --account=lsfm-edu-icls-grp-default
#SBATCH --partition=earth-3
#SBATCH --qos=earth-3.test
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
#SBATCH --chdir=/cfs/earth/scratch/mekalris/changjiang-2026/src/pipeline
#SBATCH --output=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.out
#SBATCH --error=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.err
set -euo pipefail
export PYTHONUNBUFFERED=1
/cfs/earth/scratch/mekalris/changjiang-2026/env/esmfold2/bin/python scripts/fetch-target-msa.py \
  --manifest data/targets/il7ra/manifest.json --output data/targets/il7ra/msa
