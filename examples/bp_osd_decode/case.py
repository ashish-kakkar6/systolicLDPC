from __future__ import annotations

import runpy
import sys
from pathlib import Path

import numpy as np
from scipy.sparse import issparse


THIS_DIR = Path(__file__).resolve().parent
STIM_EXAMPLE = THIS_DIR / "stim_example.py"


def _dense_uint8(matrix) -> np.ndarray:
    if issparse(matrix):
        return matrix.toarray().astype(np.uint8)
    return np.asarray(matrix, dtype=np.uint8)


sys.path.insert(0, str(THIS_DIR))
ns = runpy.run_path(str(STIM_EXAMPLE))
sys.path.pop(0)

max_iter = int(ns.get("max_iter", 30))
check_mat = _dense_uint8(ns["mat"])
H = check_mat
logicals = _dense_uint8(ns["logicals"])
syndrome = np.asarray(ns["syndrome"], dtype=np.uint8)[0].reshape(-1)
sigma = syndrome.reshape(-1, 1)
actual_observables = np.asarray(ns["actual_observables"], dtype=np.uint8)[0].reshape(-1)

priors = np.asarray(ns["priors"], dtype=np.float64).reshape(-1)
prior_prob = np.clip(priors, np.finfo(np.float64).tiny, 1.0 - np.finfo(np.float64).eps)
prior_llr = np.log((1.0 - prior_prob) / prior_prob).astype(np.float64)
