# `osd_decode`

Standalone OSD hardware example driven by a Stim-backed case.

## Purpose

This is the direct OSD flow. Python builds a Stim-backed case, SystemVerilog
runs the ranker, controller, and reduced solver, and Python checks the final
artifacts.

## Files

- `stim_example.py`: deterministic Stim source for the default case.
- `dem_mat.py`: DEM-to-matrix helper used by `stim_example.py`.
- `case.py`: exports the default problem instance.
- `common.py`: quantization, GF(2), and manifest helpers.
- `build.py`: Python setup only. Builds one immutable case.
- `run.py`: SystemVerilog compile and simulation only.
- `read.py`: Python verification only.
- `build_batch.py`, `run_batch.py`, `read_batch.py`: many-shot wrapper around the same hardware path.
- `tb_osd_decode.sv`: top-level testbench for the single-case flow.

## Run

Single case:

```sh
./.venv/bin/python examples/osd_decode/build.py
./.venv/bin/python examples/osd_decode/run.py
./.venv/bin/python examples/osd_decode/read.py
```

Batch:

```sh
./.venv/bin/python examples/osd_decode/build_batch.py --shots 1000
./.venv/bin/python examples/osd_decode/run_batch.py --sim verilator --jobs 8
./.venv/bin/python examples/osd_decode/read_batch.py
```

## Outputs

- `cases/latest/`: symlink to the active single-shot case.
- `batches/latest/`: symlink to the active batch.
- `problem/`: `H`, `sigma`, quantized scores, and cutoff memories.
- `out/`: selected columns, reduced system, solution vectors, and cycle counts.

## Final checks

`read.py` reports only:

- selected columns
- reduced matrix and syndrome
- `x` and scattered `F`
- `H @ F == sigma`
- `logicals @ F == actual_observables`
