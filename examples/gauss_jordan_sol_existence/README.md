# `gauss_jordan_sol_existence`

Forward-pass existence check for `A x = b` over `GF(2)`.

This example uses the same solver stack as `gauss_jordan_solve`, but it only
checks whether each right-hand side column is solvable. It does not reconstruct
the witness vector.

## Files

- `input_mats.py`: editable source of `A` and `B`.
- `common.py`: case and existence-check helpers.
- `build.py`: Python setup only.
- `run.py`: SystemVerilog compile and simulation only.
- `read.py`: Python verification only.

## Run

```sh
python examples/gauss_jordan_sol_existence/build.py
python examples/gauss_jordan_sol_existence/run.py
python examples/gauss_jordan_sol_existence/read.py
```

## Outputs

- `cases/latest/`: symlink to the active case.
- `data/`: solver input memories.
- `out/`: bottom-trace dump, existence flags, and cycle counts.

`read.py` reports only:

- hardware/software existence agreement
- per-column existence vector
- elapsed cycle counts
