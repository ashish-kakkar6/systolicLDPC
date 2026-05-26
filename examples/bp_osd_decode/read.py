#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from common import (
    LLR_W,
    load_binary_rows,
    load_counts,
    load_int_lines,
    load_manifest,
    load_meta,
    print_case_report,
    read_bit_vector,
    read_signed_hex_vector,
    resolve_case_dir,
    save_meta,
    update_manifest,
)


def _read_single_bit_row(path: Path) -> np.ndarray:
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if not lines:
        return np.zeros(0, dtype=np.uint8)
    if len(lines) == 1 and set(lines[0]) <= {"0", "1"}:
        return np.array([int(bit) for bit in lines[0]], dtype=np.uint8)
    return np.array([int(line) for line in lines], dtype=np.uint8)


def _residual(h_mat: np.ndarray, error_vec: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    return ((h_mat @ error_vec.astype(np.uint8)) & 1) ^ sigma.reshape(-1)


def _resolve_output_path(case_dir: Path, manifest: dict, key: str, default_rel: str) -> Path:
    run_outputs = manifest.get("run", {}).get("outputs", {})
    rel_path = run_outputs.get(key, default_rel)
    return case_dir / rel_path


def _require_ran(case_dir: Path, manifest: dict) -> None:
    if not manifest.get("stages", {}).get("ran", False):
        run_cmd = f"python examples/bp_osd_decode/run.py --case-dir {case_dir}"
        raise ValueError(f"{case_dir} has not been run yet. Run:\n{run_cmd}")


def _require_files(paths: list[Path]) -> None:
    missing = [path for path in paths if not path.exists()]
    if missing:
        missing_list = "\n".join(str(path) for path in missing)
        raise FileNotFoundError(f"missing hardware output files:\n{missing_list}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-dir", type=Path, default=Path(__file__).resolve().parent / "cases" / "latest")
    args = parser.parse_args()

    case_dir = resolve_case_dir(args.case_dir)
    manifest_path = case_dir / "manifest.json"
    manifest = load_manifest(manifest_path)
    meta = load_meta(case_dir / "meta.json")
    _require_ran(case_dir, manifest)

    h_mat = np.load(case_dir / "H.npy")
    sigma = np.load(case_dir / "sigma.npy").reshape(-1)
    logicals = np.load(case_dir / "logicals.npy")
    actual_observables = np.load(case_dir / "actual_observables.npy").reshape(-1)

    posterior_bp_sw = np.load(case_dir / "posterior_bp_sw.npy").reshape(-1)
    e_bp_sw = np.load(case_dir / "e_bp_sw.npy").reshape(-1)
    selected_indices_sw = np.load(case_dir / "selected_indices_sw.npy").reshape(-1)
    h_reduced_sw = np.load(case_dir / "H_reduced_sw.npy")
    sigma_reduced_sw = np.load(case_dir / "sigma_reduced_sw.npy").reshape(-1)
    x_software = np.load(case_dir / "x_software.npy").reshape(-1)
    f_software = np.load(case_dir / "F_software.npy").reshape(-1)
    estimate_from_bp_sw = np.load(case_dir / "estimate_padded_u4.npy").reshape(-1)

    counts_path = _resolve_output_path(case_dir, manifest, "counts_hw", "out/counts_hw.txt")
    posterior_bp_path = _resolve_output_path(case_dir, manifest, "bp_posterior_hw", "out/bp_posterior_hw.hex")
    e_bp_path = _resolve_output_path(case_dir, manifest, "bp_hard_hw", "out/bp_hard_hw.bin")
    estimate_path = _resolve_output_path(case_dir, manifest, "estimate_from_bp_hw", "out/estimate_from_bp_hw.hex")
    selected_path = _resolve_output_path(case_dir, manifest, "selected_indices_hw", "out/selected_indices_hw.txt")
    h_reduced_path = _resolve_output_path(case_dir, manifest, "h_reduced_hw", "out/h_reduced_hw.bin")
    sigma_reduced_path = _resolve_output_path(case_dir, manifest, "sigma_reduced_hw", "out/sigma_reduced_hw.bin")
    x_hardware_path = _resolve_output_path(case_dir, manifest, "x_hardware", "out/x_hardware.bin")
    f_hardware_path = _resolve_output_path(case_dir, manifest, "F_hardware", "out/F_hardware.bin")
    _require_files(
        [
            counts_path,
            posterior_bp_path,
            e_bp_path,
            estimate_path,
            selected_path,
            h_reduced_path,
            sigma_reduced_path,
            x_hardware_path,
            f_hardware_path,
        ]
    )

    counts = load_counts(counts_path)
    posterior_bp_hw = read_signed_hex_vector(posterior_bp_path, LLR_W)
    e_bp_hw = read_bit_vector(e_bp_path)
    estimate_from_bp_hw = load_int_lines(estimate_path).astype(np.uint8)
    selected_indices_hw = load_int_lines(selected_path)
    h_reduced_hw_raw = load_binary_rows(h_reduced_path)
    sigma_reduced_hw = read_bit_vector(sigma_reduced_path)
    x_hardware = _read_single_bit_row(x_hardware_path)
    f_hardware = _read_single_bit_row(f_hardware_path)

    selected_count = int(counts.get("selected_count", selected_indices_hw.size))
    compacted_rows = int(counts.get("compacted_rows", h_reduced_hw_raw.shape[0]))
    h_reduced_hw = h_reduced_hw_raw[:compacted_rows, :selected_count] if h_reduced_hw_raw.size else np.zeros((0, 0), dtype=np.uint8)
    sigma_reduced_hw = sigma_reduced_hw[:compacted_rows]
    x_hardware = x_hardware[:selected_count]
    f_hardware = f_hardware[: h_mat.shape[1]]

    bp_residual_hw = _residual(h_mat, e_bp_hw, sigma)
    osd_residual_hw = _residual(h_mat, f_hardware, sigma)
    bp_logicals_hw = ((logicals @ e_bp_hw.astype(np.uint8)) & 1).reshape(-1)
    osd_logicals_hw = ((logicals @ f_hardware.astype(np.uint8)) & 1).reshape(-1)

    bp_matches = bool(np.array_equal(posterior_bp_hw, posterior_bp_sw))
    bp_hard_matches = bool(np.array_equal(e_bp_hw, e_bp_sw))
    estimate_matches = bool(np.array_equal(estimate_from_bp_hw[: estimate_from_bp_sw.size], estimate_from_bp_sw))
    selected_matches = bool(np.array_equal(selected_indices_hw, selected_indices_sw))
    reduced_matches = bool(np.array_equal(h_reduced_hw, h_reduced_sw))
    sigma_reduced_matches = bool(np.array_equal(sigma_reduced_hw, sigma_reduced_sw))
    x_matches = bool(np.array_equal(x_hardware, x_software))
    f_matches = bool(np.array_equal(f_hardware, f_software))

    print_case_report(
        case_dir,
        "stage: read",
        "bp:"
        f" posterior_match={bp_matches}"
        f" hard_match={bp_hard_matches}"
        f" syndrome_match={bool(np.all(bp_residual_hw == 0))}"
        f" residual_weight={int(bp_residual_hw.sum())}"
        f" logicals_match={bool(np.array_equal(bp_logicals_hw, actual_observables))}",
        "osd:"
        f" estimate_match={estimate_matches}"
        f" selected_match={selected_matches}"
        f" reduced_match={reduced_matches and sigma_reduced_matches}"
        f" x_match={x_matches}"
        f" f_match={f_matches}"
        f" syndrome_match={bool(np.all(osd_residual_hw == 0))}"
        f" residual_weight={int(osd_residual_hw.sum())}"
        f" logicals_match={bool(np.array_equal(osd_logicals_hw, actual_observables))}",
        f"elapsed_cycles={counts.get('elapsed_cycles')} bp_iter_count={counts.get('bp_iter_count')} selected_count={selected_count} compacted_rows={compacted_rows}",
    )

    def _mark_read(manifest_data: dict) -> None:
        manifest_data["stages"]["read"] = True
        manifest_data["read"] = {
            "bp_posterior_matches": bp_matches,
            "bp_hard_matches": bp_hard_matches,
            "estimate_matches": estimate_matches,
            "selected_matches": selected_matches,
            "reduced_matches": reduced_matches,
            "sigma_reduced_matches": sigma_reduced_matches,
            "x_matches": x_matches,
            "f_matches": f_matches,
            "bp_residual_weight": int(bp_residual_hw.sum()),
            "osd_residual_weight": int(osd_residual_hw.sum()),
            "bp_logicals_match": bool(np.array_equal(bp_logicals_hw, actual_observables)),
            "osd_logicals_match": bool(np.array_equal(osd_logicals_hw, actual_observables)),
        }

    updated_manifest = update_manifest(manifest_path, _mark_read)
    save_meta(case_dir / "read_summary.json", updated_manifest.get("read", {}))


if __name__ == "__main__":
    main()
