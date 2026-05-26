# `bp_osd_decode`

Composed hardware decode flow: min-sum BP front-end followed by OSD.

This example is the clean `Python setup -> SV simulation -> Python readback`
path for the sequential `BP -> OSD` controller. The BP-to-OSD handoff stays in
hardware; Python does not reinterpret BP outputs between phases.

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
python examples/bp_osd_decode/build.py
python examples/bp_osd_decode/run.py
python examples/bp_osd_decode/read.py
```

## Outputs

- `cases/latest/`: symlink to the active case.
- `problem/`: BP graph files, OSD preload files, and generated score inputs.
- `out/`: BP outputs, OSD outputs, and cycle counts.

`read.py` reports the final BP and OSD checks:

- BP posterior and hard-decision agreement
- BP residual weight
- OSD selected-column and reduced-system agreement
- `H @ F == sigma`
- `logicals @ F == actual_observables`
