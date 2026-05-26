#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np

from common import (
    DEFAULT_INPUT_MODULE,
    DEFAULT_TB_TEMPLATE,
    case_timestamp,
    compute_case_id,
    ensure_dirs,
    gf2_rank,
    gf2_solve_matrix,
    load_python_namespace,
    next_src_depth,
    print_case_report,
    render_tb,
    save_manifest,
    save_meta,
    sha256_file,
    to_uint8_matrix,
    update_latest_symlink,
    write_reversed_rows,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", type=Path, default=DEFAULT_INPUT_MODULE)
    parser.add_argument("--cases-root", type=Path, default=Path(__file__).resolve().parent / "cases")
    parser.add_argument("--a-name", default="A")
    parser.add_argument("--b-name", default="B")
    parser.add_argument("--reduce-enable", type=int, default=1)
    parser.add_argument("--reduce-hop-delay", type=int, default=3)
    parser.add_argument("--reduce-start", type=int, default=None)
    parser.add_argument("--run-cycles", type=int, default=None)
    args = parser.parse_args()

    namespace = load_python_namespace(args.module)
    if args.a_name not in namespace or args.b_name not in namespace:
        raise ValueError(f"{args.module} must define `{args.a_name}` and `{args.b_name}`")

    a_mat = to_uint8_matrix(namespace[args.a_name], args.a_name)
    b_mat = to_uint8_matrix(namespace[args.b_name], args.b_name)

    m_rows, n_cols = a_mat.shape
    if b_mat.shape[0] != m_rows:
        raise ValueError(f"B has shape {b_mat.shape}, expected {m_rows} rows to match A")
    if m_rows != n_cols:
        raise ValueError("gauss_jordan_solve expects a square A matrix")
    if gf2_rank(a_mat) != n_cols:
        raise ValueError("gauss_jordan_solve expects A to be full rank over GF(2)")

    l_cols = b_mat.shape[1]
    reduce_start = int(args.reduce_start if args.reduce_start is not None else m_rows)
    run_cycles = int(args.run_cycles if args.run_cycles is not None else ((3 * n_cols) + m_rows + l_cols - 1))
    src_depth = next_src_depth(m_rows)
    x_software = gf2_solve_matrix(a_mat, b_mat)

    case_id = compute_case_id(
        module_path=args.module,
        a_mat=a_mat,
        b_mat=b_mat,
        reduce_enable=int(args.reduce_enable),
        reduce_hop_delay=int(args.reduce_hop_delay),
        reduce_start=reduce_start,
        run_cycles=run_cycles,
    )

    cases_root = args.cases_root.expanduser().resolve()
    temp_case_dir = cases_root / f".tmp_{case_id}"
    final_case_dir = cases_root / case_id
    if temp_case_dir.exists():
        shutil.rmtree(temp_case_dir)
    paths = ensure_dirs(temp_case_dir)

    np.save(temp_case_dir / "A.npy", a_mat)
    np.save(temp_case_dir / "B.npy", b_mat)
    np.save(temp_case_dir / "X_software.npy", x_software)
    write_reversed_rows(a_mat, paths["data"] / "a_rows.bin")
    write_reversed_rows(b_mat, paths["data"] / "b_rows.bin")

    tb_template = DEFAULT_TB_TEMPLATE.read_text()
    tb_path = paths["generated"] / "tb_example_gauss_jordan.sv"
    tb_path.write_text(
        render_tb(
            tb_template,
            n=n_cols,
            m=m_rows,
            l=l_cols,
            reduce_hop_delay=int(args.reduce_hop_delay),
            src_depth=src_depth,
        )
    )

    meta = {
        "case_id": case_id,
        "module": str(args.module.resolve()),
        "a_name": args.a_name,
        "b_name": args.b_name,
        "N": int(n_cols),
        "M": int(m_rows),
        "L": int(l_cols),
        "reduce_enable": int(args.reduce_enable),
        "reduce_hop_delay": int(args.reduce_hop_delay),
        "reduce_start": reduce_start,
        "run_cycles": run_cycles,
        "src_depth": int(src_depth),
        "square_full_rank": True,
        "files": {
            "a_rows_bin": str((final_case_dir / "data" / "a_rows.bin").resolve()),
            "b_rows_bin": str((final_case_dir / "data" / "b_rows.bin").resolve()),
            "A_npy": str((final_case_dir / "A.npy").resolve()),
            "B_npy": str((final_case_dir / "B.npy").resolve()),
            "X_software_npy": str((final_case_dir / "X_software.npy").resolve()),
            "tb_sv": str((final_case_dir / "generated" / "tb_example_gauss_jordan.sv").resolve()),
            "bottom_trace_bin": str((final_case_dir / "out" / "data_bottom_trace.bin").resolve()),
            "counts_txt": str((final_case_dir / "out" / "solver_counts.txt").resolve()),
        },
    }
    save_meta(temp_case_dir / "meta.json", meta)

    manifest = {
        "workflow": "gauss_jordan_solve",
        "case_id": case_id,
        "created_at": case_timestamp(),
        "module": str(args.module.resolve()),
        "M": int(m_rows),
        "N": int(n_cols),
        "L": int(l_cols),
        "sim_default": "iverilog",
        "stages": {
            "built": True,
            "ran": False,
            "read": False,
        },
        "files": {
            "A_npy": "A.npy",
            "B_npy": "B.npy",
            "X_software_npy": "X_software.npy",
            "a_rows_bin": "data/a_rows.bin",
            "b_rows_bin": "data/b_rows.bin",
            "tb_sv": "generated/tb_example_gauss_jordan.sv",
        },
        "hashes": {
            "A_npy": sha256_file(temp_case_dir / "A.npy"),
            "B_npy": sha256_file(temp_case_dir / "B.npy"),
            "X_software_npy": sha256_file(temp_case_dir / "X_software.npy"),
            "a_rows_bin": sha256_file(paths["data"] / "a_rows.bin"),
            "b_rows_bin": sha256_file(paths["data"] / "b_rows.bin"),
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
        f"M={m_rows} N={n_cols} L={l_cols} reduce_start={reduce_start} run_cycles={run_cycles}",
    )


if __name__ == "__main__":
    main()
