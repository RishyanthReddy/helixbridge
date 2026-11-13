"""CPU-safe import and CCD probe; never loads neural-network parameters."""
import json
import os
from pathlib import Path
import sys
import time

started = time.monotonic()
import numpy
import torch
import biotite
import scipy
import esm
from esm.models.esmfold2 import EsmFold2Model, ESMFold2InputBuilder, load_ccd

imported = time.monotonic()
expected = Path(sys.prefix).resolve()
paths = {m.__name__: str(Path(m.__file__).resolve()) for m in (numpy, torch, biotite, scipy, esm)}
for value in paths.values():
    Path(value).relative_to(expected)
ccd = load_ccd(cache_dir=Path(sys.argv[1]))
finished = time.monotonic()
if not all(aa in ccd for aa in ('ALA', 'GLY', 'CYS', 'ASN')):
    raise ValueError('CCD protein components missing')
print(json.dumps({'status': 'passed_import_and_ccd_only', 'python': sys.executable,
    'prefix': str(expected), 'module_paths': paths, 'torch_version': torch.__version__,
    'cuda_available': torch.cuda.is_available(), 'import_seconds': imported - started,
    'ccd_load_seconds': finished - imported, 'ccd_entries': len(ccd),
    'nn_parameters_loaded': False, 'inference_run': False}), flush=True)
