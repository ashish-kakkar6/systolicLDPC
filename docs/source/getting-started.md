# Installing

## Dependencies

- Python 3.12+ for the example wrappers, tests, and docs
- `iverilog` for HDL simulations of the examples and test flows
- `verilator` and `c++` for HDL simulations of larger examples (only when you want `--sim verilator`)
- `stim` for simulating decoding of circuit level noise
`make` installs the Python dependencies only. It does not install the HDL
simulators.

For `iverilog`:

- Ubuntu: `sudo apt install verilog`
- macOS: `brew install icarus-verilog`
- source/install: [steveicarus/iverilog](https://github.com/steveicarus/iverilog)

For optional Verilator setup:

- [Verilator install guide](https://verilator.org/guide/latest/install.html)

## Quickstart

From the repository root:

```sh
make
```

This creates `.venv`, installs the default example dependencies
(`numpy`, `scipy`, and `stim`), and checks that `iverilog` is present.

The default end-to-end decoder example path is:

```sh
./.venv/bin/python examples/minsum_decode/build.py
./.venv/bin/python examples/minsum_decode/run.py
./.venv/bin/python examples/minsum_decode/read.py
```

## Optional setup paths

For larger examples with Verilator:

```sh
make verilator-ready
```

For cocotb tests:

```sh
make test-ready
```

For documentation only:

```sh
make docs-ready
```

Run the public regression suite with:

```sh
make test
```

Build the docs with:

```sh
make docs
```

## Usage entry points

The smallest supported end-to-end examples of the systolic solver are:
- [`gauss_jordan_sol_existence`](usage/gauss-jordan-sol-existence.md)
- [`gauss_jordan_solve`](usage/gauss-jordan-solve.md)

The supported Stim-backed decoder examples are:

- [`minsum_decode`](usage/minsum-decode.md)
- [`osd_decode`](usage/osd-decode.md)
- [`bp_osd_decode`](usage/bp-osd-decode.md)
