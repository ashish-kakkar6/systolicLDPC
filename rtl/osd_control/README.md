# osd_control RTL

Minimal modular hardware pipeline for ranked decoding experiments.

## Structure

- [problem_store.sv](problem_store.sv)
  Stores the full problem in local memories:
  `H`, `sigma`, quantized `u4` scores, and quantized `u4` cutoff, with narrow
  combinational score-read ports for the ranker and controller.
- [ranker_u4_wrapper.sv](ranker_u4_wrapper.sv)
  Stable wrapper around the low-precision top-`P` ranker on a narrow
  address/data interface.
- [solver_gj_wrapper.sv](solver_gj_wrapper.sv)
  Stable wrapper around the current systolic Gauss-Jordan solver. It solves the
  reduced system directly with `B = sigma_reduced` and `L = 1`, and exposes the
  bottom-trace bitstream.
- [control.sv](control.sv)
  Orchestrates:
  ranking, independent-column selection, row gather, zero-row removal, and solve launch.
- [osd_control_top.sv](osd_control_top.sv)
  Integration top used by the simulation example.

## Current contract

The controller owns the middle pipeline and depends only on two wrappers:

- sorter wrapper
- solver wrapper

The sorter side is now intentionally memory-backed:

- the top-`P` ranker reads one `u4` score at a time from the store
- the controller reads back only the first ranked candidates one at a time
- wide packed sorter score and sorted-index buses are avoided

This keeps the implementation-specific details of the current sorter and solver out of the controller.
`x_hardware` and `F_hardware` are materialized in hardware by the controller.

Important:
- `TOP_P_MAX = M_MAX` may not be enough, because some ranked columns can fail
  the independence test before `M_MAX` columns are accepted.

## Current v1 restriction

The gathered reduced system is expected to be square after zero-row removal.
If `selected_count != compacted_rows`, the controller raises `error_o`.
