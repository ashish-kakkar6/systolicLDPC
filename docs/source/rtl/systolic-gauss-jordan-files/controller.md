# Top (`controller.sv`)

Source:
- `rtl/systolic_gauss_jordan/controller.sv`

`controller` is the top for one Gauss-Jordan run. It owns run-level
timing only and delegates row feeding to `\input`.

## Function

On `start_i`, the module latches the run configuration, starts the feeder, and
begins a local cycle counter. During the run it optionally emits a one-cycle
reduce pulse. When the configured run window completes, it pulses `done_o` and
returns idle.

The data path is:

`controller -> \input -> trapeziod_mesh`

## Interface contract

- `start_i` is single-shot while idle
- `rows_i` selects how many A/B rows the feeder issues
- `reduce_start_i` is the step-local cycle at which reduce is asserted
- `run_cycles_i == 0` falls back to `3N + rows_i + L - 2`
- `busy_o` stays high for the active run
- `done_o` is a one-cycle completion pulse
- `error_o` flags invalid control use such as restart-while-busy
