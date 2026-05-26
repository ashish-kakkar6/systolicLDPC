#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from common import REPO_ROOT, ensure_dirs, load_manifest, load_meta, print_case_report, resolve_case_dir, update_manifest


def _compile_and_run_iverilog(case_dir: Path, sim_vvp: Path, sources: list[Path], plusargs: list[str]) -> None:
    subprocess.run(
        ["iverilog", "-g2012", "-o", str(sim_vvp), "-s", "tb_minsum_decode", *map(str, sources)],
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
            "--top-module",
            "tb_minsum_decode",
            "--Mdir",
            str(build_dir),
            *map(str, sources),
        ],
        check=True,
        cwd=case_dir,
    )
    subprocess.run([str(build_dir / "Vtb_minsum_decode"), *plusargs], check=True, cwd=case_dir)


def _mark_run_complete(manifest_data: dict, sim_name: str) -> None:
    manifest_data["stages"]["ran"] = True
    manifest_data["stages"]["read"] = False
    manifest_data["run"] = {
        "sim": sim_name,
        "outputs": {
            "hard_decision_bin": "out/hard_decision_hw.bin",
            "posterior_hex": "out/posterior_llr_hw.hex",
            "counts_txt": "out/counts_hw.txt",
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

    sim_vvp = paths["out"] / "tb_minsum_decode.vvp"
    verilator_build = paths["out"] / "verilator"
    counts_path = paths["out"] / "counts_hw.txt"
    hard_path = paths["out"] / "hard_decision_hw.bin"
    posterior_path = paths["out"] / "posterior_llr_hw.hex"

    sources = [
        REPO_ROOT / "rtl/minsum_bp/minsum_pkg.sv",
        REPO_ROOT / "rtl/minsum_bp/minsum_row_engine.sv",
        REPO_ROOT / "rtl/minsum_bp/minsum_decode_top.sv",
        case_dir / manifest["files"]["tb_sv"],
    ]

    plusargs = [
        f"+PRIOR_HEX={case_dir / manifest['files']['prior_llr_hex']}",
        f"+SYNDROME_MEM={case_dir / manifest['files']['syndrome_mem']}",
        f"+ROW_PTR_HEX={case_dir / manifest['files']['row_ptr_hex']}",
        f"+EDGE_VAR_HEX={case_dir / manifest['files']['edge_var_hex']}",
        f"+HARD_OUT={hard_path}",
        f"+POSTERIOR_OUT={posterior_path}",
        f"+COUNTS_OUT={counts_path}",
        f"+MAX_ITER={int(meta['max_iter'])}",
        f"+TIMEOUT_CYCLES={int(meta['timeout_cycles'])}",
        "+RESULT_MODE=0",
    ]

    if sim_name == "iverilog":
        _compile_and_run_iverilog(case_dir, sim_vvp, sources, plusargs)
    else:
        _compile_and_run_verilator(case_dir, verilator_build, sources, plusargs)

    update_manifest(manifest_path, lambda manifest_data: _mark_run_complete(manifest_data, sim_name))
    print_case_report(case_dir, "stage: run", f"sim={sim_name}")


if __name__ == "__main__":
    main()
