# Example: `gauss_jordan_sol_existence`

Example directory:
- `examples/gauss_jordan_sol_existence`

This example checks solution existence, not solution recovery.

For each column `b_j` of `B`, it answers:

- does `A x = b_j` have a solution over `GF(2)`?

All `L` answers are produced in one hardware run.

## Inputs

Edit `examples/gauss_jordan_sol_existence/input_mats.py` to define:

- `A`: shape `(M, N)`
- `B`: shape `(M, L)`

`build.py` computes the software existence vector and writes the row files used
by the RTL driver.

The checked-in default input set is a deterministic mixed case with:

- `A`: shape `(12, 18)` and rank `10`
- `B`: shape `(12, 6)`
- alternating solvable / unsolvable RHS columns

## Commands

Build a new immutable case:

```sh
python3 examples/gauss_jordan_sol_existence/build.py
```

Run the hardware check:

```sh
python3 examples/gauss_jordan_sol_existence/run.py
```

Read the bottom trace and compare hardware against software:

```sh
python3 examples/gauss_jordan_sol_existence/read.py
```

`read.py` checks:

- `has_solution_hw[col] == has_solution_sw[col]`

`run.py` writes the hardware-computed existence vector directly from RTL.
`read.py` loads that result, then cross-checks it against the dumped bottom
trace for debug.

## Bottom Trace Interpretation

The default forward-pass run window is:

- `2 * N + M + L - 1`

The simulator writes bottom-trace text rows in bit order `L-1 ... 0`. `read.py`
reverses each row back into logical RHS-column order before checking existence.

The hardware rule is:

- `has_solution_hw[col] = True` iff no `1` appears in logical column `col`
  during the first `configured_run_cycles` bottom-trace samples

That rule is implemented directly in
`rtl/systolic_gauss_jordan/solution_existence_monitor.sv`, wrapped by
`rtl/systolic_gauss_jordan/controller_sol_existence.sv`.

The bottom stream is skewed across columns in time, so the hardware monitor
tracks each column independently and records the first contradiction cycle per
column in `first_bottom_one_cycle_hw`.

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
