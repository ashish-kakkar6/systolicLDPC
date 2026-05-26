# Test File: `test_trapeziod_full_trace_reduce.py`

Back to [Test: Systolic Gauss-Jordan](../systolic-gauss-jordan.md).

Source file: `test/systolic_gauss_jordan/test_trapeziod_full_trace_reduce.py`

## RTL counterpart

- [RTL file: `trapeziod_mesh.sv`](../../rtl/systolic-gauss-jordan-files/trapeziod-mesh.md)
- [RTL file: `pe_diag.sv`](../../rtl/systolic-gauss-jordan-files/pe-diag.md)
- [RTL file: `pe_col.sv`](../../rtl/systolic-gauss-jordan-files/pe-col.md)

## What this test checks

This is the most readable whole-mesh test in the lifted suite. It drives the
sample case through the mesh, launches reduce at the configured cycle, checks
timing expectations row by row, and writes a structured JSON trace that records
internal mesh state over time.

The test:

- loads the sample case and derives `M`, `N`, and `L`
- drives the mesh with the staggered top-edge stream
- pulses reduce at `reduce_pulse_cycle = M`
- captures `data_bottom_row`, diagonal data out, diagonal reduce mode, and the register matrix for every cycle
- writes the full trace JSON artifact
- checks that the reduce pulse reaches each diagonal row at the expected cycle

## How to run it

```sh
make -C test/systolic_gauss_jordan TEST=trapeziod_full_trace_reduce
```

## What to inspect while reading it

- `reduce_pulse_cycle` and `last_cycle` setup
- the per-cycle trace payload fields
- the final assertions on diagonal reduce arrival

## Python source

```{literalinclude} ../../../../test/systolic_gauss_jordan/test_trapeziod_full_trace_reduce.py
:language: python
:linenos:
```
