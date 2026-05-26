# docs

Docs are built using Sphinx.

## Build locally

From the repo root:

```sh
make docs-ready
make docs
```

Or directly from this folder:

```sh
../.venv/bin/python -m pip install -r requirements.txt
make html
```

Built HTML is written to:

```text
docs/_build/html/
```
