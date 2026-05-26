#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from common import ensure_dirs, load_counts, load_manifest, load_meta, osd_decode_rtl_sources, print_case_report, resolve_case_dir, update_manifest, verify_manifest_inputs


def _binary_row_width(path: Path) -> int:
    for line in path.read_text().splitlines():
        row = line.strip()
        if row:
            return len(row)
    return 0


def _hex_digit_width(path: Path) -> int:
    for line in path.read_text().splitlines():
        word = line.strip()
        if word:
            return len(word)
    return 0


def _compile_and_run_iverilog(case_dir: Path, sim_vvp: Path, sources: list[Path], plusargs: list[str]) -> None:
    subprocess.run(
        ["iverilog", "-g2012", "-o", str(sim_vvp), "-s", "tb_osd_decode", *map(str, sources)],
        check=True,
        cwd=case_dir,
    )
    subprocess.run(["vvp", str(sim_vvp), *plusargs], check=True, cwd=case_dir)


def _compile_and_run_verilator(case_dir: Path, build_dir: Path, sources: list[Path], plusargs: list[str]) -> None:
    build_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "verilator",
            "--binary",
            "-j",
            "0",
            "-sv",
            "--timing",
            "--output-split",
            "20000",
            "-Wno-fatal",
            "-MAKEFLAGS",
            "OPT_FAST=-O3",
            "--top-module",
            "tb_osd_decode",
            "--Mdir",
            str(build_dir),
            *map(str, sources),
        ],
        check=True,
        cwd=case_dir,
    )
    subprocess.run([str(build_dir / "Vtb_osd_decode"), *plusargs], check=True, cwd=case_dir)


def _mark_run_complete(manifest_data: dict, sim_name: str, save_trace: bool, counts: dict[str, int]) -> None:
    outputs = {
        "selected_indices_hw": "out/selected_indices_hw.txt",
        "h_reduced_hw": "out/h_reduced_hw.bin",
        "sigma_reduced_hw": "out/sigma_reduced_hw.bin",
        "counts_hw": "out/counts_hw.txt",
        "x_hardware": "out/x_hardware.bin",
        "F_hardware": "out/F_hardware.bin",
    }
    if save_trace:
        outputs["x_trace_hw"] = "out/x_trace_hw.bin"

    manifest_data["stages"]["ran"] = True
    manifest_data["stages"]["read"] = False
    manifest_data["run"] = {
        "sim": sim_name,
        "cycles": counts,
        "outputs": outputs,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-dir", type=Path, default=Path(__file__).resolve().parent / "cases" / "latest")
    parser.add_argument("--sim", choices=["iverilog", "verilator"], default=None)
    parser.add_argument("--save-trace", action="store_true")
    args = parser.parse_args()

    case_dir = resolve_case_dir(args.case_dir)
    paths = ensure_dirs(case_dir)
    manifest_path = case_dir / "manifest.json"
    manifest = load_manifest(manifest_path)
    verify_manifest_inputs(case_dir, manifest)
    meta = load_meta(case_dir / "meta.json")
    sim_name = args.sim or str(manifest.get("sim_default", "iverilog"))
    required_tools = ["iverilog", "vvp"] if sim_name == "iverilog" else ["verilator"]
    missing_tools = [tool for tool in required_tools if shutil.which(tool) is None]
    if missing_tools:
        raise FileNotFoundError(f"required simulator tools not found on PATH: {', '.join(missing_tools)}")
    expected_n = int(meta["N_MAX"])
    actual_n = _binary_row_width(paths["problem"] / "h_rows.mem")
    if actual_n != expected_n:
        raise ValueError(
            f"{paths['problem'] / 'h_rows.mem'} has row width {actual_n}, "
            f"but meta.json expects N_MAX={expected_n}. Re-run build.py for this case."
        )
    estimate_hex_digits = _hex_digit_width(paths["problem"] / "estimate.hex")
    cutoff_hex_digits = _hex_digit_width(paths["problem"] / "cutoff.hex")
    if estimate_hex_digits > 1 or cutoff_hex_digits > 1:
        raise ValueError(
            "osd_decode expects u4 score memories, but found stale multi-digit hex "
            "artifacts. Re-run build.py for this case."
        )

    sim_vvp = paths["out"] / "tb_osd_decode.vvp"
    verilator_build = paths["out"] / "verilator"
    for stale_name in ("x_hardware.npy", "F_hardware.npy", "solver_trace_hw.npy"):
        stale_path = case_dir / stale_name
        if stale_path.exists():
            stale_path.unlink()
    for stale_name in ("x_hardware.bin", "F_hardware.bin", "x_trace_hw.bin"):
        stale_path = paths["out"] / stale_name
        if stale_path.exists():
            stale_path.unlink()
    sources = osd_decode_rtl_sources(case_dir / manifest["files"]["tb_sv"])

    plusargs = [
        f"+H_ROWS={paths['problem'] / 'h_rows.mem'}",
        f"+SIGMA={paths['problem'] / 'sigma.mem'}",
        f"+ESTIMATE={paths['problem'] / 'estimate.hex'}",
        f"+CUTOFF={paths['problem'] / 'cutoff.hex'}",
        f"+SELECTED_OUT={paths['out'] / 'selected_indices_hw.txt'}",
        f"+H_REDUCED_OUT={paths['out'] / 'h_reduced_hw.bin'}",
        f"+SIGMA_REDUCED_OUT={paths['out'] / 'sigma_reduced_hw.bin'}",
        f"+COUNTS_OUT={paths['out'] / 'counts_hw.txt'}",
        f"+X_HARDWARE_OUT={paths['out'] / 'x_hardware.bin'}",
        f"+F_HARDWARE_OUT={paths['out'] / 'F_hardware.bin'}",
        f"+TIMEOUT_CYCLES={int(meta['timeout_cycles'])}",
    ]
    if args.save_trace:
        plusargs.append(f"+X_TRACE_OUT={paths['out'] / 'x_trace_hw.bin'}")

    if sim_name == "iverilog":
        _compile_and_run_iverilog(case_dir, sim_vvp, sources, plusargs)
    else:
        _compile_and_run_verilator(case_dir, verilator_build, sources, plusargs)

    counts = load_counts(paths["out"] / "counts_hw.txt")
    update_manifest(manifest_path, lambda manifest_data: _mark_run_complete(manifest_data, sim_name, args.save_trace, counts))

    elapsed_cycles = counts.get("elapsed_cycles")
    if elapsed_cycles is None:
        print_case_report(case_dir, "stage: run", f"sim={sim_name}")
    else:
        print_case_report(case_dir, "stage: run", f"sim={sim_name} elapsed_cycles={elapsed_cycles}")


if __name__ == "__main__":
    main()
