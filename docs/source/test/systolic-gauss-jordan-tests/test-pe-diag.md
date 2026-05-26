# Test File: `test_pe_diag.py`

Back to [Test: Systolic Gauss-Jordan](../systolic-gauss-jordan.md).

Source file: `test/systolic_gauss_jordan/test_pe_diag.py`

## RTL counterpart

- [RTL file: `pe_diag.sv`](../../rtl/systolic-gauss-jordan-files/pe-diag.md)
- [RTL file: `gj_pkg.sv`](../../rtl/systolic-gauss-jordan-files/gj-pkg.md)

## What this test checks

This page corresponds to the direct cocotb truth-table test for the diagonal
processing element. It is the shortest path from the RTL page to an executable
behavior check.

The test:

- resets the DUT
- optionally preloads the internal diagonal state bit
- enumerates `reduce_sig_i`, previous state, and `data_i`
- compares observed outputs and next state against the Python golden model

## How to run it

```sh
make -C test/systolic_gauss_jordan TEST=pe_diag
```

## What to inspect while reading it

- `reset_dut()` for the reset convention used by the suite
- `step()` for the cycle-by-cycle driver pattern
- `pe_diag_truth_table_exhaustive()` for the actual behavioral contract

## Python source

```{literalinclude} ../../../../test/systolic_gauss_jordan/test_pe_diag.py
:language: python
:linenos:
```
