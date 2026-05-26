#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from common import load_counts, load_manifest, load_meta, print_case_report, read_bit_vector, read_signed_hex_vector, resolve_case_dir, update_manifest


def _mark_read_complete(manifest_data: dict) -> None:
    manifest_data["stages"]["read"] = True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-dir", type=Path, default=Path(__file__).resolve().parent / "cases" / "latest")
    args = parser.parse_args()

    case_dir = resolve_case_dir(args.case_dir)
    manifest_path = case_dir / "manifest.json"
    manifest = load_manifest(manifest_path)
    meta = load_meta(case_dir / "meta.json")

    hard_hw = read_bit_vector(case_dir / "out" / "hard_decision_hw.bin")
    posterior_hw = read_signed_hex_vector(case_dir / "out" / "posterior_llr_hw.hex", int(meta["LLR_W"]))
    h_mat = np.load(case_dir / manifest["files"]["H_npy"]).astype(np.uint8)
    syndrome = np.load(case_dir / manifest["files"]["syndrome_npy"]).astype(np.uint8)
    hard_sw = np.load(case_dir / manifest["files"]["hard_sw_npy"]).astype(np.uint8)
    posterior_sw = np.load(case_dir / manifest["files"]["posterior_sw_npy"]).astype(np.int64)
    counts = load_counts(case_dir / "out" / "counts_hw.txt")

    syndrome_eval = (h_mat @ hard_hw) % 2
    residual = (syndrome_eval ^ syndrome).astype(np.uint8)
    residual_hamming = int(np.count_nonzero(residual))
    syndrome_match = bool(np.array_equal(syndrome_eval, syndrome))
    hard_match = bool(np.array_equal(hard_hw, hard_sw))
    posterior_match = bool(np.array_equal(posterior_hw, posterior_sw))
    logical_match = None
    logical_value = None
    actual_observables = None
    if "logicals_npy" in manifest["files"] and "actual_observables_npy" in manifest["files"]:
        logicals = np.load(case_dir / manifest["files"]["logicals_npy"]).astype(np.uint8)
        actual_observables = np.load(case_dir / manifest["files"]["actual_observables_npy"]).astype(np.uint8)
        logical_value = (logicals @ hard_hw) % 2
        logical_match = bool(np.array_equal(logical_value, actual_observables))

    update_manifest(manifest_path, _mark_read_complete)

    lines = [
        "stage: read",
        f"hard_match={hard_match} posterior_match={posterior_match}",
        f"H @ e == sigma={syndrome_match} residual_weight={residual_hamming}",
    ]
    if logical_match is not None:
        lines.append(f"logicals @ e == actual_observables={logical_match}")
    if counts:
        lines.append(f"elapsed_cycles={counts.get('elapsed_cycles')} iter_count={counts.get('iter_count')}")
    print_case_report(case_dir, *lines)


if __name__ == "__main__":
    main()
