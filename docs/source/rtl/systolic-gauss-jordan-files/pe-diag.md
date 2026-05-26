# Diagonal Processing Element (`pe_diag.sv`)

Back to [Systolic Gauss-Jordan](../systolic-gauss-jordan.md).

Source file: `rtl/systolic_gauss_jordan/pe_diag.sv`


Elementary Processing element used across the systolic mesh [Trapezoidal mesh (`trapeziod_mesh.sv`)](trapeziod-mesh.md)
which processes diagonal elements of incoming columns (pivots of each row). The opcode (`op_o`/`op_i`) enums are defined in [Shared package (`gj_pkg.sv`)](gj-pkg.md)

![Diagonal PE block figure](../../_static/figures/systolic_lifted_gauss_jordan_pe_diag.svg)


## Ports

### Inputs

- `clk`: clock signal
- `rst`: reset
- `en_i`: enable 
- `data_i`: data bit in
- `reduce_sig_i`: reduce signal activating reduction for the pivot column.

### Outputs

- `data_o`: data bit out
- `op_o`: opcode out
- `reduce_sig_o`: reduce signal activating reduction for the pivot column.

## Behaviour

- During the forward pass: drives the rightward movement of opcode which signals weather a pivot element has been found
- Drives the downward data output seen by the next row
- During the reduce pass: forwards a delayed diagonal `reduce` signal 

### Transition table

Notes:

- `r` is the current stored bit.
- `r_next` is the next stored bit.
- `data_out_next` is the combinational value later registered into `data_o`.
- `op_out_next` is the combinational value later registered into `op_o`.
- `state_o` is always the registered state bit `r`.

#### Reduce signal forwarding

| `rst` | `reduce_sig_i` | `reduce_sig_o` | Meaning |
| --- | --- | --- | --- |
| `1` | `x` | `0` | Mask reduce during reset |
| `0` | `reduce_sig_i` | `reduce_sig_i` | Forward reduce unchanged |

#### Enabled data path (`rst = 0`, `en_i = 1`)

| `reduce_sig_i` | `data_i` | `r` | `r_next` | `data_out_next` | `op_o` after clock | Meaning |
| --- | --- | --- | --- | --- | --- | --- |
| `1` | `data_i` | `1` | `1` | `data_i` | `OP_SWAP` | Active reduce branch |
| `0` or `1` | `0` | `r` | `r` | `0` | `OP_PASS` | Zero input keeps state and drives zero downward |
| `0` or `1` | `1` | `0` | `1` | `0` | `OP_LOCK` | First `1` locks the diagonal state |
| `0` | `1` | `1` | `1` | `0` | `OP_ADD` | Forward-mode add branch after the pivot is already locked |

Notes:

- `op_o after clock` is the registered copy of `op_out_next`.
- `data_out_next` defaults to `1'b0` before the branch logic and is only
  overridden in the active reduce branch.


### Test

- [Test file: `test_pe_diag.py`](../../test/systolic-gauss-jordan-tests/test-pe-diag.md)

```sh
make -C test/systolic_gauss_jordan TEST=pe_diag
```
