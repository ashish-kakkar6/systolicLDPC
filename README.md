# systolicLDPC

Open-source research software for FPGA-oriented experiments in qLDPC decoding,
centered on a systolic GF(2) Gauss-Jordan solver, a row-layered normalized
min-sum decoder, and lightweight cocotb-based verification.

## Layout

```text
systolicLDPC/
├── Makefile
├── README.md
├── requirements.txt
├── docs/
├── examples/
│   ├── gauss_jordan_solve/
│   ├── gauss_jordan_sol_existence/
│   ├── bp_osd_decode/
│   ├── minsum_decode/
│   ├── osd_decode/
│   └── shared/
├── make/
├── rtl/
│   ├── minsum_bp/
│   ├── osd_control/
│   └── systolic_gauss_jordan/
└── test/
    └── systolic_gauss_jordan/
```

## Available RTL

- `trapeziod_mesh.sv` is the structural lifted mesh.
- `pe_diag.sv` and `pe_col.sv` implement the mesh cells.
- `input.sv` owns RAM-backed row loading and the staggered top-edge feed.
- `controller.sv` owns the run window and reduce pulse.
- `mem.sv`, `delay_line.sv`, and `gj_pkg.sv` provide the shared primitives.
- `rtl/minsum_bp/` contains the current decoder-side front-end built around
  row-layered normalized min-sum.

## Example Flows

- `gauss_jordan_solve/`: start from NumPy `A` and `B`, and solve `A X = B`
- `gauss_jordan_sol_existence/`: start from NumPy `A` and `B` and check whether `A x = B` has a solution
- `osd_decode/`: start from a Stim-backed decoding problem and run OSD (Ordered Statistics Decoding) using stim priors
- `minsum_decode/`: start from a Stim-backed decoding problem and run the
  scalable min-sum decoder front-end
- `bp_osd_decode/`: run min-sum BP first, then pass BP-derived reliabilities
  directly into the OSD hardware flow

## Installation

The repository uses a local `.venv` plus workflow-specific `make` targets.

- `make`
  Installs the default example path:
  `numpy`, `scipy`, `stim`, and checks `iverilog`.
- `make verilator-ready`
  Checks the optional Verilator toolchain for larger runs:
  `verilator` and a `c++` compiler.
- `make test-ready`
  Installs `cocotb` and checks the test simulator path.
- `make docs-ready`
  Installs only the Sphinx documentation dependencies.

System tools are still installed with your OS package manager.
The required system tools are:

- `iverilog` for the default example and test flows
- `verilator` and `c++` for `--sim verilator`

`make` does not install `iverilog` or `verilator` for you. For `iverilog`:

- Ubuntu: `sudo apt install verilog`
- macOS: `brew install icarus-verilog`
- source/install: [steveicarus/iverilog](https://github.com/steveicarus/iverilog)

For optional Verilator setup, see:

- [Verilator install guide](https://verilator.org/guide/latest/install.html)

## Quick Start

From the repo root:

```sh
make
./.venv/bin/python examples/minsum_decode/build.py
./.venv/bin/python examples/minsum_decode/run.py
./.venv/bin/python examples/minsum_decode/read.py
```

Optional setup paths:

```sh
make verilator-ready
make test-ready
make docs-ready
```

Run tests or docs when needed:

```sh
make test
make docs
```

Focused regression targets:

```sh
make -C test/systolic_gauss_jordan TEST=pe_col
make -C test/systolic_gauss_jordan TEST=pe_diag
make -C test/systolic_gauss_jordan TEST=trapeziod_mesh
make -C test/systolic_gauss_jordan TEST=trapeziod_full_trace_reduce
```

## Documentation

The Sphinx site lives under `docs/source/` and builds into:

```text
docs/_build/html/
```

Additional metadata:

- contributor guide: [`CONTRIBUTING.md`](CONTRIBUTING.md)
