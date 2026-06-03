# Usage

```{toctree}
:maxdepth: 1
:hidden:

Gauss-Jordan solve <gauss-jordan-solve>
Gauss-Jordan solution existence <gauss-jordan-sol-existence>
Layered min-sum decode <minsum-decode>
OSD decode <osd-decode>
BP-OSD decode <bp-osd-decode>
```

This section documents the runnable example flows in `examples/`. Each page
maps directly to one example directory and follows the same common contract:

- `build.py`
  Python setup only. Generates one immutable case directory under
  `cases/<case_id>/` and refreshes `cases/latest`.
- `run.py`
  SystemVerilog compile and simulation only. Uses the built case as input and
  writes hardware outputs under `out/`.
- `read.py`
  Python readback and verification only. Loads the built case and hardware
  outputs, then reports the final checks.

This split keeps the workflow consistent across solver and decoder examples:

1. build the case once,
2. run the hardware simulation once,
3. read back and check the result.

## Available flows

- [Gauss-Jordan solve](gauss-jordan-solve.md)
  Direct `A X = B` solve over $\mathrm{GF}(2)$ against the reference systolic solver.
- [Gauss-Jordan solution existence](gauss-jordan-sol-existence.md)
  Uses the same solver path to determine whether `A x = B` is consistent.
- [Layered min-sum decode](minsum-decode.md)
  Standalone row-layered normalized min-sum decode on Stim-backed input data.
- [OSD decode](osd-decode.md)
  Hardware-side ranking, basis selection, reduced solve, and reconstruction from a Stim-backed syndrome.
- [BP-OSD decode](bp-osd-decode.md)
  Sequential composed flow: min-sum BP front-end followed by OSD in one SV run.
