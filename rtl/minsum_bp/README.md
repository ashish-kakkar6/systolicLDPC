# `rtl/minsum_bp`

This directory contains the repository's active belief-propagation decoder
implementation: a **row-layered, normalized min-sum** engine written in
SystemVerilog for FPGA-oriented study and composition.

The intent of this path is different from an analytically exact sum-product
decoder. It is designed to be:

- sparse and memory-aware rather than dense,
- modular enough to compose with downstream decoders such as OSD,
- simple enough to inspect, simulate, and extend without carrying a large
  nonlinear-function stack.

In the present implementation, the decoder stores only the information needed
for layered min-sum:

- `prior_llr` for each variable,
- `syndrome` bits for each check,
- a compressed row view of the Tanner graph (`row_ptr`, `edge_var`),
- current variable beliefs (`app_llr`),
- current check-to-variable messages (`c2v`).

The variable-to-check message is not stored globally. It is formed on the fly
inside the row update as:

`q_ij = app_j - r_ij`.

This keeps the state compact and makes the architecture a good foundation for
more scalable partially parallel designs.

## File Structure

### [`minsum_pkg.sv`](minsum_pkg.sv)

Shared package utilities for the min-sum path.

At present this package contains the normalization helper used by the check-row
engine:

- `alpha_scale_mag`

The current normalization is a shift-based approximation,
`alpha = 1 - 2^{-ALPHA_SHIFT}`, chosen to avoid multipliers while preserving a
clear hardware model.

### [`minsum_row_engine.sv`](minsum_row_engine.sv)

Combinational row update kernel for one active check row.

Given a packed row of incoming `q_ij` values and the row syndrome bit, this
module computes the normalized min-sum outgoing messages for that row. Its work
is the local check-node reduction:

- sign parity over the row,
- first and second minimum magnitudes,
- per-edge extrinsic sign and magnitude,
- normalized output message generation.

Conceptually, this is the mathematical heart of the decoder. It does not own
iteration control, memory, or graph traversal.

### [`minsum_decode_top.sv`](minsum_decode_top.sv)

Sequential top-level decoder for a compressed-row min-sum graph.

This module owns:

- preload interfaces for `prior_llr`, `syndrome`, `row_ptr`, and `edge_var`,
- runtime state for `app_llr` and `c2v`,
- the layered iteration schedule,
- gather / emit passes over each check row,
- final posterior and hard-decision output formatting.

The current implementation is intentionally a compact baseline:

- one active row engine,
- one edge slot processed per cycle in gather and emit,
- fixed iteration count,
- final output as posterior LLRs and hard decisions.

This keeps the control/dataflow explicit and makes the decoder suitable as a
reference point for future `K`-wide or multi-engine variants.

Two example flows currently exercise this RTL:

- [`examples/minsum_decode`](../../examples/minsum_decode)
  runs the min-sum decoder directly on a Stim-backed case.
- [`examples/bp_osd_decode`](../../examples/bp_osd_decode)
  runs min-sum BP first, then forwards the posterior-derived reliability signal
  to OSD inside a single SystemVerilog simulation.

Those example directories are the recommended entry points for reproducing the
decoder behavior end to end.
