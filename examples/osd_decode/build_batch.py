#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np

from common import (
    DEFAULT_STIM_MODULE,
    case_timestamp,
    compute_batch_id,
    ensure_batch_dirs,
    load_python_namespace,
    next_pow2,
    print_batch_report,
    quantize_scores_u4,
    render_tb,
    save_manifest,
    save_meta,
    select_independent_columns,
    sha256_file,
    stable_sorted_indices,
    to_float32_vector,
    to_uint8_dense,
    update_latest_symlink,
    write_reversed_rows,
    write_sigma_column,
    write_u4_hex,
    write_u4_scalar_hex,
)


TOP_P_MULTIPLE = 3


def _load_stim_batch(module_path: Path, shots: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    ns = load_python_namespace(module_path)

    if "dem_matrices" not in ns:
        raise KeyError("stim_example.py must define `dem_matrices`")
    if "circuit" in ns:
        sampler = ns["circuit"].compile_detector_sampler()
    elif "sampler" in ns:
        sampler = ns["sampler"]
    else:
        raise KeyError("stim_example.py must define `circuit` or `sampler`")

    h_mat = to_uint8_dense(ns["dem_matrices"].check_matrix, "dem_matrices.check_matrix")
    logicals = to_uint8_dense(ns["dem_matrices"].observables_matrix, "dem_matrices.observables_matrix")
    priors = to_float32_vector(ns["dem_matrices"].priors, "dem_matrices.priors")

    syndrome, actual_observables = sampler.sample(
        shots=int(shots),
        separate_observables=True,
    )

    sigma_all = np.asarray(syndrome, dtype=np.uint8)
    actual_all = np.asarray(actual_observables, dtype=np.uint8)
    if sigma_all.ndim == 1:
        sigma_all = sigma_all.reshape(1, -1)
    if actual_all.ndim == 1:
        actual_all = actual_all.reshape(1, -1)

    sigma_all = to_uint8_dense(sigma_all, "syndrome")
    actual_all = to_uint8_dense(actual_all, "actual_observables")
    return h_mat, logicals, priors, sigma_all, actual_all


def _shot_name(shot_index: int) -> str:
    return f"shot_{shot_index:06d}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", type=Path, default=DEFAULT_STIM_MODULE)
    parser.add_argument("--shots", type=int, default=1000)
    parser.add_argument("--batches-root", type=Path, default=Path(__file__).resolve().parent / "batches")
    args = parser.parse_args()

    if args.shots < 1:
        raise ValueError("--shots must be positive")

    h_mat, logicals, priors, sigma_all, actual_all = _load_stim_batch(args.module, int(args.shots))
    m_rows, n_cols = h_mat.shape
    if sigma_all.shape != (int(args.shots), m_rows):
        raise ValueError(
            f"sampled syndrome has shape {sigma_all.shape}, expected {(int(args.shots), m_rows)}"
        )
    if actual_all.shape[1] != logicals.shape[0]:
        raise ValueError(
            f"actual_observables width {actual_all.shape[1]} does not match logical count {logicals.shape[0]}"
        )

    initial_estimate = -np.log(np.clip(priors, np.finfo(np.float32).tiny, 1.0)).astype(np.float32)
    cutoff = np.float32(np.median(initial_estimate) + 1.0)
    initial_estimate_u4, cutoff_u4, quant_meta = quantize_scores_u4(initial_estimate, cutoff)

    n_pad = next_pow2(n_cols)
    top_p_max = min(n_pad, TOP_P_MULTIPLE * m_rows)
    sentinel_u4 = np.uint8(15)
    estimate_padded_u4 = np.full(n_pad, sentinel_u4, dtype=np.uint8)
    estimate_padded_u4[:n_cols] = initial_estimate_u4

    sorted_indices_sw = stable_sorted_indices(estimate_padded_u4)
    sorted_scores_sw = estimate_padded_u4[sorted_indices_sw]
    filtered_mask = (sorted_indices_sw < n_cols) & (sorted_scores_sw < cutoff_u4)
    filtered_indices_sw = sorted_indices_sw[filtered_mask].astype(np.int64, copy=False)
    selected_indices_sw = select_independent_columns(h_mat, filtered_indices_sw)
    rank_lookup_sw = np.empty(n_pad, dtype=np.int64)
    rank_lookup_sw[sorted_indices_sw] = np.arange(n_pad, dtype=np.int64)
    required_top_p_sw = (
        int(np.max(rank_lookup_sw[selected_indices_sw])) + 1 if selected_indices_sw.size else 0
    )
    top_p_sufficient_sw = bool(required_top_p_sw <= top_p_max)
    if not top_p_sufficient_sw:
        raise ValueError(
            "top-P ranker window is too small for this batch: "
            f"required_top_p_sw={required_top_p_sw} exceeds top_p_max={top_p_max}. "
            "Increase TOP_P or change the case because some ranked columns fail the independence test."
        )

    batch_id = compute_batch_id(
        module_path=args.module,
        h_mat=h_mat,
        sigmas=sigma_all,
        actual_observables=actual_all,
        estimate_u4=initial_estimate_u4,
        cutoff_u4=int(cutoff_u4),
        top_p_max=int(top_p_max),
    )

    batches_root = args.batches_root.expanduser().resolve()
    temp_batch_dir = batches_root / f".tmp_{batch_id}"
    final_batch_dir = batches_root / batch_id
    if temp_batch_dir.exists():
        shutil.rmtree(temp_batch_dir)
    paths = ensure_batch_dirs(temp_batch_dir)

    tb_template = (Path(__file__).resolve().parent / "tb_osd_decode.sv").read_text()
    tb_path = paths["generated"] / "tb_osd_decode.sv"
    tb_path.write_text(
        render_tb(
            tb_template,
            m_max=int(m_rows),
            n_max=int(n_cols),
            n_pad_max=int(n_pad),
        )
    )

    np.save(temp_batch_dir / "H.npy", h_mat)
    np.save(temp_batch_dir / "logicals.npy", logicals)
    np.save(temp_batch_dir / "initial_estimate.npy", initial_estimate)
    np.save(temp_batch_dir / "initial_estimate_u4.npy", initial_estimate_u4)
    np.save(temp_batch_dir / "estimate_padded_u4.npy", estimate_padded_u4)
    np.save(temp_batch_dir / "sigmas.npy", sigma_all)
    np.save(temp_batch_dir / "actual_observables.npy", actual_all)
    np.save(temp_batch_dir / "selected_indices_sw.npy", selected_indices_sw)
    np.save(temp_batch_dir / "cutoff.npy", np.array([cutoff], dtype=np.float32))
    np.save(temp_batch_dir / "cutoff_u4.npy", np.array([cutoff_u4], dtype=np.uint8))

    write_reversed_rows(h_mat, paths["problem"] / "h_rows.mem")
    write_u4_hex(estimate_padded_u4, paths["problem"] / "estimate.hex")
    write_u4_scalar_hex(int(cutoff_u4), paths["problem"] / "cutoff.hex")

    for shot_index in range(int(args.shots)):
        shot_dir = paths["shots"] / _shot_name(shot_index)
        shot_problem_dir = shot_dir / "problem"
        shot_out_dir = shot_dir / "out"
        shot_problem_dir.mkdir(parents=True, exist_ok=True)
        shot_out_dir.mkdir(parents=True, exist_ok=True)
        write_sigma_column(sigma_all[shot_index].reshape(-1, 1), shot_problem_dir / "sigma.mem")

    timeout_cycles = int((3 * n_pad) + max(64, m_rows) + (6 * m_rows) + 64)
    meta = {
        "batch_id": batch_id,
        "module": str(args.module.resolve()),
        "shots": int(args.shots),
        "M_MAX": int(m_rows),
        "N_MAX": int(n_cols),
        "N_PAD_MAX": int(n_pad),
        "top_p_max": int(top_p_max),
        "required_top_p_sw": int(required_top_p_sw),
        "top_p_sufficient_sw": bool(top_p_sufficient_sw),
        "cutoff": float(cutoff),
        "cutoff_u4": int(cutoff_u4),
        "timeout_cycles": timeout_cycles,
        "logical_observable_count": int(logicals.shape[0]),
        "score_quantization": {
            "kind": "uniform_u4",
            "low": quant_meta["low"],
            "high": quant_meta["high"],
            "sentinel": int(sentinel_u4),
        },
        "files": {
            "h_rows_mem": str((final_batch_dir / "problem" / "h_rows.mem").resolve()),
            "estimate_hex": str((final_batch_dir / "problem" / "estimate.hex").resolve()),
            "cutoff_hex": str((final_batch_dir / "problem" / "cutoff.hex").resolve()),
            "tb_sv": str((final_batch_dir / "generated" / "tb_osd_decode.sv").resolve()),
            "sigmas_npy": str((final_batch_dir / "sigmas.npy").resolve()),
            "actual_observables_npy": str((final_batch_dir / "actual_observables.npy").resolve()),
        },
    }
    save_meta(temp_batch_dir / "meta.json", meta)

    manifest = {
        "workflow": "osd_decode_batch",
        "batch_id": batch_id,
        "created_at": case_timestamp(),
        "module": str(args.module.resolve()),
        "shots": int(args.shots),
        "M_MAX": int(m_rows),
        "N_MAX": int(n_cols),
        "N_PAD_MAX": int(n_pad),
        "sim_default": "iverilog",
        "stages": {
            "built": True,
            "ran": False,
            "read": False,
        },
        "files": {
            "H_npy": "H.npy",
            "logicals_npy": "logicals.npy",
            "initial_estimate_npy": "initial_estimate.npy",
            "initial_estimate_u4_npy": "initial_estimate_u4.npy",
            "sigmas_npy": "sigmas.npy",
            "actual_observables_npy": "actual_observables.npy",
            "selected_indices_sw_npy": "selected_indices_sw.npy",
            "h_rows_mem": "problem/h_rows.mem",
            "estimate_hex": "problem/estimate.hex",
            "cutoff_hex": "problem/cutoff.hex",
            "tb_sv": "generated/tb_osd_decode.sv",
        },
        "hashes": {
            "H_npy": sha256_file(temp_batch_dir / "H.npy"),
            "logicals_npy": sha256_file(temp_batch_dir / "logicals.npy"),
            "initial_estimate_npy": sha256_file(temp_batch_dir / "initial_estimate.npy"),
            "initial_estimate_u4_npy": sha256_file(temp_batch_dir / "initial_estimate_u4.npy"),
            "sigmas_npy": sha256_file(temp_batch_dir / "sigmas.npy"),
            "actual_observables_npy": sha256_file(temp_batch_dir / "actual_observables.npy"),
            "selected_indices_sw_npy": sha256_file(temp_batch_dir / "selected_indices_sw.npy"),
            "h_rows_mem": sha256_file(paths["problem"] / "h_rows.mem"),
            "estimate_hex": sha256_file(paths["problem"] / "estimate.hex"),
            "cutoff_hex": sha256_file(paths["problem"] / "cutoff.hex"),
            "tb_sv": sha256_file(tb_path),
        },
    }
    save_manifest(temp_batch_dir / "manifest.json", manifest)

    batches_root.mkdir(parents=True, exist_ok=True)
    if final_batch_dir.exists():
        shutil.rmtree(final_batch_dir)
    temp_batch_dir.rename(final_batch_dir)
    update_latest_symlink(batches_root, final_batch_dir)

    print_batch_report(
        final_batch_dir,
        "stage: build",
        f"shots={int(args.shots)} M={m_rows} N={n_cols} N_PAD={n_pad}",
        f"cutoff_u4={int(cutoff_u4)} top_p_max={top_p_max} required_top_p_sw={required_top_p_sw}",
    )


if __name__ == "__main__":
    main()
