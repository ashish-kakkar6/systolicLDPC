# `osd_decode`

Standalone OSD hardware example driven by a Stim-backed case.

This folder is the direct OSD path: Python builds a case, SystemVerilog runs the
ranker + controller + reduced solver, and Python checks the final artifacts.

## Files

- `stim_example.py`: deterministic Stim source for the default case.
- `dem_mat.py`: DEM-to-matrix helper used by `stim_example.py`.
- `case.py`: exports the default problem instance.
- `common.py`: quantization, GF(2), and manifest helpers.
- `build.py`: Python setup only for one case.
- `run.py`: SystemVerilog compile and simulation only for one case.
- `read.py`: Python verification only for one case.
- `build_batch.py`, `run_batch.py`, `read_batch.py`: many-shot wrapper around the same hardware path.

## Run

Single case:

```sh
python examples/osd_decode/build.py
python examples/osd_decode/run.py
python examples/osd_decode/read.py
```

Batch:

```sh
python examples/osd_decode/build_batch.py --shots 1000
python examples/osd_decode/run_batch.py --sim verilator --jobs 8
python examples/osd_decode/read_batch.py
```

## Outputs

- `cases/latest/`: symlink to the active single-shot case.
- `batches/latest/`: symlink to the active batch.
- `problem/`: `H`, `sigma`, quantized scores, and cutoff memories.
- `out/`: selected columns, reduced system, solution vectors, and cycle counts.

`read.py` reports only the final hardware/software checks:

- selected columns
- reduced matrix and syndrome
- `x` and scattered `F`
- `H @ F == sigma`
- `logicals @ F == actual_observables`
