#!/bin/bash
#SBATCH --job-name=cj-screen-audit
#SBATCH --partition=earth-3
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=00:30:00
#SBATCH --output=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.out

set -euo pipefail

PROJECT=/cfs/earth/scratch/mekalris/changjiang-2026
REVISION=9e1b81696da46835e9e9cde9a3da976e0abc92ab

"$PROJECT/env/rfd4/bin/python" \
  "$PROJECT/src/pipeline/scripts/analyze-screen-benchmark.py" \
  --data-root "$PROJECT/data/benchmarks/claude-protein-binder-design/$REVISION" \
  --output-dir "$PROJECT/results/screen-benchmark-audit-v4" \
  --bootstrap-repeats 2000 \
  --random-seed 20261102
