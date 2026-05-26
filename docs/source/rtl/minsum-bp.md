# Min-sum BP

This page covers the scalable decoder-side RTL under `rtl/minsum_bp/`.

## Role

`rtl/minsum_bp/` is the current message-passing decoder path in this
repository. It is separate from the systolic Gauss-Jordan solver and is meant
to act as a scalable front-end that can either stand alone or later feed
decoder-side post-processing.

## Current files

- `minsum_pkg.sv`
  Shared arithmetic helpers, including normalization support.
- `minsum_row_engine.sv`
  The row-local normalized min-sum update kernel.
- `minsum_decode_top.sv`
  The single-engine layered controller and state store.

## Current architecture

The shipped reference implementation uses:

- row-layered normalized min-sum
- compressed row storage via `row_ptr` and `edge_var`
- persistent `app_llr[N]` and `c2v[E]` state
- one active row engine at a time

The current example flow for this RTL is:

- [Layered min-sum decode](../usage/decoder/minsum-decode.md)

## Why this path is separate

The min-sum decoder has a different scaling model from the solver RTL:

- it is graph driven, not matrix-stream driven
- it is intended to scale through row-engine replication
- it keeps the decoder front-end in a compact fixed-point row-update form

That separation keeps the decoder front-end modular and easier to evolve.
