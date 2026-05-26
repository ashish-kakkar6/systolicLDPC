SPHINXBUILD ?= ../.venv/bin/python -m sphinx
SOURCEDIR   := source
BUILDDIR    := _build

.PHONY: help html clean

help:
	@printf "Targets:\n"
	@printf "  make html  - build the Sphinx HTML site into docs/_build/html\n"
	@printf "  make clean - remove generated Sphinx output\n"

html:
	$(SPHINXBUILD) -b html -W $(SOURCEDIR) $(BUILDDIR)/html

clean:
	rm -rf $(BUILDDIR)
	rm -f figures/*.fdb_latexmk figures/*.fls figures/*.log
