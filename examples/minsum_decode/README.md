# `minsum_decode`

Standalone row-layered normalized min-sum decode example.

This folder is the production BP example for the repo. It builds one Stim-backed
case, runs one SystemVerilog decoder, and checks the final result in Python.

## Files

- `stim_example.py`: deterministic Stim source used by the default case.
- `case.py`: exports `H`, `syndrome`, `prior_llr`, and `max_iter`.
- `common.py`: quantization, graph-build, and software min-sum reference helpers.
- `build.py`: Python setup only. Writes one immutable case under `cases/<case_id>/`.
- `run.py`: SystemVerilog compile and simulation only.
- `read.py`: Python verification only.

## Run

```sh
python examples/minsum_decode/build.py
python examples/minsum_decode/run.py
python examples/minsum_decode/read.py
```

## Outputs

- `cases/latest/`: symlink to the active case.
- `problem/`: BP preload files such as `row_ptr.mem`, `edge_var.mem`, and `prior_llr.hex`.
- `out/`: hardware outputs and cycle counts.

`read.py` reports only the final checks:

- hardware/software agreement
- `H @ e == sigma`
- residual weight
- `logicals @ e == actual_observables` when logicals are present
