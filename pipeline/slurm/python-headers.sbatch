#!/usr/bin/env bash
#SBATCH --job-name=cj-python-headers
#SBATCH --account=lsfm-edu-icls-grp-default
#SBATCH --partition=earth-3
#SBATCH --qos=earth-3.test
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:15:00
#SBATCH --chdir=/cfs/earth/scratch/mekalris/changjiang-2026
#SBATCH --output=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.out
#SBATCH --error=/cfs/earth/scratch/mekalris/changjiang-2026/logs/slurm/%x-%j.err
set -euo pipefail
TASK_ROOT=/cfs/earth/scratch/mekalris/changjiang-2026
export UV_PYTHON_INSTALL_DIR="$TASK_ROOT/env/python"
"$TASK_ROOT/env/bin/uv" python install 3.12.15
MANAGED_PYTHON=$("$TASK_ROOT/env/bin/uv" python find --managed-python 3.12.15)
"$MANAGED_PYTHON" -c 'import sysconfig; print(sysconfig.get_path("include"))' > "$TASK_ROOT/env/python-include.txt"
PYTHON_INCLUDE=$(cat "$TASK_ROOT/env/python-include.txt")
test -s "$PYTHON_INCLUDE/Python.h"
printf '#include <Python.h>\nint main(void){return 0;}\n' > "$TASK_ROOT/env/python-header-check.c"
gcc -fsyntax-only -I"$PYTHON_INCLUDE" "$TASK_ROOT/env/python-header-check.c"
"$MANAGED_PYTHON" --version
printf 'Compiler verified Python headers: %s\n' "$PYTHON_INCLUDE"
