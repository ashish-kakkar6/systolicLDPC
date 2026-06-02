# Gauss-Jordan solve

Example directory:
- `examples/gauss_jordan_solve`

This flow solves `A X = B` over $\mathrm{GF}(2)$ using the production systolic
Gauss-Jordan kernel.

## Commands

```sh
python3 examples/gauss_jordan_solve/build.py
python3 examples/gauss_jordan_solve/run.py
python3 examples/gauss_jordan_solve/read.py
```

## Inputs

Edit `examples/gauss_jordan_solve/input_mats.py` to define:

- `A`: shape `(N, N)`, full rank over $\mathrm{GF}(2)$
- `B`: shape `(N, L)`

## Outputs

Generated under `cases/<case_id>/` with `cases/latest` pointing at the active case:

- `A.npy`
- `B.npy`
- `X_software.npy`
- `out/data_bottom_trace.bin`
- `out/solver_counts.txt`
- `solver_trace.npy`
- `X_hardware.npy`

## Final checks

`read.py` checks:

- `X_hardware == X_software`
- `A @ X_hardware == B`

