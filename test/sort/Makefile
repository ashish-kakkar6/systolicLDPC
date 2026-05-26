ROOT := $(abspath $(CURDIR)/../..)
include $(ROOT)/make/common.mk

SIM ?= icarus
TOPLEVEL_LANG ?= verilog
TEST ?= all

RTL_DIR := $(ROOT)/rtl/sort

export PYTHONPATH := $(CURDIR):$(PYTHONPATH)

.DEFAULT_GOAL := all
.PHONY: all rank_indexed_u4 clean

ifeq ($(TEST),all)

all: rank_indexed_u4

rank_indexed_u4:
	$(MAKE) --no-print-directory TEST=rank_indexed_u4 sim

clean:
	rm -rf $(CURDIR)/sim_build $(CURDIR)/__pycache__ $(CURDIR)/.pytest_cache
	rm -f $(CURDIR)/results.xml $(CURDIR)/results_*.xml

else

.DEFAULT_GOAL := sim

COMPILE_ARGS += -g2012
COCOTB_RESULTS_FILE := $(CURDIR)/results_$(TEST).xml

ifeq ($(TEST),rank_indexed_u4)
SIM_BUILD := $(CURDIR)/sim_build/rank_indexed_u4
VERILOG_SOURCES := \
	$(RTL_DIR)/rank_indexed_u4.sv \
	$(CURDIR)/rank_indexed_u4_tb.sv
COCOTB_TOPLEVEL := rank_indexed_u4_tb
COCOTB_TEST_MODULES := test_rank_indexed_u4
endif

ifeq ($(COCOTB_TOPLEVEL),)
$(error Unsupported TEST='$(TEST)'; use TEST=rank_indexed_u4 or TEST=all)
endif

PYTHON_BIN := $(VENV_PYTHON)
COCOTB_MAKEFILES_DIR_LOCAL := $(shell $(PYTHON_BIN) -m cocotb_tools.config --makefiles)
SIM_LOWERCASE := $(shell echo $(SIM) | tr A-Z a-z)
HAVE_SIMULATOR := $(shell if [ -f $(COCOTB_MAKEFILES_DIR_LOCAL)/simulators/Makefile.$(SIM_LOWERCASE) ]; then echo 1; else echo 0; fi;)
AVAILABLE_SIMULATORS := $(patsubst .%,%,$(suffix $(wildcard $(COCOTB_MAKEFILES_DIR_LOCAL)/simulators/Makefile.*)))

ifeq ($(HAVE_SIMULATOR),0)
$(error Couldn't find makefile for simulator: "$(SIM_LOWERCASE)"! Available simulators: $(AVAILABLE_SIMULATORS))
endif

include $(COCOTB_MAKEFILES_DIR_LOCAL)/Makefile.inc
include $(COCOTB_MAKEFILES_DIR_LOCAL)/simulators/Makefile.$(SIM_LOWERCASE)

endif
