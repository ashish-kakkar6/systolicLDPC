# OSD decode

Directory:
- `examples/osd_decode`

This flow keeps the full decoding problem in hardware-side memories and lets
the RTL controller handle ranking, independent-column selection, row
compaction, reduced solve, and result materialization.

The default Stim-backed input source lives directly in this example folder:

- `examples/osd_decode/stim_example.py`
- `examples/osd_decode/dem_mat.py`

The built case also carries the Stim logical-observable data through the flow:

- `logicals.npy` stores `dem_matrices.observables_matrix`
- `actual_observables.npy` stores the sampled logical-observable outcome

The ranking path uses quantized `u4` scores on narrow memory-backed interfaces:

- the top-`P` ranker reads one score at a time from the stored estimate RAM
- only the exact first ranked candidates are kept in hardware
- ranked indices are read back one at a time during basis selection
- large packed score and sorted-index buses are avoided

Important:
- `TOP_P_MAX = M_MAX` may not be enough, because some ranked columns can fail
  the independence test before `M_MAX` columns are accepted.

Use this flow when you want the decoder-side control path, not just the solver
kernel in isolation.

## Commands

```sh
python3 examples/osd_decode/build.py
python3 examples/osd_decode/run.py
python3 examples/osd_decode/read.py
```

For many-shot statistics, keep the RTL single-shot and parallelize the wrapper:

```sh
python3 examples/osd_decode/build_batch.py --shots 1000
python3 examples/osd_decode/run_batch.py --sim verilator --jobs 8
python3 examples/osd_decode/read_batch.py
```

The batch flow samples many Stim shots once, compiles the hardware once, and
then runs one hardware process per shot with a different `sigma.mem` while
reusing the same compiled binary and static preload files.

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

Batch runs write `batches/<batch_id>/` with `batches/latest` pointing at the
active batch. The batch reader records, for each shot:

- `actual_observables`
- `sigma`
- `F_hardware.npy`
- `H @ F == sigma`
- `logicals @ F == actual_observables`
- `elapsed_cycles`
