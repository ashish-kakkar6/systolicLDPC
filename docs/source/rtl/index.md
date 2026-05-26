# RTL

```{toctree}
:maxdepth: 1
:hidden:

systolic-gauss-jordan
minsum-bp
```

This section is the hardware map for the shipped RTL under `rtl/`.
Installation and example usage are covered elsewhere.

## Current split

- `rtl/systolic_gauss_jordan/`
  Core production GF(2) elimination kernel.
- `rtl/osd_control/`
  Decoder-side orchestration around the solver:
  problem store, ranking wrapper, reduced-system control, and solve launch.
- `rtl/minsum_bp/`
  Scalable decoder front-end built around row-layered normalized min-sum.
- `rtl/sort/`
  Low-precision ranking block used by the decoder path.

The file-level docs in this section focus on the production solver kernel.

## Reading order

1. Start with [Systolic Gauss-Jordan](systolic-gauss-jordan.md) for the core solver contract.
2. Read `controller.sv` and `input.sv` to understand the public solver-facing path.
3. Read `trapeziod_mesh.sv`, `pe_diag.sv`, and `pe_col.sv` for the cell-level array behavior.
4. Use `gj_pkg.sv`, `mem.sv`, and `delay_line.sv` as the supporting primitives reference.

## Scope

These docs are intentionally narrow:

- the production GF(2) solver path
- the main solver entry points
- control and data movement through the array
- the supporting primitives needed to follow that path
