# Systolic Solver

```{toctree}
:maxdepth: 1
:hidden:

Gauss-Jordan solve <../../examples/gauss-jordan-solve>
Gauss-Jordan solution existence <../../examples/gauss-jordan-sol-existence>
```

This section covers the direct solver-facing flow: start from explicit `A` and
`B` matrices, run the production systolic Gauss-Jordan path, and compare the
hardware result with the software reference.

- [Gauss-Jordan solve](../../examples/gauss-jordan-solve.md)
  Case-based wrapper around the production solver, with manifest checks and
  hardware/software verification.
- [Gauss-Jordan solution existence](../../examples/gauss-jordan-sol-existence.md)
  Case-based wrapper around the same solver path, but using the bottom trace to
  decide whether `A x = B` is consistent over `GF(2)`.
