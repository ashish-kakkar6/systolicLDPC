ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
VENV_DIR ?= $(ROOT)/.venv
VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip

PYTHON ?= python3
SIM ?= icarus

export PATH := $(VENV_DIR)/bin:$(PATH)
export PATH := $(ROOT)/make/bin:$(PATH)
