# OSD decode

Example directory:
- `examples/osd_decode`

This flow keeps the full decoding problem in hardware-side memories and lets
the RTL controller handle ranking, independent-column selection, row
compaction, reduced solve, and reconstruction.

## Commands

```sh
./.venv/bin/python examples/osd_decode/build.py
./.venv/bin/python examples/osd_decode/run.py
./.venv/bin/python examples/osd_decode/read.py
```

For many-shot statistics:

```sh
./.venv/bin/python examples/osd_decode/build_batch.py --shots 1000
./.venv/bin/python examples/osd_decode/run_batch.py --sim verilator --jobs 8
./.venv/bin/python examples/osd_decode/read_batch.py
```

## Inputs

The default input source is Stim-backed and lives in:

- `examples/osd_decode/stim_example.py`
- `examples/osd_decode/dem_mat.py`

The built case carries both syndrome and logical-observable data through the
flow.

## Outputs

Generated under `cases/<case_id>/` with `cases/latest` pointing at the active case:

- `H.npy`
- `sigma.npy`
- `logicals.npy`
- `actual_observables.npy`
- `initial_estimate.npy`
- `selected_indices_sw.npy`
- `selected_indices_hw.txt`
- `H_reduced_sw.npy`
- `sigma_reduced_sw.npy`
- `x_software.npy`
- `F_software.npy`
- `x_hardware.npy`
- `F_hardware.npy`

## Final checks

`read.py` reports the hardware/software agreement for the reduced solve and the
final decoded vector, including:

- `H @ F == sigma`
- `logicals @ F == actual_observables`
