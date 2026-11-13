#!/usr/bin/env bash
#SBATCH --job-name=cj-bg-install
#SBATCH --account=lsfm-edu-icls-grp-default
#SBATCH --partition=earth-3
#SBATCH --qos=earth-3.8h
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --chdir=/cfs/earth/scratch/mekalris/changjiang-2026
#SBATCH --output=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.out
#SBATCH --error=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.err
set -euo pipefail
export TASK_ROOT=/cfs/earth/scratch/mekalris/changjiang-2026
export XDG_CACHE_HOME="$TASK_ROOT/env/cache"
export UV_CACHE_DIR="$TASK_ROOT/env/cache/uv"
export HF_HOME="$TASK_ROOT/data/weights/huggingface"
export HF_HUB_DISABLE_IMPLICIT_TOKEN=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export PYTHONUNBUFFERED=1
UV="$TASK_ROOT/env/bin/uv"
PYTHON="$TASK_ROOT/env/boltzgen/bin/python"
test ! -e "$TASK_ROOT/env/boltzgen"
"$UV" venv --python 3.12 "$TASK_ROOT/env/boltzgen"
"$UV" pip install --python "$PYTHON" 'torch==2.11.0' 'numpy==2.3.5' 'numba==0.62.1' -e "$TASK_ROOT/src/BoltzGen"
"$UV" pip check --python "$PYTHON"
"$UV" pip freeze --python "$PYTHON" > "$TASK_ROOT/env/boltzgen-freeze.txt"
"$PYTHON" "$TASK_ROOT/src/pipeline/scripts/fetch-boltzgen-reserve.py"
"$PYTHON" -c 'import torch,boltzgen; from boltzgen.data.parse.schema import YamlDesignParser; from boltzgen.task.predict.predict import Predict; from boltzgen.task.predict.predict_solublempnn import PredictSolubleMPNN; print("BoltzGen CPU imports passed",torch.__version__,boltzgen.__file__)'
