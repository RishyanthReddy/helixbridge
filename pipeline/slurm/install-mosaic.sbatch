#!/usr/bin/env bash
#SBATCH --job-name=cj-install-mosaic
#SBATCH --account=lsfm-edu-icls-grp-default
#SBATCH --partition=earth-3
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --chdir=/cfs/earth/scratch/mekalris/changjiang-2026
#SBATCH --output=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.out
#SBATCH --error=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.err
set -euo pipefail
TASK_ROOT=/cfs/earth/scratch/mekalris/changjiang-2026
export XDG_CACHE_HOME="$TASK_ROOT/env/cache"
export UV_CACHE_DIR="$TASK_ROOT/env/cache/uv"
export UV_PYTHON_INSTALL_DIR="$TASK_ROOT/env/python"
export HF_HUB_DISABLE_IMPLICIT_TOKEN=1
export WANDB_MODE=disabled
UV="$TASK_ROOT/env/bin/uv"
MOSAIC_PYTHON="$TASK_ROOT/env/mosaic-boltz2/bin/python"
if [[ ! -x "$MOSAIC_PYTHON" ]]; then
  "$UV" venv --python "$("$UV" python find --managed-python 3.12.15)" "$TASK_ROOT/env/mosaic-boltz2"
fi
test "$(git -C "$TASK_ROOT/src/mosaic-runtime" rev-parse HEAD)" = 5937f37164bcb28bc6f1000f10134145438e5971
test "$(git -C "$TASK_ROOT/src/joltz" rev-parse HEAD)" = ed0f04257dac85bd4b7bf45521cc280f86d38ded
test "$(git -C "$TASK_ROOT/src/mosaic-boltz" rev-parse HEAD)" = 7ea718a1440ecbe8e2418317192b501544147edd
# Only the Boltz2/ProteinMPNN runtime is qualified. Optional Mosaic backends remain absent.
"$UV" pip install --python "$MOSAIC_PYTHON" --index-url https://download.pytorch.org/whl/cpu 'torch==2.11.0'
"$UV" pip install --python "$MOSAIC_PYTHON" --no-sources \
  'jax[cuda12]==0.11.1' 'equinox>=0.13.0' 'dm-haiku>=0.0.13' 'optax>=0.2.4' \
  'ml-collections>=1.0.0' -e "$TASK_ROOT/src/mosaic-boltz" -e "$TASK_ROOT/src/joltz"
"$UV" pip install --python "$MOSAIC_PYTHON" --no-deps -e "$TASK_ROOT/src/mosaic-runtime"
"$UV" pip freeze --python "$MOSAIC_PYTHON" > "$TASK_ROOT/env/mosaic-boltz2-freeze.txt"
"$MOSAIC_PYTHON" -c 'from mosaic.models.boltz2 import Boltz2; from mosaic.proteinmpnn.mpnn import load_mpnn_sol; from mosaic.optimizers import simplex_APGM; print("Scoped Boltz2/ProteinMPNN imports passed")'
