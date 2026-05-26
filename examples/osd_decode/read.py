#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from common import interpret_bottom_trace, load_binary_rows, load_counts, load_int_lines, load_manifest, load_meta, load_trace, print_case_report, resolve_case_dir, update_manifest, verify_manifest_inputs


def _mark_read_complete(
    manifest_data: dict,
    *,
    cycle_info: dict[str, int],
    selected_match: bool,
    h_reduced_match: bool,
    sigma_reduced_match: bool,
    x_match: bool,
    f_match: bool,
    reduced_equation_match: bool,
    full_equation_match: bool,
    logical_projection: list[int],
    actual_observables: list[int],
    logical_member_match: list[bool],
    logical_member_match_all: bool,
) -> None:
    manifest_data["stages"]["read"] = True
    manifest_data["read"] = {
        "cycles": cycle_info,
        "selected_match": selected_match,
        "h_reduced_match": h_reduced_match,
        "sigma_reduced_match": sigma_reduced_match,
        "x_match": x_match,
        "F_match": f_match,
        "H_red_x_equals_sigma_reduced": reduced_equation_match,
        "H_F_equals_sigma": full_equation_match,
        "logicals_times_F_hardware": logical_projection,
        "actual_observables": actual_observables,
        "logicals_times_F_hardware_equals_actual_observables": logical_member_match,
        "logicals_times_F_hardware_equals_actual_observables_all": logical_member_match_all,
    }


def _gf2_equation_holds(matrix: np.ndarray, vector: np.ndarray, rhs: np.ndarray) -> bool:
    if matrix.ndim != 2 or vector.ndim != 1:
        return False
    if matrix.shape[1] != vector.shape[0]:
        return False
    rhs_vec = rhs.reshape(-1)
    if matrix.shape[0] != rhs_vec.shape[0]:
        return False
    return bool(np.array_equal((matrix @ vector) % 2, rhs_vec))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-dir", type=Path, default=Path(__file__).resolve().parent / "cases" / "latest")
    parser.add_argument("--print-full", action="store_true")
    args = parser.parse_args()

    case_dir = resolve_case_dir(args.case_dir)
    manifest_path = case_dir / "manifest.json"
    manifest = load_manifest(manifest_path)
    verify_manifest_inputs(case_dir, manifest)
    if not manifest.get("stages", {}).get("ran", False):
        raise ValueError(f"{case_dir} has not been run yet")
    for rel_path in manifest.get("run", {}).get("outputs", {}).values():
        if not (case_dir / rel_path).exists():
            raise FileNotFoundError(f"expected run artifact missing: {case_dir / rel_path}")
    meta = load_meta(case_dir / "meta.json")

    h_mat = np.load(case_dir / "H.npy", allow_pickle=False)
    sigma = np.load(case_dir / "sigma.npy", allow_pickle=False)
    logicals = np.load(case_dir / "logicals.npy", allow_pickle=False)
    actual_observables = np.load(case_dir / "actual_observables.npy", allow_pickle=False)
    estimate = np.load(case_dir / "initial_estimate.npy", allow_pickle=False)
    estimate_u4 = np.load(case_dir / "initial_estimate_u4.npy", allow_pickle=False)
    selected_sw = np.load(case_dir / "selected_indices_sw.npy", allow_pickle=False)
    h_reduced_sw = np.load(case_dir / "H_reduced_sw.npy", allow_pickle=False)
    sigma_reduced_sw = np.load(case_dir / "sigma_reduced_sw.npy", allow_pickle=False)
    x_software = np.load(case_dir / "x_software.npy", allow_pickle=False)
    f_software = np.load(case_dir / "F_software.npy", allow_pickle=False)

    out_dir = case_dir / "out"
    selected_hw = load_int_lines(out_dir / "selected_indices_hw.txt")
    counts_hw = load_counts(out_dir / "counts_hw.txt")
    h_reduced_hw_full = load_binary_rows(out_dir / "h_reduced_hw.bin")
    sigma_reduced_hw = load_binary_rows(out_dir / "sigma_reduced_hw.bin")
    x_trace_path = out_dir / "x_trace_hw.bin"
    x_hardware_path = out_dir / "x_hardware.bin"
    f_hardware_path = out_dir / "F_hardware.bin"

    selected_count_hw = counts_hw.get("selected_count", int(selected_hw.size))
    h_reduced_hw = h_reduced_hw_full[:, :selected_count_hw] if h_reduced_hw_full.size else h_reduced_hw_full

    x_hardware = load_binary_rows(x_hardware_path)[0].astype(np.uint8, copy=False) if x_hardware_path.exists() else np.zeros(0, dtype=np.uint8)
    f_hardware = load_binary_rows(f_hardware_path)[0].astype(np.uint8, copy=False) if f_hardware_path.exists() else np.zeros(h_mat.shape[1], dtype=np.uint8)
    x_hardware_status = "loaded from hardware outputs" if x_hardware.size else "hardware result not available"
    solver_trace_hw = np.zeros((0, 0), dtype=np.uint8)
    if x_trace_path.exists():
        x_trace_lines = [line.strip() for line in x_trace_path.read_text().splitlines() if line.strip()]
        x_trace_has_unknowns = any(set(line) - {"0", "1"} for line in x_trace_lines)
        if x_trace_has_unknowns:
            x_hardware_status = f"{x_hardware_status}; trace contains unknown values"
        elif selected_count_hw > 0:
            x_trace = load_trace(x_trace_path)
            solver_trace_hw = interpret_bottom_trace(
                x_trace,
                n_rows=selected_count_hw,
                l_cols=1,
            )
            np.save(case_dir / "solver_trace_hw.npy", solver_trace_hw)
    np.save(case_dir / "x_hardware.npy", x_hardware)
    np.save(case_dir / "F_hardware.npy", f_hardware)
    reduced_equation_match = _gf2_equation_holds(h_reduced_hw, x_hardware, sigma_reduced_hw)
    full_equation_match = _gf2_equation_holds(h_mat, f_hardware, sigma)
    logical_projection = ((logicals @ f_hardware) % 2).astype(np.uint8, copy=False)
    logical_member_match = (logical_projection == actual_observables)
    logical_member_match_all = bool(np.all(logical_member_match))

    update_manifest(
        manifest_path,
        lambda manifest_data: _mark_read_complete(
            manifest_data,
            cycle_info=counts_hw,
            selected_match=bool(np.array_equal(selected_sw, selected_hw)),
            h_reduced_match=bool(np.array_equal(h_reduced_sw, h_reduced_hw)),
            sigma_reduced_match=bool(np.array_equal(sigma_reduced_sw, sigma_reduced_hw)),
            x_match=bool(np.array_equal(x_software, x_hardware)),
            f_match=bool(np.array_equal(f_software, f_hardware)),
            reduced_equation_match=reduced_equation_match,
            full_equation_match=full_equation_match,
            logical_projection=logical_projection.tolist(),
            actual_observables=actual_observables.tolist(),
            logical_member_match=logical_member_match.tolist(),
            logical_member_match_all=logical_member_match_all,
        ),
    )

    if args.print_full:
        np.set_printoptions(threshold=np.inf, linewidth=200)
        print("initial_estimate =")
        print(estimate)
        print()
        print("logicals =")
        print(logicals)
        print()
        print("actual_observables =")
        print(actual_observables)
        print()
        print("initial_estimate_u4 =")
        print(estimate_u4)
        print()
        print("selected_sw =")
        print(selected_sw)
        print()
        print("selected_hw =")
        print(selected_hw)
        print()
        print("H_reduced_sw =")
        print(h_reduced_sw)
        print()
        print("H_reduced_hw =")
        print(h_reduced_hw)
        print()
        print("sigma_reduced_sw =")
        print(sigma_reduced_sw)
        print()
        print("sigma_reduced_hw =")
        print(sigma_reduced_hw)
        print()
        print("x_software =")
        print(x_software)
        print()
        print("F_software =")
        print(f_software)
        print()
        print("x_hardware =")
        print(x_hardware)
        print()
        print("F_hardware =")
        print(f_hardware)
        if solver_trace_hw.size:
            print()
            print("solver_trace_hw =")
            print(solver_trace_hw)
        print()
        print(f"x_hardware_status = {x_hardware_status}")
        print()
        print(f"cycle_info = {counts_hw}")
        print()
        print(f"H_red @ x_reduced == sigma_reduced = {reduced_equation_match}")
        print(f"H @ x == sigma = {full_equation_match}")
        print(f"logicals @ F_hardware (mod 2) = {logical_projection}")
        print(f"logicals @ F_hardware == actual_observables (mod 2) = {logical_member_match}")
        return

    lines = [
        "stage: read",
        f"selected_match={np.array_equal(selected_sw, selected_hw)} h_reduced_match={np.array_equal(h_reduced_sw, h_reduced_hw)} sigma_reduced_match={np.array_equal(sigma_reduced_sw, sigma_reduced_hw)}",
        f"x_match={np.array_equal(x_software, x_hardware)} F_match={np.array_equal(f_software, f_hardware)}",
        f"H_red @ x == sigma_reduced={reduced_equation_match} H @ F == sigma={full_equation_match}",
        f"logicals @ F == actual_observables={logical_member_match_all}",
    ]
    if any(key in counts_hw for key in ("elapsed_cycles", "solver_run_cycles")):
        lines.append(f"elapsed_cycles={counts_hw.get('elapsed_cycles')} solver_run_cycles={counts_hw.get('solver_run_cycles')} selected_count={selected_count_hw}")
    print_case_report(case_dir, *lines)

if __name__ == "__main__":
    main()
