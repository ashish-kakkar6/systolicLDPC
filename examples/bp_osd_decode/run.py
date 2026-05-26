#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from common import (
    bp_osd_rtl_sources,
    ensure_dirs,
    load_counts,
    load_manifest,
    load_meta,
    print_case_report,
    resolve_case_dir,
    update_manifest,
)


def _compile_and_run_iverilog(case_dir: Path, sim_vvp: Path, sources: list[Path], plusargs: list[str]) -> None:
    subprocess.run(
        ["iverilog", "-g2012", "-o", str(sim_vvp), "-s", "tb_bp_osd_decode", *map(str, sources)],
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
            "tb_bp_osd_decode",
            "--Mdir",
            str(build_dir),
            *map(str, sources),
        ],
        check=True,
        cwd=case_dir,
    )
    subprocess.run([str(build_dir / "Vtb_bp_osd_decode"), *plusargs], check=True, cwd=case_dir)


def _mark_run_complete(manifest_data: dict, sim_name: str, counts: dict[str, int]) -> None:
    manifest_data["stages"]["ran"] = True
    manifest_data["stages"]["read"] = False
    manifest_data["run"] = {
        "sim": sim_name,
        "cycles": counts,
        "outputs": {
            "bp_hard_hw": "out/bp_hard_hw.bin",
            "bp_posterior_hw": "out/bp_posterior_hw.hex",
            "estimate_from_bp_hw": "out/estimate_from_bp_hw.hex",
            "selected_indices_hw": "out/selected_indices_hw.txt",
            "h_reduced_hw": "out/h_reduced_hw.bin",
            "sigma_reduced_hw": "out/sigma_reduced_hw.bin",
            "x_hardware": "out/x_hardware.bin",
            "F_hardware": "out/F_hardware.bin",
            "counts_hw": "out/counts_hw.txt",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-dir", type=Path, default=Path(__file__).resolve().parent / "cases" / "latest")
    parser.add_argument("--sim", choices=["iverilog", "verilator"], default=None)
    args = parser.parse_args()

    case_dir = resolve_case_dir(args.case_dir)
    paths = ensure_dirs(case_dir)
    manifest_path = case_dir / "manifest.json"
    manifest = load_manifest(manifest_path)
    meta = load_meta(case_dir / "meta.json")

    sim_name = args.sim or str(manifest.get("sim_default", "iverilog"))
    required_tools = ["iverilog", "vvp"] if sim_name == "iverilog" else ["verilator"]
    missing = [tool for tool in required_tools if shutil.which(tool) is None]
    if missing:
        raise FileNotFoundError(f"required simulator tools not found on PATH: {', '.join(missing)}")

    sim_vvp = paths["out"] / "tb_bp_osd_decode.vvp"
    verilator_build = paths["out"] / "verilator"
    sources = bp_osd_rtl_sources(case_dir / manifest["files"]["tb_sv"])

    plusargs = [
        f"+BP_PRIOR_HEX={case_dir / manifest['files']['bp_prior_llr_hex']}",
        f"+BP_SYNDROME_MEM={case_dir / manifest['files']['bp_syndrome_mem']}",
        f"+BP_ROW_PTR_HEX={case_dir / manifest['files']['bp_row_ptr_hex']}",
        f"+BP_EDGE_VAR_HEX={case_dir / manifest['files']['bp_edge_var_hex']}",
        f"+OSD_H_ROWS={case_dir / manifest['files']['osd_h_rows_mem']}",
        f"+OSD_SIGMA={case_dir / manifest['files']['osd_sigma_mem']}",
        f"+BP_HARD_OUT={paths['out'] / 'bp_hard_hw.bin'}",
        f"+BP_POSTERIOR_OUT={paths['out'] / 'bp_posterior_hw.hex'}",
        f"+ESTIMATE_OUT={paths['out'] / 'estimate_from_bp_hw.hex'}",
        f"+SELECTED_OUT={paths['out'] / 'selected_indices_hw.txt'}",
        f"+H_REDUCED_OUT={paths['out'] / 'h_reduced_hw.bin'}",
        f"+SIGMA_REDUCED_OUT={paths['out'] / 'sigma_reduced_hw.bin'}",
        f"+X_HARDWARE_OUT={paths['out'] / 'x_hardware.bin'}",
        f"+F_HARDWARE_OUT={paths['out'] / 'F_hardware.bin'}",
        f"+COUNTS_OUT={paths['out'] / 'counts_hw.txt'}",
        f"+MAX_ITER={int(meta['max_iter'])}",
        f"+TIMEOUT_CYCLES={int(meta['timeout_cycles'])}",
    ]

    if sim_name == "iverilog":
        _compile_and_run_iverilog(case_dir, sim_vvp, sources, plusargs)
    else:
        _compile_and_run_verilator(case_dir, verilator_build, sources, plusargs)

    counts = load_counts(paths["out"] / "counts_hw.txt")
    update_manifest(manifest_path, lambda manifest_data: _mark_run_complete(manifest_data, sim_name, counts))
    elapsed_cycles = counts.get("elapsed_cycles")
    if elapsed_cycles is None:
        print_case_report(case_dir, "stage: run", f"sim={sim_name}")
    else:
        print_case_report(case_dir, "stage: run", f"sim={sim_name} elapsed_cycles={elapsed_cycles}")


if __name__ == "__main__":
    main()
