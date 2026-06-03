# Gauss-Jordan solution existence

Example directory:
- `examples/gauss_jordan_sol_existence`

This flow uses the systolic Gauss-Jordan path to determine whether
`A x = B` is consistent over $\mathrm{GF}(2)$.

## Commands

```sh
./.venv/bin/python examples/gauss_jordan_sol_existence/build.py
./.venv/bin/python examples/gauss_jordan_sol_existence/run.py
./.venv/bin/python examples/gauss_jordan_sol_existence/read.py
```

## Inputs

Edit `examples/gauss_jordan_sol_existence/input_mats.py` to define:

- `A`: shape `(M, N)`
- `B`: shape `(M, L)`

The checked-in default case is deterministic and mixes solvable and unsolvable
right-hand sides.

## Outputs

Generated under `cases/<case_id>/` with `cases/latest` pointing at the active case:

- `A.npy`
- `B.npy`
- `manifest.json`
- `meta.json`
- `out/data_bottom_trace.bin`
- `out/has_solution_hw.txt`
- `out/first_one_cycle_hw.txt`
- `out/solver_counts.txt`
- `bottom_trace.npy`

## Final checks

`read.py` checks:

- `has_solution_hw[col] == has_solution_sw[col]`
