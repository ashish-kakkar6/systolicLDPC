# Usage

```{toctree}
:maxdepth: 2
:hidden:

Systolic Solve <systolic-solver/index>
Decoder <decoder/index>
```

This section groups the public execution flows around the production RTL path.

- [Systolic Solve](systolic-solver/index.md)
  Direct `A X = B` solve flows against the production Gauss-Jordan kernel.
- [Decoder](decoder/index.md)
  Decoder-oriented flows built around a scalable row-layered normalized min-sum
  front-end, with optional ranking and reduced-system construction around the
  same solver.
