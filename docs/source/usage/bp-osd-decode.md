# BP-OSD decode

Example directory:
- `examples/bp_osd_decode`

This is the composed hardware decode flow: min-sum BP front-end followed by
OSD. The BP-to-OSD handoff stays in hardware, so the repository workflow remains
`Python build -> SV run -> Python read`.

## Commands

```sh
./.venv/bin/python examples/bp_osd_decode/build.py
./.venv/bin/python examples/bp_osd_decode/run.py
./.venv/bin/python examples/bp_osd_decode/read.py
```

## Inputs

The default case source is Stim-backed. `build.py` generates:

- `H`
- `sigma`
- `logicals`
- `actual_observables`
- `prior_llr`
- `max_iter`

The BP stage runs for the configured fixed iteration count, and the resulting
posterior-derived reliabilities are forwarded to OSD entirely in SV.

## Outputs

Generated under `cases/<case_id>/` with `cases/latest` pointing at the active case:

- BP graph and preload files under `problem/`
- BP outputs under `out/`
- OSD outputs under `out/`
- cycle counts for the composed run

## Final checks

`read.py` reports both stages:

- BP posterior and hard-decision agreement
- BP residual weight
- OSD selected-column and reduced-system agreement
- `H @ F == sigma`
- `logicals @ F == actual_observables`
