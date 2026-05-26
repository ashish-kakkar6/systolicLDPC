#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np

from common import (
    BP_SCORE_SHIFT,
    DEFAULT_CASE_MODULE,
    LLR_W,
    bit_lines,
    build_row_graph,
    case_timestamp,
    compute_case_id,
    ensure_dirs,
    fixed_to_float,
    gf2_solve,
    load_python_namespace,
    minsum_reference,
    next_pow2,
    print_case_report,
    quantize_bp_posterior_u4,
    quantize_llr,
    render_tb,
    save_manifest,
    save_meta,
    select_independent_columns,
    sha256_file,
    stable_sorted_indices,
    to_float_vector,
    to_uint8_matrix,
    to_uint8_vector,
    update_latest_symlink,
    write_hex_lines,
    write_reversed_rows,
    write_sigma_column,
    write_u4_hex,
)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", type=Path, default=DEFAULT_CASE_MODULE)
    parser.add_argument("--cases-root", type=Path, default=Path(__file__).resolve().parent / "cases")
    parser.add_argument("--score-shift", type=int, default=BP_SCORE_SHIFT)
    args = parser.parse_args()

    ns = load_python_namespace(args.module)
    required = ["H", "sigma", "logicals", "actual_observables", "prior_llr", "max_iter"]
    missing = [name for name in required if name not in ns]
    if missing:
        raise ValueError(f"{args.module} is missing {missing}")

    h_mat = to_uint8_matrix(ns["H"], "H")
    sigma_vec = to_uint8_vector(np.asarray(ns["sigma"], dtype=np.uint8).reshape(-1), "sigma")
    sigma = sigma_vec.reshape(-1, 1)
    logicals = to_uint8_matrix(ns["logicals"], "logicals")
    actual_observables = to_uint8_vector(ns["actual_observables"], "actual_observables")
    prior_llr = to_float_vector(ns["prior_llr"], "prior_llr")
    max_iter = int(ns["max_iter"])

    m_rows, n_cols = h_mat.shape
    if sigma.shape != (m_rows, 1):
        raise ValueError(f"sigma must have shape {(m_rows, 1)}, found {sigma.shape}")
    if logicals.shape[1] != n_cols:
        raise ValueError(f"logicals must have {n_cols} columns, found {logicals.shape[1]}")
    if actual_observables.shape != (logicals.shape[0],):
        raise ValueError(
            f"actual_observables must have shape {(logicals.shape[0],)}, found {actual_observables.shape}"
        )
    if prior_llr.shape != (n_cols,):
        raise ValueError(f"prior_llr must have shape {(n_cols,)}, found {prior_llr.shape}")

    graph = build_row_graph(h_mat)
    e_edges = int(graph["E"])
    row_deg_max = int(graph["ROW_DEG_MAX"])
    row_ptr = np.asarray(graph["row_ptr"], dtype=np.int64)
    edge_var = np.asarray(graph["edge_var"], dtype=np.int64)

    prior_q = quantize_llr(prior_llr)
    posterior_bp_sw, e_bp_sw = minsum_reference(h_mat, sigma_vec, prior_q, max_iter)
    posterior_bp_sw_f = fixed_to_float(posterior_bp_sw)
    estimate_from_bp_u4 = quantize_bp_posterior_u4(posterior_bp_sw, args.score_shift)

    n_pad = next_pow2(n_cols)
    top_p_max = n_pad
    sentinel_u4 = np.uint8(15)
    cutoff_u4 = np.uint8(15)
    estimate_padded_u4 = np.full(n_pad, sentinel_u4, dtype=np.uint8)
    estimate_padded_u4[:n_cols] = estimate_from_bp_u4

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
            "top-P ranker window is too small for this BP->OSD case: "
            f"required_top_p_sw={required_top_p_sw} exceeds top_p_max={top_p_max}"
        )

    h_selected = (
        h_mat[:, selected_indices_sw]
        if selected_indices_sw.size
        else np.zeros((m_rows, 0), dtype=np.uint8)
    )
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
    software_status = "ok" if square_ok else "reduced system is not square"
    if square_ok:
        try:
            x_software = gf2_solve(h_reduced, sigma_reduced[:, 0])
            f_software[selected_indices_sw] = x_software
        except ValueError as exc:
            software_status = str(exc)
            square_ok = False

    bp_residual_sw = ((h_mat @ e_bp_sw.astype(np.uint8)) & 1) ^ sigma_vec
    osd_residual_sw = ((h_mat @ f_software.astype(np.uint8)) & 1) ^ sigma_vec

    case_id = compute_case_id(
        module_path=args.module,
        h_mat=h_mat,
        sigma=sigma,
        prior_q=prior_q,
        max_iter=max_iter,
        score_shift=args.score_shift,
    )

    cases_root = args.cases_root.expanduser().resolve()
    temp_case_dir = cases_root / f".tmp_{case_id}"
    final_case_dir = cases_root / case_id
    if temp_case_dir.exists():
        shutil.rmtree(temp_case_dir)
    paths = ensure_dirs(temp_case_dir)

    tb_template = (Path(__file__).resolve().parent / "tb_bp_osd_decode.sv").read_text()
    tb_path = paths["generated"] / "tb_bp_osd_decode.sv"
    tb_path.write_text(
        render_tb(
            tb_template,
            m=m_rows,
            n=n_cols,
            e=e_edges,
            row_deg_max=row_deg_max,
            n_pad_max=n_pad,
        )
    )

    np.save(temp_case_dir / "H.npy", h_mat)
    np.save(temp_case_dir / "sigma.npy", sigma)
    np.save(temp_case_dir / "logicals.npy", logicals)
    np.save(temp_case_dir / "actual_observables.npy", actual_observables)
    np.save(temp_case_dir / "prior_llr.npy", prior_llr)
    np.save(temp_case_dir / "prior_llr_fixed.npy", prior_q)
    np.save(temp_case_dir / "row_ptr.npy", row_ptr)
    np.save(temp_case_dir / "edge_var.npy", edge_var)
    np.save(temp_case_dir / "posterior_bp_sw.npy", posterior_bp_sw)
    np.save(temp_case_dir / "posterior_bp_sw_float.npy", posterior_bp_sw_f)
    np.save(temp_case_dir / "e_bp_sw.npy", e_bp_sw)
    np.save(temp_case_dir / "bp_residual_sw.npy", bp_residual_sw)
    np.save(temp_case_dir / "estimate_from_bp_u4.npy", estimate_from_bp_u4)
    np.save(temp_case_dir / "estimate_padded_u4.npy", estimate_padded_u4)
    np.save(temp_case_dir / "sorted_indices_sw.npy", sorted_indices_sw)
    np.save(temp_case_dir / "filtered_indices_sw.npy", filtered_indices_sw)
    np.save(temp_case_dir / "selected_indices_sw.npy", selected_indices_sw)
    np.save(temp_case_dir / "H_reduced_sw.npy", h_reduced)
    np.save(temp_case_dir / "sigma_reduced_sw.npy", sigma_reduced)
    np.save(temp_case_dir / "x_software.npy", x_software)
    np.save(temp_case_dir / "F_software.npy", f_software)
    np.save(temp_case_dir / "osd_residual_sw.npy", osd_residual_sw)

    write_hex_lines(prior_q, LLR_W, paths["problem"] / "bp_prior_llr.hex")
    (paths["problem"] / "bp_syndrome.mem").write_text("\n".join(bit_lines(sigma_vec)) + "\n")
    write_hex_lines(row_ptr, max(1, int(np.ceil(np.log2(e_edges + 1)))), paths["problem"] / "bp_row_ptr.hex")
    write_hex_lines(edge_var, max(1, int(np.ceil(np.log2(n_cols)))), paths["problem"] / "bp_edge_var.hex")
    write_reversed_rows(h_mat, paths["problem"] / "osd_h_rows.mem")
    write_sigma_column(sigma, paths["problem"] / "osd_sigma.mem")
    write_u4_hex(estimate_padded_u4, paths["problem"] / "estimate_from_bp_sw.hex")

    bp_cycles = 1 + n_cols + e_edges + (max_iter * (m_rows + (2 * e_edges) + 1)) + n_cols
    bridge_cycles = n_pad + 3
    osd_cycles = int((3 * n_pad) + max(64, m_rows) + (6 * m_rows) + 128)
    timeout_cycles = bp_cycles + bridge_cycles + osd_cycles + 256

    meta = {
        "case_id": case_id,
        "module": str(args.module.resolve()),
        "M": int(m_rows),
        "N": int(n_cols),
        "E": int(e_edges),
        "ROW_DEG_MAX": int(row_deg_max),
        "N_PAD_MAX": int(n_pad),
        "max_iter": int(max_iter),
        "timeout_cycles": int(timeout_cycles),
        "score_shift": int(args.score_shift),
        "top_p_max": int(top_p_max),
        "required_top_p_sw": int(required_top_p_sw),
        "top_p_sufficient_sw": bool(top_p_sufficient_sw),
        "selected_count_sw": int(selected_indices_sw.size),
        "compacted_rows_sw": int(h_reduced.shape[0]),
        "square_ok": bool(square_ok),
        "software_status": software_status,
        "logical_observable_count": int(logicals.shape[0]),
        "files": {
            "bp_prior_llr_hex": str((final_case_dir / "problem" / "bp_prior_llr.hex").resolve()),
            "bp_syndrome_mem": str((final_case_dir / "problem" / "bp_syndrome.mem").resolve()),
            "bp_row_ptr_hex": str((final_case_dir / "problem" / "bp_row_ptr.hex").resolve()),
            "bp_edge_var_hex": str((final_case_dir / "problem" / "bp_edge_var.hex").resolve()),
            "osd_h_rows_mem": str((final_case_dir / "problem" / "osd_h_rows.mem").resolve()),
            "osd_sigma_mem": str((final_case_dir / "problem" / "osd_sigma.mem").resolve()),
            "tb_sv": str((final_case_dir / "generated" / "tb_bp_osd_decode.sv").resolve()),
        },
    }
    save_meta(temp_case_dir / "meta.json", meta)

    manifest = {
        "workflow": "bp_osd_decode",
        "case_id": case_id,
        "created_at": case_timestamp(),
        "module": str(args.module.resolve()),
        "M": int(m_rows),
        "N": int(n_cols),
        "E": int(e_edges),
        "ROW_DEG_MAX": int(row_deg_max),
        "N_PAD_MAX": int(n_pad),
        "max_iter": int(max_iter),
        "sim_default": "iverilog",
        "stages": {"built": True, "ran": False, "read": False},
        "files": {
            "bp_prior_llr_hex": "problem/bp_prior_llr.hex",
            "bp_syndrome_mem": "problem/bp_syndrome.mem",
            "bp_row_ptr_hex": "problem/bp_row_ptr.hex",
            "bp_edge_var_hex": "problem/bp_edge_var.hex",
            "osd_h_rows_mem": "problem/osd_h_rows.mem",
            "osd_sigma_mem": "problem/osd_sigma.mem",
            "tb_sv": "generated/tb_bp_osd_decode.sv",
        },
        "hashes": {
            "bp_prior_llr_hex": sha256_file(paths["problem"] / "bp_prior_llr.hex"),
            "bp_syndrome_mem": sha256_file(paths["problem"] / "bp_syndrome.mem"),
            "bp_row_ptr_hex": sha256_file(paths["problem"] / "bp_row_ptr.hex"),
            "bp_edge_var_hex": sha256_file(paths["problem"] / "bp_edge_var.hex"),
            "osd_h_rows_mem": sha256_file(paths["problem"] / "osd_h_rows.mem"),
            "osd_sigma_mem": sha256_file(paths["problem"] / "osd_sigma.mem"),
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
        f"M={m_rows} N={n_cols} E={e_edges} N_PAD={n_pad} max_iter={max_iter}",
        f"bp_residual_weight={int(bp_residual_sw.sum())} osd_residual_weight={int(osd_residual_sw.sum())}",
        f"selected_count_sw={selected_indices_sw.size} top_p_max={top_p_max} score_shift={args.score_shift}",
    )


if __name__ == "__main__":
    main()
