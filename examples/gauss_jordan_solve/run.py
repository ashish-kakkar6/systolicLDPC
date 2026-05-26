#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from common import (
    REPO_ROOT,
    ensure_dirs,
    load_counts,
    load_manifest,
    load_meta,
    print_case_report,
    resolve_case_dir,
    update_manifest,
    verify_manifest_inputs,
)


def _compile_and_run_iverilog(case_dir: Path, sim_vvp: Path, sources: list[Path], plusargs: list[str]) -> None:
    subprocess.run(
        ["iverilog", "-g2012", "-o", str(sim_vvp), "-s", "tb_example_gauss_jordan", *map(str, sources)],
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
            "tb_example_gauss_jordan",
            "--Mdir",
            str(build_dir),
            *map(str, sources),
        ],
        check=True,
        cwd=case_dir,
    )
    subprocess.run([str(build_dir / "Vtb_example_gauss_jordan"), *plusargs], check=True, cwd=case_dir)


def _mark_run_complete(manifest_data: dict, sim_name: str, counts: dict[str, int]) -> None:
    manifest_data["stages"]["ran"] = True
    manifest_data["stages"]["read"] = False
    manifest_data["run"] = {
        "sim": sim_name,
        "cycles": counts,
        "outputs": {
            "bottom_trace_bin": "out/data_bottom_trace.bin",
            "counts_txt": "out/solver_counts.txt",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-dir", type=Path, default=Path(__file__).resolve().parent / "cases" / "latest")
    parser.add_argument("--sim", choices=["iverilog", "verilator"], default=None)
    parser.add_argument("--waves", type=int, default=0)
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

    sim_vvp = paths["out"] / "tb_example_gauss_jordan.vvp"
    verilator_build = paths["out"] / "verilator"
    wave_file = paths["out"] / "tb_example_gauss_jordan.fst"
    counts_path = paths["out"] / "solver_counts.txt"
    bottom_bin = paths["out"] / "data_bottom_trace.bin"
    for stale_name in ("solver_trace.npy", "X_hardware.npy"):
        stale_path = case_dir / stale_name
        if stale_path.exists():
            stale_path.unlink()

    sources = [
        REPO_ROOT / "rtl/systolic_gauss_jordan/gj_pkg.sv",
        REPO_ROOT / "rtl/systolic_gauss_jordan/delay_line.sv",
        REPO_ROOT / "rtl/systolic_gauss_jordan/mem.sv",
        REPO_ROOT / "rtl/systolic_gauss_jordan/pe_diag.sv",
        REPO_ROOT / "rtl/systolic_gauss_jordan/pe_col.sv",
        REPO_ROOT / "rtl/systolic_gauss_jordan/trapeziod_mesh.sv",
        REPO_ROOT / "rtl/systolic_gauss_jordan/input.sv",
        REPO_ROOT / "rtl/systolic_gauss_jordan/controller.sv",
        case_dir / manifest["files"]["tb_sv"],
    ]

    plusargs = [
        f"+A_BIN={case_dir / manifest['files']['a_rows_bin']}",
        f"+B_BIN={case_dir / manifest['files']['b_rows_bin']}",
        f"+BOTTOM_BIN={bottom_bin}",
        f"+COUNTS_OUT={counts_path}",
        f"+TIMEOUT_CYCLES={int(meta['run_cycles']) + 32}",
        f"+REDUCE_ENABLE={int(meta['reduce_enable'])}",
        f"+REDUCE_START={int(meta['reduce_start'])}",
        f"+RUN_CYCLES={int(meta['run_cycles'])}",
        f"+WAVES={args.waves}",
        f"+WAVE_FILE={wave_file}",
    ]

    if sim_name == "iverilog":
        _compile_and_run_iverilog(case_dir, sim_vvp, sources, plusargs)
    else:
        _compile_and_run_verilator(case_dir, verilator_build, sources, plusargs)

    counts = load_counts(counts_path)
    update_manifest(manifest_path, lambda manifest_data: _mark_run_complete(manifest_data, sim_name, counts))

    elapsed_cycles = counts.get("elapsed_cycles")
    if elapsed_cycles is None:
        print_case_report(case_dir, "stage: run", f"sim={sim_name}")
    else:
        print_case_report(case_dir, "stage: run", f"sim={sim_name} elapsed_cycles={elapsed_cycles}")


if __name__ == "__main__":
    main()
