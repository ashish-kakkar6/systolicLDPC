# `gauss_jordan_solve`

Direct solve example for the systolic Gauss-Jordan core over `GF(2)`.

## Purpose

This is the smallest end-to-end solver flow in the repository. Python builds
`A` and `B`, SystemVerilog runs the solver, and Python reconstructs and checks
the solution matrix `X`.

## Files

- `input_mats.py`: editable source of `A` and `B`.
- `common.py`: case, trace, and GF(2) helper functions.
- `build.py`: Python setup only. Builds one immutable case.
- `run.py`: SystemVerilog compile and simulation only.
- `read.py`: Python verification only.
- `tb_example_gauss_jordan.sv`: top-level testbench for this flow.

## Run

```sh
./.venv/bin/python examples/gauss_jordan_solve/build.py
./.venv/bin/python examples/gauss_jordan_solve/run.py
./.venv/bin/python examples/gauss_jordan_solve/read.py
```

## Outputs

- `cases/latest/`: symlink to the active case.
- `data/`: solver input memories.
- `out/`: bottom-trace dump and cycle counts.

## Final checks

`read.py` reports only:

- hardware/software solution match
- `A @ X == B`
- elapsed cycle counts
