ROOT := $(abspath $(CURDIR)/../..)
include $(ROOT)/make/common.mk

SIM ?= icarus
TOPLEVEL_LANG ?= verilog
WAVES ?= 0
TEST ?= all

RTL_DIR := $(ROOT)/rtl/systolic_gauss_jordan
SAMPLE_MATRIX_JSON := $(CURDIR)/vectors/trapeziod_dynamics_sample.json
SAMPLE_M := 4
SAMPLE_N := 5
SAMPLE_L := 4

export PYTHONPATH := $(CURDIR):$(PYTHONPATH)

.DEFAULT_GOAL := all
.PHONY: all pe_diag pe_col trapeziod_mesh trapeziod_full_trace_reduce trapeziod_debug_flow clean

ifeq ($(TEST),all)

all: pe_diag pe_col trapeziod_mesh trapeziod_full_trace_reduce

pe_diag:
	$(MAKE) --no-print-directory TEST=pe_diag sim

pe_col:
	$(MAKE) --no-print-directory TEST=pe_col sim

trapeziod_mesh:
	$(MAKE) --no-print-directory TEST=trapeziod_mesh sim

trapeziod_full_trace_reduce:
	$(MAKE) --no-print-directory TEST=trapeziod_full_trace_reduce sim

trapeziod_debug_flow:
	$(MAKE) --no-print-directory TEST=trapeziod_debug_flow sim

clean:
	rm -rf $(CURDIR)/sim_build $(CURDIR)/__pycache__ $(CURDIR)/.pytest_cache
	rm -f $(CURDIR)/results.xml $(CURDIR)/results_*.xml

else

.DEFAULT_GOAL := sim

COMPILE_ARGS += -g2012
COCOTB_RESULTS_FILE := $(CURDIR)/results_$(TEST).xml

COMMON_SOURCES := \
	$(RTL_DIR)/gj_pkg.sv \
	$(RTL_DIR)/pe_diag.sv \
	$(RTL_DIR)/pe_col.sv

TRAPEZOID_MESH_COMPILE_ARGS := \
	-Ptrapeziod_mesh.N=$(SAMPLE_N) \
	-Ptrapeziod_mesh.M=$(SAMPLE_M) \
	-Ptrapeziod_mesh.L=$(SAMPLE_L)

DEBUG_REDUCE_HOP_DELAY ?= 2
DEBUG_FORWARD_RUN_CYCLES ?=
DEBUG_REDUCE_RUN_CYCLES ?=
DEBUG_REDUCE_START ?= $(SAMPLE_M)
DEBUG_MATRIX_JSON ?= $(SAMPLE_MATRIX_JSON)
DEBUG_EXPECTED_REDUCED_JSON ?= $(CURDIR)/vectors/trapeziod_dynamics_expected_reduce.json
DEBUG_STRICT ?= 0

ifeq ($(TEST),pe_diag)
SIM_BUILD := $(CURDIR)/sim_build/pe_diag
VERILOG_SOURCES := \
	$(RTL_DIR)/gj_pkg.sv \
	$(RTL_DIR)/pe_diag.sv
COCOTB_TOPLEVEL := pe_diag
COCOTB_TEST_MODULES := test_pe_diag
endif

ifeq ($(TEST),pe_col)
SIM_BUILD := $(CURDIR)/sim_build/pe_col
VERILOG_SOURCES := \
	$(RTL_DIR)/gj_pkg.sv \
	$(RTL_DIR)/pe_col.sv
COCOTB_TOPLEVEL := pe_col
COCOTB_TEST_MODULES := test_pe_col
endif

ifeq ($(TEST),trapeziod_mesh)
SIM_BUILD := $(CURDIR)/sim_build/trapeziod_mesh_M$(SAMPLE_M)_N$(SAMPLE_N)_L$(SAMPLE_L)
VERILOG_SOURCES := \
	$(COMMON_SOURCES) \
	$(RTL_DIR)/trapeziod_mesh.sv
COCOTB_TOPLEVEL := trapeziod_mesh
COCOTB_TEST_MODULES := test_trapeziod_mesh
COMPILE_ARGS += $(TRAPEZOID_MESH_COMPILE_ARGS)
endif

ifeq ($(TEST),trapeziod_full_trace_reduce)
SIM_BUILD := $(CURDIR)/sim_build/trapeziod_full_trace_reduce_M$(SAMPLE_M)_N$(SAMPLE_N)_L$(SAMPLE_L)
VERILOG_SOURCES := \
	$(COMMON_SOURCES) \
	$(RTL_DIR)/trapeziod_mesh.sv
COCOTB_TOPLEVEL := trapeziod_mesh
COCOTB_TEST_MODULES := test_trapeziod_full_trace_reduce
COMPILE_ARGS += $(TRAPEZOID_MESH_COMPILE_ARGS)
FULL_TRACE_REDUCE_JSON := $(SIM_BUILD)/trapeziod_full_trace_reduce.json
export FULL_TRACE_REDUCE_JSON
endif

ifeq ($(TEST),trapeziod_debug_flow)
SIM_BUILD := $(CURDIR)/sim_build/trapeziod_debug_flow_M$(SAMPLE_M)_N$(SAMPLE_N)_L$(SAMPLE_L)_RHD$(DEBUG_REDUCE_HOP_DELAY)
VERILOG_SOURCES := \
	$(COMMON_SOURCES) \
	$(RTL_DIR)/trapeziod_mesh.sv
COCOTB_TOPLEVEL := trapeziod_mesh
COCOTB_TEST_MODULES := test_trapeziod_debug_flow
COMPILE_ARGS += \
	-Ptrapeziod_mesh.N=$(SAMPLE_N) \
	-Ptrapeziod_mesh.M=$(SAMPLE_M) \
	-Ptrapeziod_mesh.L=$(SAMPLE_L) \
	-Ptrapeziod_mesh.REDUCE_HOP_DELAY=$(DEBUG_REDUCE_HOP_DELAY)
DEBUG_TRACE_JSON := $(SIM_BUILD)/trapeziod_debug_flow.json
DEBUG_TRACE_TXT := $(SIM_BUILD)/trapeziod_debug_flow.txt
export DEBUG_TRACE_JSON
export DEBUG_TRACE_TXT
export DEBUG_MATRIX_JSON
export DEBUG_EXPECTED_REDUCED_JSON
export DEBUG_FORWARD_RUN_CYCLES
export DEBUG_REDUCE_RUN_CYCLES
export DEBUG_REDUCE_START
export DEBUG_REDUCE_HOP_DELAY
export DEBUG_STRICT
endif

ifeq ($(COCOTB_TOPLEVEL),)
$(error Unsupported TEST='$(TEST)'; use TEST=pe_diag, TEST=pe_col, TEST=trapeziod_mesh, TEST=trapeziod_full_trace_reduce, TEST=trapeziod_debug_flow, or TEST=all)
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
