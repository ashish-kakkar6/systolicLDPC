#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from common import ensure_dirs, gf2_equation_holds, interpret_solution_from_trace, load_counts, load_manifest, load_meta, load_trace, print_case_report, resolve_case_dir, update_manifest, verify_manifest_inputs


def _mark_read_complete(
    manifest_data: dict,
    *,
    cycle_info: dict[str, int],
    x_match: bool,
    a_x_equals_b: bool,
) -> None:
    manifest_data["stages"]["read"] = True
    manifest_data["read"] = {
        "cycles": cycle_info,
        "x_match": x_match,
        "A_X_equals_B": a_x_equals_b,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-dir", type=Path, default=Path(__file__).resolve().parent / "cases" / "latest")
    parser.add_argument("--print-full", action="store_true")
    args = parser.parse_args()

    case_dir = resolve_case_dir(args.case_dir)
    paths = ensure_dirs(case_dir)
    manifest_path = case_dir / "manifest.json"
    manifest = load_manifest(manifest_path)
    verify_manifest_inputs(case_dir, manifest)
    if not manifest.get("stages", {}).get("ran", False):
        raise ValueError(f"{case_dir} has not been run yet")
    for rel_path in manifest.get("run", {}).get("outputs", {}).values():
        if not (case_dir / rel_path).exists():
            raise FileNotFoundError(f"expected run artifact missing: {case_dir / rel_path}")

    meta = load_meta(case_dir / "meta.json")
    a_mat = np.load(case_dir / "A.npy", allow_pickle=False)
    b_mat = np.load(case_dir / "B.npy", allow_pickle=False)
    x_software = np.load(case_dir / "X_software.npy", allow_pickle=False)
    counts = load_counts(paths["out"] / "solver_counts.txt")

    trace = load_trace(paths["out"] / "data_bottom_trace.bin")
    solver_trace, x_hardware = interpret_solution_from_trace(
        trace,
        n_rows=int(meta["N"]),
        l_cols=int(meta["L"]),
    )
    np.save(case_dir / "solver_trace.npy", solver_trace)
    np.save(case_dir / "X_hardware.npy", x_hardware)

    x_match = bool(np.array_equal(x_software, x_hardware))
    a_x_equals_b = gf2_equation_holds(a_mat, x_hardware, b_mat)

    update_manifest(
        manifest_path,
        lambda manifest_data: _mark_read_complete(
            manifest_data,
            cycle_info=counts,
            x_match=x_match,
            a_x_equals_b=a_x_equals_b,
        ),
    )

    if args.print_full:
        np.set_printoptions(threshold=np.inf, linewidth=200)
        print("A =")
        print(a_mat)
        print()
        print("B =")
        print(b_mat)
        print()
        print("X_software =")
        print(x_software)
        print()
        print("solver_trace =")
        print(solver_trace)
        print()
        print("X_hardware =")
        print(x_hardware)
        print()
        print(f"cycle_info = {counts}")
        print()
        print(f"X_match = {x_match}")
        print(f"A @ X == B = {a_x_equals_b}")
        return

    lines = ["stage: read", f"X_match={x_match} A @ X == B={a_x_equals_b}"]
    if counts:
        lines.append(f"elapsed_cycles={counts.get('elapsed_cycles')} configured_run_cycles={counts.get('configured_run_cycles')}")
    print_case_report(case_dir, *lines)


if __name__ == "__main__":
    main()
