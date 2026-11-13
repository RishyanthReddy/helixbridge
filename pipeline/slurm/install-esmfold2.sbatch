#!/usr/bin/env bash
#SBATCH --job-name=cj-install-esm
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
export HF_HOME="$TASK_ROOT/data/weights/huggingface"
export HF_HUB_DISABLE_IMPLICIT_TOKEN=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
UV="$TASK_ROOT/env/bin/uv"
PYTHON="$TASK_ROOT/env/esmfold2/bin/python"
if [[ ! -x "$PYTHON" ]]; then "$UV" venv --python 3.12 "$TASK_ROOT/env/esmfold2"; fi
"$UV" pip install --python "$PYTHON" 'esm==3.4.1.post1'
"$UV" pip freeze --python "$PYTHON" > "$TASK_ROOT/env/esmfold2-freeze.txt"
"$PYTHON" - <<'PY'
import inspect
from esm.models.esmfold2 import EsmFold2Model, ESMFold2InputBuilder, ProteinInput, StructurePredictionInput
for cls in (EsmFold2Model, ESMFold2InputBuilder, ProteinInput, StructurePredictionInput):
    print(cls.__name__, inspect.getfile(cls), inspect.signature(cls))
print('fold:', inspect.signature(ESMFold2InputBuilder.fold))
PY
