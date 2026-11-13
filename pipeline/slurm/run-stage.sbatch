#!/usr/bin/env bash
#SBATCH --job-name=cj-stage
#SBATCH --account=lsfm-edu-icls-grp-default
#SBATCH --partition=earth-4
#SBATCH --qos=earth-4.8h
#SBATCH --gres=gpu:l40s:1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --signal=B:TERM@120
#SBATCH --chdir=/cfs/earth/scratch/mekalris/changjiang-2026/src/pipeline
#SBATCH --output=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.out
#SBATCH --error=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.err
set -euo pipefail
TASK_ROOT=/cfs/earth/scratch/mekalris/changjiang-2026
export TASK_ROOT
export XDG_CACHE_HOME="$TASK_ROOT/env/cache"
export HF_HOME="$TASK_ROOT/data/weights/huggingface"
export HF_HUB_DISABLE_IMPLICIT_TOKEN=1
export BINDCRAFT_WEIGHTS="$TASK_ROOT/data/weights/bindcraft"
export BINDCRAFT_WORKERS_PER_GPU=1
export BINDCRAFT_DESIGN_WORKERS=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export PYTHONUNBUFFERED=1
if [[ -f "$TASK_ROOT/env/python-include.txt" ]]; then
  PYTHON_INCLUDE=$(cat "$TASK_ROOT/env/python-include.txt")
  test -s "$PYTHON_INCLUDE/Python.h"
  export CPATH="$PYTHON_INCLUDE${CPATH:+:$CPATH}"
fi
TASK_SPEC="${1:?Pass the task JSON path}"
TASK_PID=""
(
  while true; do
    nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv,noheader
    sleep 10
  done
) > "$TASK_ROOT/logs/slurm/${SLURM_JOB_ID}-gpu.csv" &
MONITOR_PID=$!
cleanup() { kill "$MONITOR_PID" 2>/dev/null || true; }
terminate() {
  if [[ -n "$TASK_PID" ]]; then
    kill -TERM "$TASK_PID" 2>/dev/null || true
    wait "$TASK_PID" || true
  fi
  exit 143
}
trap cleanup EXIT
trap terminate TERM INT
"$TASK_ROOT/src/BindCraft2/.venv/bin/python" -m binder_campaign run "$TASK_SPEC" &
TASK_PID=$!
wait "$TASK_PID"
