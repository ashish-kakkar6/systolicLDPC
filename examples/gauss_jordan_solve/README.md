# `gauss_jordan_solve`

Direct solve example for the systolic Gauss-Jordan core over `GF(2)`.

This folder is the simplest matrix solve path in the repo: Python builds `A`
and `B`, SystemVerilog runs the solver, and Python reconstructs and checks `X`.

## Files

- `input_mats.py`: editable source of `A` and `B`.
- `common.py`: case, trace, and GF(2) helper functions.
- `build.py`: Python setup only.
- `run.py`: SystemVerilog compile and simulation only.
- `read.py`: Python verification only.

## Run

```sh
python examples/gauss_jordan_solve/build.py
python examples/gauss_jordan_solve/run.py
python examples/gauss_jordan_solve/read.py
```

## Outputs

- `cases/latest/`: symlink to the active case.
- `data/`: solver input memories.
- `out/`: bottom-trace dump and cycle counts.

`read.py` reports only:

- hardware/software solution match
- `A @ X == B`
- elapsed cycle counts
