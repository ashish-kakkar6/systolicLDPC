#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np

from common import (
    compute_case_id,
    case_timestamp,
    DEFAULT_CASE_MODULE,
    ensure_dirs,
    gf2_solve,
    load_python_namespace,
    next_pow2,
    print_case_report,
    quantize_scores_u4,
    render_tb,
    save_meta,
    save_manifest,
    select_independent_columns,
    stable_sorted_indices,
    to_float32_vector,
    to_uint8_dense,
    sha256_file,
    update_latest_symlink,
    write_u4_hex,
    write_u4_scalar_hex,
    write_reversed_rows,
    write_sigma_column,
)

TOP_P_MULTIPLE = 3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", type=Path, default=DEFAULT_CASE_MODULE)
    parser.add_argument("--cases-root", type=Path, default=Path(__file__).resolve().parent / "cases")
    parser.add_argument("--h-name", default="H")
    parser.add_argument("--sigma-name", default="sigma")
    parser.add_argument("--estimate-name", default="initial_estimate")
    parser.add_argument("--cutoff-name", default="cutoff")
    args = parser.parse_args()

    ns = load_python_namespace(args.module)
    required = [args.h_name, args.sigma_name, args.estimate_name, args.cutoff_name]
    missing = [name for name in required if name not in ns]
    if missing:
        raise ValueError(f"{args.module} is missing {missing}")

    h_mat = to_uint8_dense(ns[args.h_name], args.h_name)
    sigma = to_uint8_dense(ns[args.sigma_name], args.sigma_name)
    logicals = to_uint8_dense(ns["logicals"], "logicals")
    actual_observables = to_uint8_dense(
        np.asarray(ns["actual_observables"], dtype=np.uint8).reshape(1, -1),
        "actual_observables",
    )[0]
    initial_estimate = to_float32_vector(ns[args.estimate_name], args.estimate_name)
    cutoff = np.float32(ns[args.cutoff_name])

    m_rows, n_cols = h_mat.shape
    if sigma.shape != (m_rows, 1):
        raise ValueError(f"{args.sigma_name} must have shape {(m_rows, 1)}, found {sigma.shape}")
    if logicals.shape[1] != n_cols:
        raise ValueError(
            f"logicals must have {n_cols} columns to match H, found {logicals.shape[1]}"
        )
    if actual_observables.shape != (logicals.shape[0],):
        raise ValueError(
            f"actual_observables must have shape {(logicals.shape[0],)}, found {actual_observables.shape}"
        )
    if initial_estimate.shape != (n_cols,):
        raise ValueError(f"{args.estimate_name} must have shape {(n_cols,)}, found {initial_estimate.shape}")

    initial_estimate_u4, cutoff_u4, quant_meta = quantize_scores_u4(initial_estimate, cutoff)
    n_pad = next_pow2(n_cols)
    top_p_max = min(n_pad, TOP_P_MULTIPLE * m_rows)
    case_id = compute_case_id(
        module_path=args.module,
        h_mat=h_mat,
        sigma=sigma,
        estimate_u4=initial_estimate_u4,
        cutoff_u4=int(cutoff_u4),
        top_p_max=int(top_p_max),
    )

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
            "top-P ranker window is too small for this case: "
            f"required_top_p_sw={required_top_p_sw} exceeds top_p_max={top_p_max}. "
            "Increase TOP_P or change the case because some ranked columns fail the independence test."
        )

    h_selected = h_mat[:, selected_indices_sw] if selected_indices_sw.size else np.zeros((m_rows, 0), dtype=np.uint8)
    row_mask = h_selected.any(axis=1) if h_selected.size else np.zeros(m_rows, dtype=bool)
    unsatisfied_zero_rows = np.flatnonzero((~row_mask) & (sigma[:, 0] == 1))
    h_reduced = h_selected[row_mask]
    sigma_reduced = sigma[row_mask]

    square_ok = bool(
        selected_indices_sw.size > 0
        and unsatisfied_zero_rows.size == 0
        and h_reduced.shape[0] == selected_indices_sw.size
    )

    x_software = np.zeros(selected_indices_sw.size, dtype=np.uint8)
    f_software = np.zeros(n_cols, dtype=np.uint8)
    b_solver = sigma_reduced.copy()
    software_status = "ok" if square_ok else "reduced system is not square"
    if square_ok:
        try:
            x_software = gf2_solve(h_reduced, sigma_reduced[:, 0])
            f_software[selected_indices_sw] = x_software
        except ValueError as exc:
            software_status = str(exc)
            square_ok = False

    cases_root = args.cases_root.expanduser().resolve()
    temp_case_dir = cases_root / f".tmp_{case_id}"
    final_case_dir = cases_root / case_id
    if temp_case_dir.exists():
        shutil.rmtree(temp_case_dir)
    paths = ensure_dirs(temp_case_dir)

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

    np.save(temp_case_dir / "H.npy", h_mat)
    np.save(temp_case_dir / "sigma.npy", sigma)
    np.save(temp_case_dir / "logicals.npy", logicals)
    np.save(temp_case_dir / "actual_observables.npy", actual_observables)
    np.save(temp_case_dir / "initial_estimate.npy", initial_estimate)
    np.save(temp_case_dir / "initial_estimate_u4.npy", initial_estimate_u4)
    np.save(temp_case_dir / "estimate_padded_u4.npy", estimate_padded_u4)
    np.save(temp_case_dir / "sorted_indices_sw.npy", sorted_indices_sw)
    np.save(temp_case_dir / "filtered_indices_sw.npy", filtered_indices_sw)
    np.save(temp_case_dir / "selected_indices_sw.npy", selected_indices_sw)
    np.save(temp_case_dir / "rank_lookup_sw.npy", rank_lookup_sw)
    np.save(temp_case_dir / "H_reduced_sw.npy", h_reduced)
    np.save(temp_case_dir / "sigma_reduced_sw.npy", sigma_reduced)
    np.save(temp_case_dir / "B_solver.npy", b_solver)
    np.save(temp_case_dir / "x_software.npy", x_software)
    np.save(temp_case_dir / "F_software.npy", f_software)
    np.save(temp_case_dir / "cutoff.npy", np.array([cutoff], dtype=np.float32))
    np.save(temp_case_dir / "cutoff_u4.npy", np.array([cutoff_u4], dtype=np.uint8))

    write_reversed_rows(h_mat, paths["problem"] / "h_rows.mem")
    write_sigma_column(sigma, paths["problem"] / "sigma.mem")
    write_u4_hex(estimate_padded_u4, paths["problem"] / "estimate.hex")
    write_u4_scalar_hex(int(cutoff_u4), paths["problem"] / "cutoff.hex")

    meta = {
      "case_id": case_id,
      "module": str(args.module.resolve()),
      "H_name": args.h_name,
      "sigma_name": args.sigma_name,
      "estimate_name": args.estimate_name,
      "cutoff_name": args.cutoff_name,
      "M_MAX": int(m_rows),
      "N_MAX": int(n_cols),
      "N_PAD_MAX": int(n_pad),
      "timeout_cycles": int((3 * n_pad) + max(64, m_rows) + (6 * m_rows) + 64),
      "top_p_max": int(top_p_max),
      "required_top_p_sw": int(required_top_p_sw),
      "top_p_sufficient_sw": bool(top_p_sufficient_sw),
      "cutoff": float(cutoff),
      "cutoff_u4": int(cutoff_u4),
      "logical_observable_count": int(logicals.shape[0]),
      "score_quantization": {
        "kind": "uniform_u4",
        "low": quant_meta["low"],
        "high": quant_meta["high"],
        "sentinel": int(sentinel_u4),
      },
      "selected_count_sw": int(selected_indices_sw.size),
      "compacted_rows_sw": int(h_reduced.shape[0]),
      "square_ok": bool(square_ok),
      "software_status": software_status,
      "files": {
        "logicals_npy": str((final_case_dir / "logicals.npy").resolve()),
        "actual_observables_npy": str((final_case_dir / "actual_observables.npy").resolve()),
        "h_rows_mem": str((final_case_dir / "problem" / "h_rows.mem").resolve()),
        "sigma_mem": str((final_case_dir / "problem" / "sigma.mem").resolve()),
        "estimate_hex": str((final_case_dir / "problem" / "estimate.hex").resolve()),
        "cutoff_hex": str((final_case_dir / "problem" / "cutoff.hex").resolve()),
        "tb_sv": str((final_case_dir / "generated" / "tb_osd_decode.sv").resolve()),
      },
    }
    save_meta(temp_case_dir / "meta.json", meta)

    manifest = {
      "workflow": "osd_decode",
      "case_id": case_id,
      "created_at": case_timestamp(),
      "module": str(args.module.resolve()),
      "M_MAX": int(m_rows),
      "N_MAX": int(n_cols),
      "N_PAD_MAX": int(n_pad),
      "cutoff_u4": int(cutoff_u4),
      "top_p_max": int(top_p_max),
      "required_top_p_sw": int(required_top_p_sw),
      "top_p_sufficient_sw": bool(top_p_sufficient_sw),
      "sim_default": "iverilog",
      "stages": {
        "built": True,
        "ran": False,
        "read": False,
      },
      "files": {
        "logicals_npy": "logicals.npy",
        "actual_observables_npy": "actual_observables.npy",
        "h_rows_mem": "problem/h_rows.mem",
        "sigma_mem": "problem/sigma.mem",
        "estimate_hex": "problem/estimate.hex",
        "cutoff_hex": "problem/cutoff.hex",
        "tb_sv": "generated/tb_osd_decode.sv",
      },
      "hashes": {
        "logicals_npy": sha256_file(temp_case_dir / "logicals.npy"),
        "actual_observables_npy": sha256_file(temp_case_dir / "actual_observables.npy"),
        "h_rows_mem": sha256_file(paths["problem"] / "h_rows.mem"),
        "sigma_mem": sha256_file(paths["problem"] / "sigma.mem"),
        "estimate_hex": sha256_file(paths["problem"] / "estimate.hex"),
        "cutoff_hex": sha256_file(paths["problem"] / "cutoff.hex"),
        "tb_sv": sha256_file(tb_path),
      },
    }
    save_manifest(temp_case_dir / "manifest.json", manifest)

    cases_root.mkdir(parents=True, exist_ok=True)
    if final_case_dir.exists():
        shutil.rmtree(final_case_dir)
    temp_case_dir.rename(final_case_dir)
    update_latest_symlink(cases_root, final_case_dir)

    print_case_report(
        final_case_dir,
        "stage: build",
        f"M={m_rows} N={n_cols} N_PAD={n_pad} selected_count_sw={selected_indices_sw.size}",
        f"cutoff_u4={int(cutoff_u4)} top_p_max={top_p_max} required_top_p_sw={required_top_p_sw}",
        f"square_ok={square_ok} software_status={software_status}",
    )


if __name__ == "__main__":
    main()
