# Mesh (`trapeziod_mesh.sv`)

Source file: `rtl/systolic_gauss_jordan/trapeziod_mesh.sv`


![Trapezoidal mesh figure (`M=3`, `N=4`, `L=2`)](../../_static/figures/systolic_lifted_gauss_jordan_trapeziod_mesh_m3_n4_l2.svg)
## Parameters
Systolic mesh for returning the solution $A^{-1}B$ for a system of equations $A X = B$ consisting of parameters
- `N`: number of rows of `A` and `B`
- `M`: number of columns of `A`
- `L`: number of columns of `B`

## Ports

- `clk`: clock 
- `rst`: synchronous reset
- `en_i`: global hold/advance enable
- `reduce_i`: reduce signal into `pe_diag` for reduce pass
- `data_top_i[(N+L)-1:0]`: top-edge data input vector for all global columns
- `data_bottom_o[L-1:0]`: bottom-boundary readout 
- `diag_data_out_o[N-1:0]`: debug export of each diagonal cell's downward data output
- `diag_reduce_in_o[N-1:0]`: debug export of the reduce bit seen by each diagonal cell
- `a_regs_flat_o[(N*N)-1:0]`: flattened export of all stored bits in the triangular `A` region
- `b_regs_flat_o[(N*L)-1:0]`: flattened export of all stored bits in the lifted `B` rectangle

## Structural organization

Coordinates with `col < row` are outside the trapezoid and are tied off to known
simulation values:

- `data_down_bus[row][col] = 0`
- `op_bus[row][col] = OP_PASS`
- `a_regs_flat_o[(row * N) + col] = 0` when `col < N`

At diagonal cells, the mesh instantiates [`pe_diag.sv`](pe-diag.md).

Each diagonal cell:

- receives vertical data from `data_top_i[col]` when `row == 0` else from  from `data_down_bus[row-1][col]`
- receives its row's reduce token from `reduce_in_bus[row]`
- drives the first horizontal opcode token for that row into `op_bus[row][col]`
- exports its local stored bit into `a_regs_flat_o[(row * N) + col]`

The diagonal downward data output is also exported through `diag_data_out_o[row]`.

At off-diagonal cells the mesh instantiates [`pe_col.sv`](pe-col.md).


Storage export depends on the global column:

- if `col < N`, the cell belongs to the triangular `A` region and exports into
  `a_regs_flat_o[(row * N) + col]`
- if `col >= N`, the cell belongs to the lifted `B` rectangle and exports into
  `b_regs_flat_o[(row * L) + (col - N)]`

## Internal buses

### Vertical data bus

`data_down_bus[row][col]` is the downward data emitted by cell `(row, col)`.
It is consumed by the cell at `(row + 1, col)`.

This is the only vertical data path in the structural mesh:

- top-edge cells read from `data_top_i`
- all lower active cells read from `data_down_bus[row-1][col]`

### Horizontal opcode bus

`op_bus[row][col]` is the opcode emitted by cell `(row, col)` and consumed by
the cell immediately to the right at `(row, col + 1)`.

This means:

- each diagonal cell seeds the row's opcode flow
- each `pe_col` forwards the opcode one hop to the right

## Reduce path

The reduce path is separate from the horizontal opcode bus and flows diagonally.
- the reduce pipeline has a delay for each diagonal hop `REDUCE_PIPE_STAGES= max(1, REDUCE_HOP_DELAY)`


For row `k > 0`:

- `reduce_out_bus[k-1]` enters the pipeline for row `k`
- after `REDUCE_PIPE_STAGES` enabled clock cycles, it appears on `reduce_in_bus[k]`

This is implemented with:

- `reduce_in_bus`
- `reduce_out_bus`
- `reduce_pipe_q[1:MESH_ROWS-1][0:REDUCE_PIPE_STAGES-1]`

## Export packing

### `a_regs_flat_o`

This export always has width `N * N`, even though only the upper-triangular
part corresponds to active cells.

Packing rule:

```text
a_regs_flat_o[(row * N) + col]
```

- active `A`-region cells write their stored bit there
- inactive coordinates below the diagonal are driven to `0`

### `b_regs_flat_o`

This export packs only the lifted rectangle on the right:

```text
b_regs_flat_o[(row * L) + (col - N)]
```

for `col >= N`.

So each mesh row contributes exactly `L` bits to `b_regs_flat_o`.

## Boundary export

The RTL makes only the lifted rectangle on the far right architecturally visible
at the bottom boundary:

```text
data_bottom_o[lift_col] = data_down_bus[N-1][N + lift_col]
```

for `lift_col = 0 .. L-1`.

## Debugging notes

The cocotb tests intentionally rely on stable generated hierarchy names.
The RTL comments call out these scopes and signals as part of the debugging
contract:

- `g_row`
- `g_col`
- `g_diag`
- `g_apply`
- `u_pe_diag`
- `u_pe_col`
- local signal name `data_in`

The explicit debug outputs `diag_data_out_o` and `diag_reduce_in_o` are also
part of that observability story.

## Test
- [Test file: `test_trapeziod_mesh.py`](../../test/systolic-gauss-jordan-tests/test-trapeziod-mesh.md)
```sh
make -C test/systolic_gauss_jordan TEST=trapeziod_mesh
```


- [Test file: `test_trapeziod_full_trace_reduce.py`](../../test/systolic-gauss-jordan-tests/test-trapeziod-full-trace-reduce.md)
traces the register behavior during the reduce phase.
```sh
make -C test/systolic_gauss_jordan TEST=trapeziod_full_trace_reduce
```

Back to [Systolic Gauss-Jordan](../systolic-gauss-jordan.md).
