# Shared Package (`gj_pkg.sv`)
Source file: `rtl/systolic_gauss_jordan/gj_pkg.sv`

Shared types for the systolic Gauss-Jordan modules.

`opcode_t` is  a two-bit enum with:
- `OP_PASS` : Forward the incoming data bit unchanged.
- `OP_SWAP` : Emit the stored bit and load the incoming bit.
- `OP_ADD`  :  Emit the XOR of the incoming bit and the stored bit.

Back to [Systolic Gauss-Jordan](../systolic-gauss-jordan.md).
