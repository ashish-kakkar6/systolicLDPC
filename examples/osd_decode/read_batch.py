#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from common import (
    ensure_batch_dirs,
    load_binary_rows,
    load_counts,
    load_manifest,
    load_meta,
    print_batch_report,
    resolve_case_dir,
    update_manifest,
    verify_batch_manifest_inputs,
)


def _shot_name(shot_index: int) -> str:
    return f"shot_{shot_index:06d}"


def _mark_read_complete(
    manifest_data: dict,
    *,
    results_jsonl: str,
    shots: int,
    h_f_equals_sigma_count: int,
    logical_match_all_count: int,
) -> None:
    manifest_data["stages"]["read"] = True
    manifest_data["read"] = {
        "results_jsonl": results_jsonl,
        "shots": int(shots),
        "H_F_equals_sigma_count": int(h_f_equals_sigma_count),
        "logicals_match_all_count": int(logical_match_all_count),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", type=Path, default=Path(__file__).resolve().parent / "batches" / "latest")
    args = parser.parse_args()

    batch_dir = resolve_case_dir(args.batch_dir)
    paths = ensure_batch_dirs(batch_dir)
    manifest_path = batch_dir / "manifest.json"
    manifest = load_manifest(manifest_path)
    verify_batch_manifest_inputs(batch_dir, manifest)
    if not manifest.get("stages", {}).get("ran", False):
        raise ValueError(f"{batch_dir} has not been run yet")

    meta = load_meta(batch_dir / "meta.json")
    h_mat = np.load(batch_dir / "H.npy", allow_pickle=False)
    logicals = np.load(batch_dir / "logicals.npy", allow_pickle=False)
    sigma_all = np.load(batch_dir / "sigmas.npy", allow_pickle=False)
    actual_all = np.load(batch_dir / "actual_observables.npy", allow_pickle=False)

    results_path = batch_dir / "shot_results.jsonl"
    results_lines: list[str] = []
    h_f_equals_sigma_count = 0
    logical_match_all_count = 0

    for shot_index in range(int(meta["shots"])):
        shot_dir = paths["shots"] / _shot_name(shot_index)
        shot_out_dir = shot_dir / "out"
        f_hardware_bin = shot_out_dir / "F_hardware.bin"
        counts_path = shot_out_dir / "counts_hw.txt"
        if not f_hardware_bin.exists():
            raise FileNotFoundError(f"missing hardware output: {f_hardware_bin}")
        if not counts_path.exists():
            raise FileNotFoundError(f"missing hardware output: {counts_path}")

        sigma = sigma_all[shot_index].astype(np.uint8, copy=False)
        actual_observables = actual_all[shot_index].astype(np.uint8, copy=False)
        f_hardware_rows = load_binary_rows(f_hardware_bin)
        if f_hardware_rows.shape[0] != 1:
            raise ValueError(f"{f_hardware_bin} must contain exactly one row, found {f_hardware_rows.shape[0]}")
        f_hardware = f_hardware_rows[0].astype(np.uint8, copy=False)
        if f_hardware.shape[0] != h_mat.shape[1]:
            raise ValueError(
                f"{f_hardware_bin} has width {f_hardware.shape[0]}, expected {h_mat.shape[1]} from H"
            )

        f_hardware_npy = shot_dir / "F_hardware.npy"
        np.save(f_hardware_npy, f_hardware)

        h_f_equals_sigma = bool(np.array_equal((h_mat @ f_hardware) % 2, sigma))
        logical_match = ((logicals @ f_hardware) % 2 == actual_observables)
        logical_match_all = bool(np.all(logical_match))
        counts = load_counts(counts_path)
        elapsed_cycles = counts.get("elapsed_cycles")

        if h_f_equals_sigma:
            h_f_equals_sigma_count += 1
        if logical_match_all:
            logical_match_all_count += 1

        summary = {
            "shot_index": shot_index,
            "actual_observables": actual_observables.tolist(),
            "F_hardware_npy": str(f_hardware_npy.relative_to(batch_dir)),
            "sigma": sigma.tolist(),
            "H_F_equals_sigma": h_f_equals_sigma,
            "logicals_times_F_equals_actual_observables": logical_match.tolist(),
            "elapsed_cycles": elapsed_cycles,
        }
        summary_path = shot_dir / "summary.json"
        summary_path.write_text(json.dumps(summary, indent=2) + "\n")
        results_lines.append(json.dumps(summary))

    results_path.write_text("\n".join(results_lines) + ("\n" if results_lines else ""))
    update_manifest(
        manifest_path,
        lambda manifest_data: _mark_read_complete(
            manifest_data,
            results_jsonl="shot_results.jsonl",
            shots=int(meta["shots"]),
            h_f_equals_sigma_count=h_f_equals_sigma_count,
            logical_match_all_count=logical_match_all_count,
        ),
    )

    print_batch_report(
        batch_dir,
        "stage: read",
        f"shots={int(meta['shots'])}",
        f"results_jsonl={results_path}",
        f"H @ F == sigma count={h_f_equals_sigma_count}",
        f"logicals @ F == actual_observables count={logical_match_all_count}",
    )


if __name__ == "__main__":
    main()
