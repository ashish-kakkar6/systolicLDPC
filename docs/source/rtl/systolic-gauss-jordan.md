# Systolic Gauss-Jordan

```{toctree}
:maxdepth: 1
:hidden:

systolic-gauss-jordan-files/gj-pkg
systolic-gauss-jordan-files/delay-line
systolic-gauss-jordan-files/mem
systolic-gauss-jordan-files/input
systolic-gauss-jordan-files/controller
systolic-gauss-jordan-files/pe-diag
systolic-gauss-jordan-files/pe-col
systolic-gauss-jordan-files/trapeziod-mesh
```
This folder contains the production RTL for the systolic Gauss-Jordan path in
`rtl/systolic_gauss_jordan/`.

## Role

This subsystem implements the production GF(2) elimination kernel introduced on
the project homepage. It streams rows of the augmented system `[A | B]` through
a lifted trapezoidal mesh whose processing elements perform pivot detection,
row updates, and reduction using only local state and nearest-neighbor
communication.

## Production surface

The production top solves `A x = B` by streaming rows of `[A | B]` into the
mesh. The only architectural output exposed by the production top is the bottom
boundary trace `data_bottom_o`.

## Why systolic

The design uses a systolic organization because the target computation is
dominated by regular GF(2) row operations with predictable communication
patterns. This makes the array suitable for FPGA-oriented studies in which
throughput, locality, and control simplicity matter as much as arithmetic
count.

## RTL overview

Row `r` begins at global column `r`. The first active cell on that row is a
`pe_diag` instance, and every active cell to its right is a `pe_col` instance.
Data enters from the top edge and moves downward within a global column.
Opcodes enter each row at the diagonal cell and move rightward across the active region.

The production path is intentionally small:
- `input.sv` reads A/B rows, applies the stagger schedule, and feeds the mesh
- `controller.sv` owns the run window and reduce pulse
- `pe_diag.sv`, `pe_col.sv`, and `trapeziod_mesh.sv` implement the array
- `mem.sv`, `delay_line.sv`, and `gj_pkg.sv` provide the supporting primitives

## Resource scaling

Because the architecture is regular and parameterized, its resource cost can be
studied as a function of matrix dimensions, mesh shape, and scheduling
strategy. This makes the module useful both as an implementation vehicle and as
a platform for exploring hardware-performance tradeoffs in decoder design.

## Module map

| Source file | Documentation page | Role in the subsystem |
| --- | --- | --- |
| `rtl/systolic_gauss_jordan/gj_pkg.sv` | [Shared package](systolic-gauss-jordan-files/gj-pkg.md) | Canonical home for opcode definitions and shared data types |
| `rtl/systolic_gauss_jordan/delay_line.sv` | [Delay line](systolic-gauss-jordan-files/delay-line.md) | Small reusable timing primitive used by feeders and wrappers |
| `rtl/systolic_gauss_jordan/mem.sv` | [Memory](systolic-gauss-jordan-files/mem.md) | Simple synchronous storage block for experiments and examples |
| `rtl/systolic_gauss_jordan/input.sv` | [Minimal input pipeline](systolic-gauss-jordan-files/input.md) | Collapsed production feeder from A/B RAMs to the staggered mesh ingress |
| `rtl/systolic_gauss_jordan/controller.sv` | [Bottom-trace top](systolic-gauss-jordan-files/controller.md) | Minimal production top that exposes only the bottom architectural trace |
| `rtl/systolic_gauss_jordan/pe_diag.sv` | [Diagonal PE](systolic-gauss-jordan-files/pe-diag.md) | Left-edge pivot cell that generates or forwards row control |
| `rtl/systolic_gauss_jordan/pe_col.sv` | [Column PE](systolic-gauss-jordan-files/pe-col.md) | Interior/right processing cell that applies the diagonal opcode |
| `rtl/systolic_gauss_jordan/trapeziod_mesh.sv` | [Trapezoidal mesh](systolic-gauss-jordan-files/trapeziod-mesh.md) | Structural mesh tying the lifted array together |

## How to test this now

The matching public cocotb suite is documented in
[Test: Systolic Gauss-Jordan](../test/systolic-gauss-jordan.md).
The fastest useful commands are:

```sh
make -C test/systolic_gauss_jordan TEST=pe_diag
make -C test/systolic_gauss_jordan TEST=pe_col
make -C test/systolic_gauss_jordan TEST=trapeziod_mesh
make -C test/systolic_gauss_jordan TEST=trapeziod_full_trace_reduce
```
