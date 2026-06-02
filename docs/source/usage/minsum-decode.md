# Layered min-sum decode

Example directory:
- `examples/minsum_decode`

This is the standalone decoder-facing reference flow. It uses the scalable RTL
under `rtl/minsum_bp/` and a Stim-backed case builder.

## Commands

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

It quantizes the priors, runs the fixed-point Python min-sum reference, and
keeps the sampled syndrome and logical-observable data as-is.

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

## Final checks

`read.py` reports:

- the final hard decision vector `e`
- `H @ e == sigma`
- `residual = (H @ e) - sigma` over $\mathrm{GF}(2)$
- `|residual|`, the Hamming weight of the residual
- `logicals @ e == actual_observables`

