#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np

from common import (
    ALPHA_SHIFT,
    DEFAULT_CASE_MODULE,
    LLR_FRAC,
    LLR_W,
    build_row_graph,
    case_timestamp,
    compute_case_id,
    ensure_dirs,
    load_python_namespace,
    minsum_reference,
    print_case_report,
    quantize_llr,
    render_tb,
    save_manifest,
    save_meta,
    sha256_file,
    to_float_vector,
    to_uint8_matrix,
    to_uint8_vector,
    twos_hex_lines,
    bit_lines,
    update_latest_symlink,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", type=Path, default=DEFAULT_CASE_MODULE)
    parser.add_argument("--cases-root", type=Path, default=Path(__file__).resolve().parent / "cases")
    parser.add_argument("--h-name", default="H")
    parser.add_argument("--syndrome-name", default="syndrome")
    parser.add_argument("--prior-name", default="prior_llr")
    parser.add_argument("--max-iter-name", default="max_iter")
    args = parser.parse_args()

    ns = load_python_namespace(args.module)
    required = [args.h_name, args.syndrome_name, args.prior_name]
    missing = [name for name in required if name not in ns]
    if missing:
        raise ValueError(f"{args.module} is missing {missing}")

    h_mat = to_uint8_matrix(ns[args.h_name], args.h_name)
    syndrome = to_uint8_vector(ns[args.syndrome_name], args.syndrome_name)
    prior_llr = to_float_vector(ns[args.prior_name], args.prior_name)
    max_iter = int(ns.get(args.max_iter_name, 8))

    m_rows, n_cols = h_mat.shape
    if syndrome.shape != (m_rows,):
        raise ValueError(f"{args.syndrome_name} must have shape {(m_rows,)}, found {syndrome.shape}")
    if prior_llr.shape != (n_cols,):
        raise ValueError(f"{args.prior_name} must have shape {(n_cols,)}, found {prior_llr.shape}")
    if max_iter < 1:
        raise ValueError("max_iter must be positive")

    graph = build_row_graph(h_mat)
    prior_q = quantize_llr(prior_llr)
    posterior_sw, hard_sw = minsum_reference(h_mat, syndrome, prior_q, max_iter)
    case_id = compute_case_id(
        module_path=args.module,
        h_mat=h_mat,
        syndrome=syndrome,
        prior_q=prior_q,
        max_iter=max_iter,
    )

    cases_root = args.cases_root.expanduser().resolve()
    temp_case_dir = cases_root / f".tmp_{case_id}"
    final_case_dir = cases_root / case_id
    if temp_case_dir.exists():
        shutil.rmtree(temp_case_dir)
    paths = ensure_dirs(temp_case_dir)

    np.save(temp_case_dir / "H.npy", h_mat)
    np.save(temp_case_dir / "syndrome.npy", syndrome)
    np.save(temp_case_dir / "prior_llr.npy", prior_llr)
    np.save(temp_case_dir / "prior_llr_fixed.npy", prior_q)
    np.save(temp_case_dir / "posterior_sw.npy", posterior_sw)
    np.save(temp_case_dir / "hard_sw.npy", hard_sw)
    np.save(temp_case_dir / "row_ptr.npy", graph["row_ptr"])
    np.save(temp_case_dir / "edge_var.npy", graph["edge_var"])

    optional_files: dict[str, tuple[Path, str]] = {}
    if "check_mat" in ns:
        check_mat = to_uint8_matrix(ns["check_mat"], "check_mat")
        check_mat_path = temp_case_dir / "check_mat.npy"
        np.save(check_mat_path, check_mat)
        optional_files["check_mat_npy"] = (check_mat_path, "check_mat.npy")
    if "priors" in ns:
        priors = to_float_vector(ns["priors"], "priors")
        priors_path = temp_case_dir / "priors.npy"
        np.save(priors_path, priors)
        optional_files["priors_npy"] = (priors_path, "priors.npy")
    if "target_error" in ns:
        target_error = to_uint8_vector(ns["target_error"], "target_error")
        target_error_path = temp_case_dir / "target_error.npy"
        np.save(target_error_path, target_error)
        optional_files["target_error_npy"] = (target_error_path, "target_error.npy")
    if "logicals" in ns:
        logicals = to_uint8_matrix(ns["logicals"], "logicals")
        logicals_path = temp_case_dir / "logicals.npy"
        np.save(logicals_path, logicals)
        optional_files["logicals_npy"] = (logicals_path, "logicals.npy")
    if "actual_observables" in ns:
        actual_observables = to_uint8_vector(ns["actual_observables"], "actual_observables")
        actual_observables_path = temp_case_dir / "actual_observables.npy"
        np.save(actual_observables_path, actual_observables)
        optional_files["actual_observables_npy"] = (actual_observables_path, "actual_observables.npy")
    if "software_reference_error" in ns:
        software_reference_error = to_uint8_vector(ns["software_reference_error"], "software_reference_error")
        software_reference_error_path = temp_case_dir / "software_reference_error.npy"
        np.save(software_reference_error_path, software_reference_error)
        optional_files["software_reference_error_npy"] = (
            software_reference_error_path,
            "software_reference_error.npy",
        )

    row_ptr_w = max(1, int(np.ceil(np.log2(int(graph["E"]) + 1))))
    edge_var_w = max(1, int(np.ceil(np.log2(n_cols))))

    (paths["problem"] / "prior_llr.hex").write_text("\n".join(twos_hex_lines(prior_q, LLR_W)) + "\n")
    (paths["problem"] / "syndrome.mem").write_text("\n".join(bit_lines(syndrome)) + "\n")
    (paths["problem"] / "row_ptr.hex").write_text("\n".join(twos_hex_lines(graph["row_ptr"], row_ptr_w)) + "\n")
    (paths["problem"] / "edge_var.hex").write_text("\n".join(twos_hex_lines(graph["edge_var"], edge_var_w)) + "\n")

    tb_template = (Path(__file__).resolve().parent / "tb_minsum_decode.sv").read_text()
    tb_path = paths["generated"] / "tb_minsum_decode.sv"
    tb_path.write_text(
        render_tb(
            tb_template,
            m=m_rows,
            n=n_cols,
            e=int(graph["E"]),
            row_deg_max=int(graph["ROW_DEG_MAX"]),
        )
    )

    timeout_cycles = int(n_cols + int(graph["E"]) + max_iter * ((2 * int(graph["E"])) + (2 * m_rows) + 4) + n_cols + 32)

    meta = {
        "case_id": case_id,
        "module": str(args.module.resolve()),
        "M": int(m_rows),
        "N": int(n_cols),
        "E": int(graph["E"]),
        "ROW_DEG_MAX": int(graph["ROW_DEG_MAX"]),
        "LLR_W": int(LLR_W),
        "LLR_FRAC": int(LLR_FRAC),
        "ALPHA_SHIFT": int(ALPHA_SHIFT),
        "max_iter": int(max_iter),
        "timeout_cycles": timeout_cycles,
        "selected_shot_index": int(ns["selected_shot_index"]) if "selected_shot_index" in ns else None,
        "files": {
            "prior_llr_hex": str((final_case_dir / "problem" / "prior_llr.hex").resolve()),
            "syndrome_mem": str((final_case_dir / "problem" / "syndrome.mem").resolve()),
            "row_ptr_hex": str((final_case_dir / "problem" / "row_ptr.hex").resolve()),
            "edge_var_hex": str((final_case_dir / "problem" / "edge_var.hex").resolve()),
            "tb_sv": str((final_case_dir / "generated" / "tb_minsum_decode.sv").resolve()),
        },
    }
    save_meta(temp_case_dir / "meta.json", meta)

    manifest = {
        "workflow": "minsum_decode",
        "case_id": case_id,
        "created_at": case_timestamp(),
        "module": str(args.module.resolve()),
        "M": int(m_rows),
        "N": int(n_cols),
        "E": int(graph["E"]),
        "max_iter": int(max_iter),
        "sim_default": "iverilog",
        "stages": {
            "built": True,
            "ran": False,
            "read": False,
        },
        "files": {
            "H_npy": "H.npy",
            "syndrome_npy": "syndrome.npy",
            "prior_llr_npy": "prior_llr.npy",
            "prior_llr_fixed_npy": "prior_llr_fixed.npy",
            "posterior_sw_npy": "posterior_sw.npy",
            "hard_sw_npy": "hard_sw.npy",
            "row_ptr_npy": "row_ptr.npy",
            "edge_var_npy": "edge_var.npy",
            "prior_llr_hex": "problem/prior_llr.hex",
            "syndrome_mem": "problem/syndrome.mem",
            "row_ptr_hex": "problem/row_ptr.hex",
            "edge_var_hex": "problem/edge_var.hex",
            "tb_sv": "generated/tb_minsum_decode.sv",
        },
        "hashes": {
            "H_npy": sha256_file(temp_case_dir / "H.npy"),
            "syndrome_npy": sha256_file(temp_case_dir / "syndrome.npy"),
            "prior_llr_npy": sha256_file(temp_case_dir / "prior_llr.npy"),
            "prior_llr_fixed_npy": sha256_file(temp_case_dir / "prior_llr_fixed.npy"),
            "posterior_sw_npy": sha256_file(temp_case_dir / "posterior_sw.npy"),
            "hard_sw_npy": sha256_file(temp_case_dir / "hard_sw.npy"),
            "row_ptr_npy": sha256_file(temp_case_dir / "row_ptr.npy"),
            "edge_var_npy": sha256_file(temp_case_dir / "edge_var.npy"),
            "prior_llr_hex": sha256_file(paths["problem"] / "prior_llr.hex"),
            "syndrome_mem": sha256_file(paths["problem"] / "syndrome.mem"),
            "row_ptr_hex": sha256_file(paths["problem"] / "row_ptr.hex"),
            "edge_var_hex": sha256_file(paths["problem"] / "edge_var.hex"),
            "tb_sv": sha256_file(tb_path),
        },
    }
    for key, (path_obj, rel_path) in optional_files.items():
        manifest["files"][key] = rel_path
        manifest["hashes"][key] = sha256_file(path_obj)
    save_manifest(temp_case_dir / "manifest.json", manifest)

    cases_root.mkdir(parents=True, exist_ok=True)
    if final_case_dir.exists():
        shutil.rmtree(final_case_dir)
    temp_case_dir.rename(final_case_dir)
    update_latest_symlink(cases_root, final_case_dir)

    print_case_report(
        final_case_dir,
        "stage: build",
        f"M={m_rows} N={n_cols} E={int(graph['E'])} ROW_DEG_MAX={int(graph['ROW_DEG_MAX'])} max_iter={max_iter}",
        f"target_error_present={'target_error_npy' in optional_files} actual_observables_present={'actual_observables_npy' in optional_files}",
    )


if __name__ == "__main__":
    main()
