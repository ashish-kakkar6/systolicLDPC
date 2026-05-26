# systolic_gauss_jordan RTL

Production GF(2) Gauss-Jordan solver used by the example flows and the OSD
control wrapper.

## Structure

- [controller.sv](controller.sv)
  Public top for one solve run. Owns the start/done window, the optional
  reduce pulse, and the RAM write interface used by the examples and wrappers.
- [controller_sol_existence.sv](controller_sol_existence.sv)
  Thin wrapper around `controller.sv` used by the existence example. It reuses
  the same solver path and adds per-column existence outputs.
- [input.sv](input.sv)
  Solver feeder. Owns the A/B memories, reads rows back in order, packs each
  row as `{B, A}`, and applies the staggered top-edge schedule expected by the
  mesh. The module name is escaped as `\input`.
- [solution_existence_monitor.sv](solution_existence_monitor.sv)
  Hardware monitor for `gauss_jordan_sol_existence`. Watches `data_bottom_o`
  for one configured forward-pass window and records whether each RHS column
  ever emitted a bottom-node `1`.
- [trapeziod_mesh.sv](trapeziod_mesh.sv)
  Pure structural systolic mesh. Wires the diagonal and off-diagonal cells,
  propagates the delayed reduce path, and exposes the bottom trace plus the
  internal `A`/`B` state snapshots.
- [pe_diag.sv](pe_diag.sv)
  Diagonal cell. Detects or forwards the pivot condition and emits the opcode
  stream that drives the rest of the row.
- [pe_col.sv](pe_col.sv)
  Off-diagonal cell. Updates one stored bit under the diagonal opcode stream
  and forwards the transformed data downward.
- [mem.sv](mem.sv)
  Simple synchronous single-port memory used for the row stores.
- [delay_line.sv](delay_line.sv)
  Reusable synchronous delay primitive used for the top-edge stagger schedule.
- [gj_pkg.sv](gj_pkg.sv)
  Shared opcode enum used across the mesh and processing elements.

## Flow

1. `controller.sv` latches the run parameters and launches one solve window.
2. `input.sv` reads A and B rows from `mem.sv`, delays each top-edge lane with
   `delay_line.sv`, and feeds the staggered row into `trapeziod_mesh.sv`.
3. `trapeziod_mesh.sv` applies Gauss-Jordan updates through `pe_diag.sv` and
   `pe_col.sv` while the reduce signal moves between diagonal cells.
4. The observable outputs are `data_bottom_o` for the streamed bottom trace and
   `b_regs_flat_o` for the mesh B-state snapshot.

For the existence example:

1. `controller_sol_existence.sv` instantiates `controller.sv`.
2. `solution_existence_monitor.sv` watches the streamed `data_bottom_o`.
3. `has_solution_o[col]` is `1` iff column `col` never emits a bottom-node `1`
   during the configured forward-pass window.
