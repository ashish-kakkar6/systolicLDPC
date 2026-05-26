# Layered Min-sum Decode

The `minsum_decode` example is the current standalone decoder-facing reference
flow in this repository. It uses the scalable RTL under `rtl/minsum_bp/` and a
Stim-backed case builder that takes one deterministic seeded sample, like the
`osd_decode` flow.

## Commands

From the repository root:

```sh
./.venv/bin/python examples/minsum_decode/build.py
./.venv/bin/python examples/minsum_decode/run.py
./.venv/bin/python examples/minsum_decode/read.py
```

## Inputs

The build step starts from:

- a Stim-generated detector error model
- the derived binary check matrix `H`
- binary logical-observable matrix `logicals`
- per-edge priors

It then quantizes the priors, runs the fixed-point Python min-sum reference for
comparison, and keeps the sampled syndrome and observable data as-is.

## Outputs

The built case stores:

- `H.npy`
- `syndrome.npy`
- `actual_observables.npy`
- `logicals.npy`
- `prior_llr.npy`
- row-major graph data for `row_ptr` and `edge_var`
- software reference posterior LLRs and hard decisions

The hardware run writes:

- `out/hard_decision_hw.bin`
- `out/posterior_llr_hw.hex`
- `out/counts_hw.txt`

The read step compares hardware and software, then reports:

- the final hard decision vector `e`
- final fixed-point and floating-point posterior values
- `H @ e == sigma`
- `residual = (H @ e) - sigma` over GF(2)
- `|residual|`, the Hamming weight of the residual
- `logicals @ e == actual_observables`

## Why this flow exists

This example is the compact scalable decoder path:

- row-layered schedule
- normalized min-sum with `alpha = 0.75`
- compressed row storage
- fixed-point row-local updates with compact persistent state

It is meant to be the clean base path for future `P > 1` row-engine
parallelization.
