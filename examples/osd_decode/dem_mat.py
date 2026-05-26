from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Tuple

import numpy as np
import stim
from scipy.sparse import csc_matrix


def iter_set_xor(set_list: list[list[int]]) -> FrozenSet[int]:
    out = set()
    for values in set_list:
        current = set(values)
        out = (out - current) | (current - out)
    return frozenset(out)


def dict_to_csc_matrix(
    elements_dict: Dict[int, FrozenSet[int]], shape: Tuple[int, int]
) -> csc_matrix:
    nnz = sum(len(values) for values in elements_dict.values())
    data = np.ones(nnz, dtype=np.uint8)
    row_ind = np.zeros(nnz, dtype=np.int64)
    col_ind = np.zeros(nnz, dtype=np.int64)

    i = 0
    for col, rows in elements_dict.items():
        for row in rows:
            row_ind[i] = row
            col_ind[i] = col
            i += 1

    return csc_matrix((data, (row_ind, col_ind)), shape=shape)


@dataclass
class DemMatrices:
    check_matrix: csc_matrix
    observables_matrix: csc_matrix
    edge_check_matrix: csc_matrix
    edge_observables_matrix: csc_matrix
    hyperedge_to_edge_matrix: csc_matrix
    priors: np.ndarray


def detector_error_model_to_check_matrices(
    dem: stim.DetectorErrorModel,
    allow_undecomposed_hyperedges: bool = False,
) -> DemMatrices:
    hyperedge_ids: Dict[FrozenSet[int], int] = {}
    edge_ids: Dict[FrozenSet[int], int] = {}
    hyperedge_obs_map: Dict[int, FrozenSet[int]] = {}
    edge_obs_map: Dict[int, FrozenSet[int]] = {}
    priors_dict: Dict[int, float] = {}
    hyperedge_to_edge: Dict[int, FrozenSet[int]] = {}

    def handle_error(
        prob: float, detectors: list[list[int]], observables: list[list[int]]
    ) -> None:
        hyperedge_dets = iter_set_xor(detectors)
        hyperedge_obs = iter_set_xor(observables)

        if hyperedge_dets not in hyperedge_ids:
            hyperedge_ids[hyperedge_dets] = len(hyperedge_ids)
            priors_dict[hyperedge_ids[hyperedge_dets]] = 0.0

        hid = hyperedge_ids[hyperedge_dets]
        hyperedge_obs_map[hid] = hyperedge_obs
        priors_dict[hid] = priors_dict[hid] * (1 - prob) + prob * (1 - priors_dict[hid])

        edge_list = []
        for det_group, obs_group in zip(detectors, observables):
            edge_dets = frozenset(det_group)
            edge_obs = frozenset(obs_group)

            if len(edge_dets) > 2:
                if not allow_undecomposed_hyperedges:
                    raise ValueError(
                        "A hyperedge error mechanism was found that was not decomposed into edges. "
                        "Call circuit.detector_error_model with decompose_errors=True."
                    )
                continue

            if edge_dets not in edge_ids:
                edge_ids[edge_dets] = len(edge_ids)
            eid = edge_ids[edge_dets]
            edge_list.append(eid)
            edge_obs_map[eid] = edge_obs

        if hid not in hyperedge_to_edge:
            hyperedge_to_edge[hid] = frozenset(edge_list)

    for instruction in dem.flattened():
        if instruction.type == "error":
            detectors: List[List[int]] = [[]]
            observables: List[List[int]] = [[]]
            prob = instruction.args_copy()[0]
            for target in instruction.targets_copy():
                if target.is_relative_detector_id():
                    detectors[-1].append(target.val)
                elif target.is_logical_observable_id():
                    observables[-1].append(target.val)
                elif target.is_separator():
                    detectors.append([])
                    observables.append([])
            handle_error(prob, detectors, observables)
        elif instruction.type in {"detector", "logical_observable"}:
            continue
        else:
            raise NotImplementedError(f"unsupported DEM instruction: {instruction.type}")

    check_matrix = dict_to_csc_matrix(
        {v: k for k, v in hyperedge_ids.items()},
        shape=(dem.num_detectors, len(hyperedge_ids)),
    )
    observables_matrix = dict_to_csc_matrix(
        hyperedge_obs_map,
        shape=(dem.num_observables, len(hyperedge_ids)),
    )
    priors = np.zeros(len(hyperedge_ids))
    for i, prob in priors_dict.items():
        priors[i] = prob

    hyperedge_to_edge_matrix = dict_to_csc_matrix(
        hyperedge_to_edge,
        shape=(len(edge_ids), len(hyperedge_ids)),
    )
    edge_check_matrix = dict_to_csc_matrix(
        {v: k for k, v in edge_ids.items()},
        shape=(dem.num_detectors, len(edge_ids)),
    )
    edge_observables_matrix = dict_to_csc_matrix(
        edge_obs_map,
        shape=(dem.num_observables, len(edge_ids)),
    )

    return DemMatrices(
        check_matrix=check_matrix,
        observables_matrix=observables_matrix,
        edge_check_matrix=edge_check_matrix,
        edge_observables_matrix=edge_observables_matrix,
        hyperedge_to_edge_matrix=hyperedge_to_edge_matrix,
        priors=priors,
    )
