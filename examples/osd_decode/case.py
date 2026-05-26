from __future__ import annotations

import runpy
import sys
from pathlib import Path

import numpy as np
from scipy.sparse import issparse


THIS_DIR = Path(__file__).resolve().parent
STIM_DIR = THIS_DIR
STIM_EXAMPLE = THIS_DIR / "stim_example.py"

sys.path.insert(0, str(STIM_DIR))
ns = runpy.run_path(str(STIM_EXAMPLE))
sys.path.pop(0)

mat = ns["mat"]
H = mat.toarray().astype(np.uint8) if issparse(mat) else np.asarray(mat, dtype=np.uint8)
sigma = np.asarray(ns["syndrome"], dtype=np.uint8)[0].reshape(-1, 1)
actual_observables = np.asarray(ns["actual_observables"], dtype=np.uint8)[0]
if "logicals" in ns:
    logicals_src = ns["logicals"]
elif "dem_matrices" in ns:
    logicals_src = ns["dem_matrices"].observables_matrix
else:
    raise KeyError(
        "stim_example.py must define `logicals` or `dem_matrices.observables_matrix`"
    )
logicals = (
    logicals_src.toarray().astype(np.uint8)
    if issparse(logicals_src)
    else np.asarray(logicals_src, dtype=np.uint8)
)

if "priors" in ns:
    priors = np.asarray(ns["priors"], dtype=np.float32)
elif "dem_matrices" in ns:
    priors = np.asarray(ns["dem_matrices"].priors, dtype=np.float32)
else:
    raise KeyError("stim_example.py must define `priors` or `dem_matrices.priors`")

# Lower score means more likely. Use negative log-probability as the ranking score.
initial_estimate = -np.log(np.clip(priors, np.finfo(np.float32).tiny, 1.0)).astype(np.float32)
cutoff = np.float32(np.median(initial_estimate) + 1.0)
