# Test File: `test_trapeziod_mesh.py`

Back to [Test: Systolic Gauss-Jordan](../systolic-gauss-jordan.md).

Source file: `test/systolic_gauss_jordan/test_trapeziod_mesh.py`

## RTL counterpart

- [RTL file: `trapeziod_mesh.sv`](../../rtl/systolic-gauss-jordan-files/trapeziod-mesh.md)
- [RTL file: `pe_diag.sv`](../../rtl/systolic-gauss-jordan-files/pe-diag.md)
- [RTL file: `pe_col.sv`](../../rtl/systolic-gauss-jordan-files/pe-col.md)

## What this test checks

This is the direct forward-flow mesh regression. It does not assert the whole
reduce trace; instead, it checks the structural array behavior on a checked-in
sample case.

The test:

- loads the sample case from JSON
- builds the staggered top-edge input streams in Python
- drives the mesh without reduce mode
- compares bottom-row outputs against the Python model cycle by cycle
- checks that opcode launch and horizontal propagation occur at the expected times

## How to run it

```sh
make -C test/systolic_gauss_jordan TEST=trapeziod_mesh
```

## What to inspect while reading it

- `build_top_input_streams()` and `sample_streams_at_cycle()` usage
- the per-cycle bottom-output comparison
- the lock/add propagation checks across row `0`

## Python source

```{literalinclude} ../../../../test/systolic_gauss_jordan/test_trapeziod_mesh.py
:language: python
:linenos:
```
