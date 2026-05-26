from __future__ import annotations

import stim

from dem_mat import detector_error_model_to_check_matrices


P = 0.03
N_SHOTS = 1

circuit = stim.Circuit.generated(
    "surface_code:rotated_memory_x",
    distance=3,
    rounds=3,
    after_clifford_depolarization=P,
    before_round_data_depolarization=P,
    after_reset_flip_probability=P,
    before_measure_flip_probability=P,
)

model = circuit.detector_error_model(decompose_errors=True)
sampler = circuit.compile_detector_sampler()
syndrome, actual_observables = sampler.sample(
    shots=N_SHOTS,
    separate_observables=True,
)

dem_matrices = detector_error_model_to_check_matrices(model)
mat = dem_matrices.check_matrix
priors = dem_matrices.priors
logicals = dem_matrices.observables_matrix


