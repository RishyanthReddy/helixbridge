#!/usr/bin/env bash
#SBATCH --job-name=cj-install-boltz
#SBATCH --account=lsfm-edu-icls-grp-default
#SBATCH --partition=earth-3
#SBATCH --qos=earth-3.8h
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --chdir=/cfs/earth/scratch/mekalris/changjiang-2026
#SBATCH --output=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.out
#SBATCH --error=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.err
set -euo pipefail
TASK_ROOT=/cfs/earth/scratch/mekalris/changjiang-2026
export XDG_CACHE_HOME="$TASK_ROOT/env/cache"
export UV_CACHE_DIR="$TASK_ROOT/env/cache/uv"
export UV_PYTHON_INSTALL_DIR="$TASK_ROOT/env/python"
export WANDB_MODE=disabled
UV="$TASK_ROOT/env/bin/uv"
MANAGED_PYTHON=$("$UV" python find --managed-python 3.12.15)
PYTHON="$TASK_ROOT/env/boltz/bin/python"
if [[ ! -x "$PYTHON" ]]; then "$UV" venv --python "$MANAGED_PYTHON" "$TASK_ROOT/env/boltz"; fi
# Plain installation avoids mixing the optional cu12 kernels with PyTorch cu13.
"$UV" pip install --python "$PYTHON" 'boltz==2.2.1'
"$UV" pip freeze --python "$PYTHON" > "$TASK_ROOT/env/boltz-freeze.txt"
"$TASK_ROOT/env/boltz/bin/boltz" predict --help > "$TASK_ROOT/env/boltz-predict-help.txt"
"$PYTHON" -c 'import importlib.metadata; print("boltz", importlib.metadata.version("boltz"))'
