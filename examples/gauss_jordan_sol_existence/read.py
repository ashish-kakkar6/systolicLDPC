#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from common import ensure_dirs, interpret_existence_from_trace, load_counts, load_first_one_cycle_vector, load_has_solution_vector, load_manifest, load_meta, load_trace, print_case_report, resolve_case_dir, update_manifest, verify_manifest_inputs


def _mark_read_complete(
    manifest_data: dict,
    *,
    cycle_info: dict[str, int],
    has_solution_sw: np.ndarray,
    has_solution_hw: np.ndarray,
    has_solution_trace: np.ndarray,
    existence_match: np.ndarray,
    first_bottom_one_cycle_hw: list[int | None],
) -> None:
    bottom_trace_has_one_hw = (~has_solution_hw).astype(np.uint8).tolist()
    manifest_data["stages"]["read"] = True
    manifest_data["read"] = {
        "cycles": cycle_info,
        "has_solution_sw": has_solution_sw.astype(np.uint8).tolist(),
        "has_solution_hw": has_solution_hw.astype(np.uint8).tolist(),
        "has_solution_trace": has_solution_trace.astype(np.uint8).tolist(),
        "existence_match": existence_match.astype(np.uint8).tolist(),
        "existence_match_all": bool(np.all(existence_match)),
        "bottom_trace_has_one_hw": bottom_trace_has_one_hw,
        "first_bottom_one_cycle_hw": first_bottom_one_cycle_hw,
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
    counts = load_counts(paths["out"] / "solver_counts.txt")
    configured_run_cycles = int(counts.get("configured_run_cycles", meta["run_cycles"]))

    trace = load_trace(paths["out"] / "data_bottom_trace.bin")
    bottom_trace, has_solution_trace, first_bottom_one_cycle_trace = interpret_existence_from_trace(
        trace,
        l_cols=int(meta["L"]),
        configured_run_cycles=configured_run_cycles,
    )
    has_solution_hw = load_has_solution_vector(paths["out"] / "has_solution_hw.txt", int(meta["L"]))
    first_bottom_one_cycle_hw = load_first_one_cycle_vector(
        paths["out"] / "first_one_cycle_hw.txt",
        int(meta["L"]),
    )
    np.save(case_dir / "bottom_trace.npy", bottom_trace)

    has_solution_sw = np.asarray(meta["has_solution_sw"], dtype=np.uint8).astype(bool, copy=False)
    if not np.array_equal(has_solution_hw, has_solution_trace):
        raise ValueError(
            f"{case_dir} hardware existence file does not match trace interpretation"
        )
    if first_bottom_one_cycle_hw != first_bottom_one_cycle_trace:
        raise ValueError(
            f"{case_dir} first-one cycle file does not match trace interpretation"
        )
    existence_match = (has_solution_hw == has_solution_sw)

    update_manifest(
        manifest_path,
        lambda manifest_data: _mark_read_complete(
            manifest_data,
            cycle_info=counts,
            has_solution_sw=has_solution_sw,
            has_solution_hw=has_solution_hw,
            has_solution_trace=has_solution_trace,
            existence_match=existence_match,
            first_bottom_one_cycle_hw=first_bottom_one_cycle_hw,
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
        print("bottom_trace =")
        print(bottom_trace)
        print()
        print(f"cycle_info = {counts}")
        print()
        print(f"has_solution_sw = {has_solution_sw}")
        print(f"has_solution_hw = {has_solution_hw}")
        print(f"has_solution_trace = {has_solution_trace}")
        print(f"existence_match = {existence_match}")
        print(f"existence_match_all = {bool(np.all(existence_match))}")
        print(f"bottom_trace_has_one_hw = {~has_solution_hw}")
        print(f"first_bottom_one_cycle_hw = {first_bottom_one_cycle_hw}")
        return

    lines = [
        "stage: read",
        f"existence_match_all={bool(np.all(existence_match))}",
        f"has_solution_sw={has_solution_sw.astype(np.uint8).tolist()}",
        f"has_solution_hw={has_solution_hw.astype(np.uint8).tolist()}",
    ]
    if counts:
        lines.append(f"elapsed_cycles={counts.get('elapsed_cycles')} configured_run_cycles={counts.get('configured_run_cycles')}")
    print_case_report(case_dir, *lines)


if __name__ == "__main__":
    main()
