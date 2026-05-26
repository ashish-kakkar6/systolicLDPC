from __future__ import annotations
import runpy
from pathlib import Path

import stim

THIS_DIR = Path(__file__).resolve().parent
DEM_MAT_NS = runpy.run_path(str(THIS_DIR.parent / "osd_decode" / "dem_mat.py"))
detector_error_model_to_check_matrices = DEM_MAT_NS["detector_error_model_to_check_matrices"]

P = 0.05
DISTANCE = 5
ROUNDS = 5
seed = 123
N_SHOTS = 1
max_iter = 30

circuit = stim.Circuit.generated(
    "surface_code:rotated_memory_x",
    distance=DISTANCE,
    rounds=ROUNDS,
    after_clifford_depolarization=P,
    before_round_data_depolarization=P,
    after_reset_flip_probability=P,
    before_measure_flip_probability=P,
)

model = circuit.detector_error_model(decompose_errors=True)
dem_matrices = detector_error_model_to_check_matrices(model)
mat = dem_matrices.check_matrix
priors = dem_matrices.priors
logicals = dem_matrices.observables_matrix

sampler = circuit.compile_detector_sampler(seed=seed)
syndrome, actual_observables = sampler.sample(
    shots=N_SHOTS,
    separate_observables=True,
)
