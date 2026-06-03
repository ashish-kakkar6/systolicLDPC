include make/common.mk

.DEFAULT_GOAL := ready

.PHONY: help ready core-ready verilator-ready test-ready docs-ready \
	venv deps deps-core deps-stim deps-test deps-docs \
	check-python-version check-iverilog check-verilator check-cxx \
	test test-sort docs clean

help:
	@printf "Targets:\n"
	@printf "  make               - install default decoder example Python deps (numpy, scipy, stim) and check iverilog\n"
	@printf "                       note: make does not install iverilog or verilator for you\n"
	@printf "                       ubuntu: sudo apt install verilog\n"
	@printf "                       macOS: brew install icarus-verilog\n"
	@printf "                       iverilog source/install: https://github.com/steveicarus/iverilog\n"
	@printf "  make core-ready    - install only core example Python deps (numpy, scipy) and check iverilog\n"
	@printf "  make verilator-ready - check the optional Verilator toolchain for larger runs\n"
	@printf "                       optional Verilator install docs: https://verilator.org/guide/latest/install.html\n"
	@printf "  make test-ready    - install cocotb and check the test simulator path\n"
	@printf "  make docs-ready    - install only documentation dependencies\n"
	@printf "  make test          - run the current cocotb suites\n"
	@printf "  make test-sort     - run the sorter cocotb suite\n"
	@printf "  make docs          - build the Sphinx HTML documentation into docs/_build/html\n"
	@printf "  make clean         - remove generated simulation and docs artifacts\n"

ready: deps-stim check-iverilog
	@printf "Default min-sum decoder example environment is ready.\n"

core-ready: deps-core check-iverilog
	@printf "Core example environment is ready.\n"

verilator-ready: ready check-verilator check-cxx
	@printf "Verilator example environment is ready.\n"

test-ready: deps-test check-iverilog
	@printf "Test environment is ready.\n"

docs-ready: deps-docs
	@printf "Docs environment is ready.\n"

$(VENV_PYTHON):
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_PYTHON) -m pip install --upgrade pip

venv: $(VENV_PYTHON)

deps: deps-stim

deps-core: venv requirements-core.txt check-python-version
	$(VENV_PYTHON) -m pip install -r requirements-core.txt

deps-stim: venv requirements-stim.txt check-python-version
	$(VENV_PYTHON) -m pip install -r requirements.txt

deps-test: venv requirements-test.txt check-python-version
	$(VENV_PYTHON) -m pip install -r requirements-test.txt

deps-docs: venv requirements-docs.txt check-python-version
	$(VENV_PYTHON) -m pip install -r requirements-docs.txt

check-python-version: venv
	@$(VENV_PYTHON) -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else "Python 3.12+ is required")'

check-iverilog:
	@command -v iverilog >/dev/null 2>&1 || { \
		printf "Missing required tool: iverilog\n" >&2; \
		printf "Install it separately; make only installs Python dependencies.\n" >&2; \
		printf "  ubuntu: sudo apt install verilog\n" >&2; \
		printf "  macOS: brew install icarus-verilog\n" >&2; \
		printf "  source/install: https://github.com/steveicarus/iverilog\n" >&2; \
		exit 1; \
	}

check-verilator:
	@command -v verilator >/dev/null 2>&1 || { \
		printf "Missing required tool: verilator\n" >&2; \
		printf "Install it separately; make only installs Python dependencies.\n" >&2; \
		printf "  install docs: https://verilator.org/guide/latest/install.html\n" >&2; \
		exit 1; \
	}

check-cxx:
	@command -v c++ >/dev/null 2>&1 || { printf "Missing required tool: c++ compiler\n" >&2; exit 1; }

test: test-ready
	$(MAKE) -C test/systolic_gauss_jordan TEST=all
	$(MAKE) -C test/sort TEST=all

test-sort: test-ready
	$(MAKE) -C test/sort TEST=all

docs: docs-ready
	$(MAKE) -C docs html

clean:
	$(MAKE) -C test/systolic_gauss_jordan clean
	$(MAKE) -C test/sort clean
	$(MAKE) -C docs clean
	rm -rf examples/*/cases
	rm -rf examples/*/batches
	rm -rf examples/*/__pycache__
