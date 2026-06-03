# Contributing

Thanks for your interest in `systolicLDPC`.

## Setup

From the repository root:

```sh
make
```

Optional setup targets:

```sh
make test-ready
make docs-ready
make verilator-ready
```

## Common workflow

Public examples follow the same contract:

1. `build.py`
   Python setup only. Creates one immutable case under `cases/<case_id>/`.
2. `run.py`
   SystemVerilog compile and simulation only.
3. `read.py`
   Python verification and reporting only.

When adding a new example, keep that split intact.

## Checks

Before opening a change, run the checks relevant to the files you touched:

```sh
make test
make docs
```

For example-specific changes, also run the corresponding example flow:

```sh
./.venv/bin/python examples/<example_name>/build.py
./.venv/bin/python examples/<example_name>/run.py
./.venv/bin/python examples/<example_name>/read.py
```

## Repository layout

- `rtl/`: synthesizable hardware modules and small RTL-local READMEs
- `examples/`: public runnable flows
- `test/`: cocotb regression suites
- `docs/source/`: Sphinx source for the public documentation

## Generated artifacts

Do not commit generated outputs such as:

- `examples/*/cases/`
- `examples/*/batches/`
- `test/**/sim_build/`
- `docs/_build/`

Use `make clean` to return the tree to a source-only state.

## Style

- Keep example scripts concise and public-facing.
- Prefer reusable helpers in `examples/shared/` when logic is common across flows.
- Keep docs and runnable commands consistent with the local `.venv` workflow:
  `./.venv/bin/python ...`
