# Test File: `test_pe_col.py`

Back to [Test: Systolic Gauss-Jordan](../systolic-gauss-jordan.md).

Source file: `test/systolic_gauss_jordan/test_pe_col.py`

## RTL counterpart

- [RTL file: `pe_col.sv`](../../rtl/systolic-gauss-jordan-files/pe-col.md)
- [RTL file: `gj_pkg.sv`](../../rtl/systolic-gauss-jordan-files/gj-pkg.md)

## What this test checks

This is the direct cocotb truth-table test for the column processing element.
It exercises the local stored bit, the incoming opcode token, and the emitted
data/output behavior for every relevant small input combination.

The test:

- resets the DUT
- optionally preloads the local stored bit
- enumerates `data_i` and all opcode values
- compares observed outputs and next state against the Python golden model

## How to run it

```sh
make -C test/systolic_gauss_jordan TEST=pe_col
```

## What to inspect while reading it

- `reset_dut()` for the suite-wide reset pattern
- `step()` for the one-cycle drive-and-sample helper
- `pe_col_truth_table_exhaustive()` for the contract being asserted

## Python source

```{literalinclude} ../../../../test/systolic_gauss_jordan/test_pe_col.py
:language: python
:linenos:
```
