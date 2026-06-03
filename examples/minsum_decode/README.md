# `minsum_decode`

Standalone row-layered normalized min-sum decode example.

## Purpose

This is the standalone decoder-facing flow for the repository's active
message-passing path. It builds one deterministic Stim-backed case, runs one
SystemVerilog decoder, and checks the final result in Python.

## Files

- `stim_example.py`: deterministic Stim source used by the default case.
- `case.py`: exports `H`, `syndrome`, `prior_llr`, and `max_iter`.
- `common.py`: quantization, graph-build, and software min-sum reference helpers.
- `build.py`: Python setup only. Writes one immutable case under `cases/<case_id>/`.
- `run.py`: SystemVerilog compile and simulation only.
- `read.py`: Python verification only.
- `tb_minsum_decode.sv`: top-level testbench for this flow.

## Run

```sh
./.venv/bin/python examples/minsum_decode/build.py
./.venv/bin/python examples/minsum_decode/run.py
./.venv/bin/python examples/minsum_decode/read.py
```

## Outputs

- `cases/latest/`: symlink to the active case.
- `problem/`: BP preload files such as `row_ptr.mem`, `edge_var.mem`, and `prior_llr.hex`.
- `out/`: hardware outputs and cycle counts.

## Final checks

`read.py` reports only:

- hardware/software agreement
- `H @ e == sigma`
- residual weight
- `logicals @ e == actual_observables` when logicals are present
