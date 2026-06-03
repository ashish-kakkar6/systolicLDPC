# `bp_osd_decode`

Composed hardware decode flow: min-sum BP front-end followed by OSD.

## Purpose

This is the composed `BP -> OSD` flow. It keeps the public contract
`Python setup -> SV simulation -> Python readback`, while the BP-to-OSD
handoff stays entirely in hardware.

## Files

- `stim_example.py`: deterministic Stim source for the default case.
- `case.py`: exports `H`, `sigma`, `logicals`, `actual_observables`, `prior_llr`, and `max_iter`.
- `common.py`: shared BP/OSD glue helpers and software references.
- `build.py`: Python setup only. Builds one immutable case.
- `run.py`: SystemVerilog compile and simulation only.
- `read.py`: Python verification only.
- `tb_bp_osd_decode.sv`: top-level testbench for the composed flow.

## Run

```sh
./.venv/bin/python examples/bp_osd_decode/build.py
./.venv/bin/python examples/bp_osd_decode/run.py
./.venv/bin/python examples/bp_osd_decode/read.py
```

## Outputs

- `cases/latest/`: symlink to the active case.
- `problem/`: BP graph files, OSD preload files, and generated score inputs.
- `out/`: BP outputs, OSD outputs, and cycle counts.

## Final checks

`read.py` reports only:

- BP posterior and hard-decision agreement
- BP residual weight
- OSD selected-column and reduced-system agreement
- `H @ F == sigma`
- `logicals @ F == actual_observables`
