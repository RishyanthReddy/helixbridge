#!/usr/bin/env bash
#SBATCH --job-name=cj-install-rfd4
#SBATCH --account=lsfm-edu-icls-grp-default
#SBATCH --partition=earth-3
#SBATCH --qos=earth-3.8h
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:00:00
#SBATCH --chdir=/cfs/earth/scratch/mekalris/changjiang-2026
#SBATCH --output=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.out
#SBATCH --error=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.err
set -euo pipefail
TASK_ROOT=/cfs/earth/scratch/mekalris/changjiang-2026
export TASK_ROOT
export XDG_CACHE_HOME="$TASK_ROOT/env/cache"
export UV_CACHE_DIR="$TASK_ROOT/env/cache/uv"
export UV_PYTHON_INSTALL_DIR="$TASK_ROOT/env/python"
export HF_HOME="$TASK_ROOT/data/weights/huggingface"
export HF_HUB_DISABLE_IMPLICIT_TOKEN=1
export WANDB_MODE=disabled
UV="$TASK_ROOT/env/bin/uv"
MANAGED_PYTHON=$("$UV" python find --managed-python 3.12.15)
PYTHON="$TASK_ROOT/env/rfd4/bin/python"
if [[ ! -x "$PYTHON" ]]; then "$UV" venv --python "$MANAGED_PYTHON" "$TASK_ROOT/env/rfd4"; fi
test "$(git -C "$TASK_ROOT/src/RFD4-Proteina" rev-parse HEAD)" = ddd934f7e6b86f7582ce487d5b19f6c526c644b5
# Generation only: no external oracle environments or optional CUDA metric packages.
# Torch/cu132 follows this source revision's qualified runtime.
"$UV" pip install --python "$PYTHON" --no-sources --torch-backend cu132 \
  'torch==2.14.1' -e "$TASK_ROOT/src/RFD4-Proteina"
"$UV" pip check --python "$PYTHON"
"$UV" pip freeze --python "$PYTHON" > "$TASK_ROOT/env/rfd4-freeze.txt"
"$TASK_ROOT/env/rfd4/bin/rfd4-generate" --help > "$TASK_ROOT/env/rfd4-generate-help.txt"
"$PYTHON" "$TASK_ROOT/src/pipeline/scripts/fetch-rfd4.py"
