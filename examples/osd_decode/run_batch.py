#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from common import (
    ensure_batch_dirs,
    load_manifest,
    load_meta,
    osd_decode_rtl_sources,
    print_batch_report,
    resolve_case_dir,
    update_manifest,
    verify_batch_manifest_inputs,
)


def _shot_name(shot_index: int) -> str:
    return f"shot_{shot_index:06d}"


def _compile_iverilog(batch_dir: Path, sim_vvp: Path, sources: list[Path]) -> None:
    subprocess.run(
        ["iverilog", "-g2012", "-o", str(sim_vvp), "-s", "tb_osd_decode", *map(str, sources)],
        check=True,
        cwd=batch_dir,
    )


def _compile_verilator(batch_dir: Path, build_dir: Path, sources: list[Path]) -> None:
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
        cwd=batch_dir,
    )


def _run_one_shot(
    *,
    sim_name: str,
    batch_dir: Path,
    shared_problem_dir: Path,
    binary_path: Path,
    shot_dir: Path,
    timeout_cycles: int,
) -> None:
    shot_problem_dir = shot_dir / "problem"
    shot_out_dir = shot_dir / "out"
    shot_out_dir.mkdir(parents=True, exist_ok=True)

    for stale_name in (
        "selected_indices_hw.txt",
        "h_reduced_hw.bin",
        "sigma_reduced_hw.bin",
        "counts_hw.txt",
        "x_hardware.bin",
        "F_hardware.bin",
        "x_trace_hw.bin",
    ):
        stale_path = shot_out_dir / stale_name
        if stale_path.exists():
            stale_path.unlink()

    plusargs = [
        f"+H_ROWS={shared_problem_dir / 'h_rows.mem'}",
        f"+SIGMA={shot_problem_dir / 'sigma.mem'}",
        f"+ESTIMATE={shared_problem_dir / 'estimate.hex'}",
        f"+CUTOFF={shared_problem_dir / 'cutoff.hex'}",
        f"+SELECTED_OUT={shot_out_dir / 'selected_indices_hw.txt'}",
        f"+H_REDUCED_OUT={shot_out_dir / 'h_reduced_hw.bin'}",
        f"+SIGMA_REDUCED_OUT={shot_out_dir / 'sigma_reduced_hw.bin'}",
        f"+COUNTS_OUT={shot_out_dir / 'counts_hw.txt'}",
        f"+X_HARDWARE_OUT={shot_out_dir / 'x_hardware.bin'}",
        f"+F_HARDWARE_OUT={shot_out_dir / 'F_hardware.bin'}",
        f"+TIMEOUT_CYCLES={timeout_cycles}",
    ]

    command = ["vvp", str(binary_path), *plusargs] if sim_name == "iverilog" else [str(binary_path), *plusargs]
    subprocess.run(command, check=True, cwd=batch_dir)


def _mark_run_complete(manifest_data: dict, *, sim_name: str, jobs: int) -> None:
    manifest_data["stages"]["ran"] = True
    manifest_data["stages"]["read"] = False
    manifest_data["run"] = {
        "sim": sim_name,
        "jobs": int(jobs),
        "outputs_root": "shots",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", type=Path, default=Path(__file__).resolve().parent / "batches" / "latest")
    parser.add_argument("--sim", choices=["iverilog", "verilator"], default=None)
    parser.add_argument("--jobs", type=int, default=0)
    args = parser.parse_args()

    batch_dir = resolve_case_dir(args.batch_dir)
    paths = ensure_batch_dirs(batch_dir)
    manifest_path = batch_dir / "manifest.json"
    manifest = load_manifest(manifest_path)
    verify_batch_manifest_inputs(batch_dir, manifest)
    meta = load_meta(batch_dir / "meta.json")

    sim_name = args.sim or str(manifest.get("sim_default", "iverilog"))
    required_tools = ["iverilog", "vvp"] if sim_name == "iverilog" else ["verilator"]
    missing_tools = [tool for tool in required_tools if shutil.which(tool) is None]
    if missing_tools:
        raise FileNotFoundError(f"required simulator tools not found on PATH: {', '.join(missing_tools)}")

    tb_path = batch_dir / manifest["files"]["tb_sv"]
    sources = osd_decode_rtl_sources(tb_path)
    sim_vvp = paths["out"] / "tb_osd_decode.vvp"
    verilator_build = paths["out"] / "verilator"
    if sim_name == "iverilog":
        _compile_iverilog(batch_dir, sim_vvp, sources)
        binary_path = sim_vvp
    else:
        _compile_verilator(batch_dir, verilator_build, sources)
        binary_path = verilator_build / "Vtb_osd_decode"

    shot_count = int(meta["shots"])
    timeout_cycles = int(meta["timeout_cycles"])
    jobs = int(args.jobs) if args.jobs > 0 else max(1, os.cpu_count() or 1)
    shared_problem_dir = paths["problem"]
    shot_dirs = [paths["shots"] / _shot_name(shot_index) for shot_index in range(shot_count)]

    with ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = [
            executor.submit(
                _run_one_shot,
                sim_name=sim_name,
                batch_dir=batch_dir,
                shared_problem_dir=shared_problem_dir,
                binary_path=binary_path,
                shot_dir=shot_dir,
                timeout_cycles=timeout_cycles,
            )
            for shot_dir in shot_dirs
        ]
        for future in as_completed(futures):
            future.result()

    update_manifest(manifest_path, lambda manifest_data: _mark_run_complete(manifest_data, sim_name=sim_name, jobs=jobs))
    print_batch_report(batch_dir, "stage: run", f"sim={sim_name} shots={shot_count} jobs={jobs}")


if __name__ == "__main__":
    main()
