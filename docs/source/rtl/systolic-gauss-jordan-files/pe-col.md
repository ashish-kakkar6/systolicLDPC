# Column Processing Element (`pe_col.sv`)

Back to [Systolic Gauss-Jordan](../systolic-gauss-jordan.md).

Source file: `rtl/systolic_gauss_jordan/pe_col.sv`

Elementary Processing element used across the systolic mesh [Trapezoidal mesh (`trapeziod_mesh.sv`)](trapeziod-mesh.md)
which processes incoming columns (non-pivot members of each row). The opcode (`op_o`/`op_i`) enums are defined in [Shared package (`gj_pkg.sv`)](gj-pkg.md)

![Column PE block figure](../../_static/figures/systolic_lifted_gauss_jordan_pe_col.svg)

## Ports 
### Inputs

- `clk`: clock signal
- `rst`: reset
- `en_i`: enable
- `data_i`: data bit in
- `op_i`: op signal in

### Outputs

- `op_o`: op signal out
- `data_o`: data bit out
- `state_o`: internal register state out


## Behaviour
- receives opcodes (`op_o`/`op_i`) from pivot element ([Trapezoidal mesh (`pe_diag.sv`)](pe-diag.md)) which are transferred
horizontally 
- receives data bits (`data_in`) vertically which are used to update internal register `r` and determine `data_out` 
based on opcodes.

### Transition table

Notes:

- `r` is the current stored bit.
- `r_next` is the next stored bit.
- `data_o_next` is the combinational value later registered into `data_o`.
- `op_o` is the registered copy of `op_i` when `rst = 0` and `en_i = 1`.

#### Enabled data path (`rst = 0`, `en_i = 1`)

| `op_i` | `data_i` | `r` | `r_next` | `data_o_next` | `op_o` after clock | Meaning |
| --- | --- | --- | --- | --- | --- | --- |
| `OP_PASS` | `data_i` | `r` | `r` | `data_i` | `OP_PASS` | Forward vertical data unchanged |
| `OP_SWAP` | `data_i` | `r` | `data_i` | `r` | `OP_SWAP` | Emit stored bit and load incoming bit |
| `OP_LOCK` | `data_i` | `r` | `data_i` | `r` | `OP_LOCK` | Same local state update as `OP_SWAP` |
| `OP_ADD` | `data_i` | `r` | `r` | `r ^ data_i` | `OP_ADD` | Add incoming bit into the vertical stream over GF(2) |
| default | `data_i` | `r` | `r` | `data_i` | `op_i` | Fallback behaves like pass |

## Test 

- [Test file: `test_pe_col.py`](../../test/systolic-gauss-jordan-tests/test-pe-col.md) verifies truth table

```sh
make -C test/systolic_gauss_jordan TEST=pe_col
```
