---
orphan: true
---

# Examples

This section documents the direct Python wrapper around the production RTL
solver path.

## Available examples

- [NumPy solve flow](examples/gauss-jordan-solve.md)
- [GF(2) solution existence flow](examples/gauss-jordan-sol-existence.md)
- [Layered min-sum decode pipeline](usage/decoder/minsum-decode.md)
- [OSD decode pipeline](usage/decoder/osd-decode.md)

## Common flow

The direct solve flow:

1. write `a_rows.bin` and `b_rows.bin` from Python matrices
2. render a case-local testbench with the required `N`, `M`, and `L`
3. run `rtl/systolic_gauss_jordan/controller.sv`
4. inspect `data_bottom_trace.bin` either to reconstruct a solution or to check
   a trace-based property such as solution existence

Decoder-oriented examples start with the scalable `minsum_decode` flow and may
layer additional ranking and reduction logic around the same production solver,
as in `osd_decode`.
