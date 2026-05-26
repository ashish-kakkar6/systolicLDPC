# Example: `gauss_jordan_solve`

Example directory:
- `examples/gauss_jordan_solve`

This example solves the system of equations $A X = B$ over $GF(2)$ using the
production systolic Gauss-Jordan path, with the same case/manifest workflow as
`osd_decode`.

Edit:
- `input_mats.py`
by defining 
- `A`: shape `(N, N)` of full rank over `GF(2)`
- `B`: shape `(N, L)`

To create a new immutable case directory with software reference outputs, run
```sh
python3 examples/gauss_jordan_solve/build.py
```
Rows are written to `a_rows.bin` and `b_rows.bin` with each row reversed so the
RTL sees the expected column order.

To run the hardware solve, run
```
python3 examples/gauss_jordan_solve/run.py
```
`run.py` verifies `manifest.json`, records simulator outputs, and writes the
measured cycle counts to `out/solver_counts.txt`.

To reconstruct the hardware solution and verify it, run
```
python3 examples/gauss_jordan_solve/read.py
```

`read.py` checks:

- `X_hardware == X_software`
- `A @ X_hardware == B`

## Commands

```sh
python3 examples/gauss_jordan_solve/build.py
python3 examples/gauss_jordan_solve/run.py
python3 examples/gauss_jordan_solve/read.py
```

## Outputs

Generated under `cases/<case_id>/` with `cases/latest` pointing at the active case:

- `A.npy`
- `B.npy`
- `X_software.npy`
- `out/data_bottom_trace.bin`
- `out/solver_counts.txt`
- `solver_trace.npy`
- `X_hardware.npy`
