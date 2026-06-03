# `gauss_jordan_sol_existence`

Forward-pass existence check for `A x = b` over `GF(2)`.

## Purpose

This flow uses the same systolic solver stack as `gauss_jordan_solve`, but it
only checks whether each right-hand side column is solvable. It does not
reconstruct the witness vector.

## Files

- `input_mats.py`: editable source of `A` and `B`.
- `common.py`: case and existence-check helpers.
- `build.py`: Python setup only. Builds one immutable case.
- `run.py`: SystemVerilog compile and simulation only.
- `read.py`: Python verification only.
- `tb_example_gauss_jordan_sol_existence.sv`: top-level testbench for this flow.

## Run

```sh
./.venv/bin/python examples/gauss_jordan_sol_existence/build.py
./.venv/bin/python examples/gauss_jordan_sol_existence/run.py
./.venv/bin/python examples/gauss_jordan_sol_existence/read.py
```

## Outputs

- `cases/latest/`: symlink to the active case.
- `data/`: solver input memories.
- `out/`: bottom-trace dump, existence flags, and cycle counts.

## Final checks

`read.py` reports only:

- hardware/software existence agreement
- per-column existence vector
- elapsed cycle counts
