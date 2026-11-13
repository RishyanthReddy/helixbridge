#!/usr/bin/env bash
#SBATCH --job-name=cj-install
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
export XDG_CACHE_HOME="$TASK_ROOT/env/cache"
export UV_CACHE_DIR="$TASK_ROOT/env/cache/uv"
export UV_PYTHON_INSTALL_DIR="$TASK_ROOT/env/python"
export BINDCRAFT_WEIGHTS="$TASK_ROOT/data/weights/bindcraft"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
mkdir -p "$XDG_CACHE_HOME" "$TASK_ROOT/env/bin" "$TASK_ROOT/data/weights"
if [[ ! -x "$TASK_ROOT/env/bin/uv" ]]; then
  curl -fLsS --max-time 120 https://astral.sh/uv/install.sh -o "$TASK_ROOT/env/uv-install.sh"
  UV_INSTALL_DIR="$TASK_ROOT/env/bin" UV_NO_MODIFY_PATH=1 sh "$TASK_ROOT/env/uv-install.sh"
fi
UV="$TASK_ROOT/env/bin/uv"
"$UV" --version
cd "$TASK_ROOT/src/BindCraft2"
if [[ ! -x .venv/bin/python ]]; then "$UV" venv --python 3.12 .venv; fi
"$UV" pip install --python .venv/bin/python -e '.[cuda13]'
"$UV" pip freeze --python .venv/bin/python > "$TASK_ROOT/env/bc2-freeze.txt"
.venv/bin/bindcraft fetch-weights
.venv/bin/python -m bindcraft.selfcheck cuda13
git rev-parse HEAD
.venv/bin/python --version
