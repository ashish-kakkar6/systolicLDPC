import json
import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge

from trapeziod_test_utils import (
    build_top_input_streams,
    collect_diag_data_out_row,
    collect_diag_reduce_inputs,
    collect_register_matrix,
    format_reduce_mode_row,
    format_register_matrix,
    load_sample_case,
    pack_bits,
    sample_streams_at_cycle,
)

def collect_bottom_data(dut, cycle, first_valid_cycle):
    if cycle < first_valid_cycle:
        return None

    packed = int(dut.data_bottom_o.value)
    return [(packed >> idx) & 1 for idx in range(len(dut.data_bottom_o))]


def expected_reduce_cycle(reduce_pulse_cycle, row):
    if row == 0:
        return reduce_pulse_cycle
    return reduce_pulse_cycle + ((2 * row) - 1)


@cocotb.test()
async def trapeziod_full_trace_reduce(dut):
    trace_json = Path(os.environ["FULL_TRACE_REDUCE_JSON"])
    case = load_sample_case()

    total_cols = len(dut.data_top_i)
    l = len(dut.data_bottom_o)
    n = total_cols - l
    m = case["M"]

    assert case["N"] == n, f"JSON N={case['N']} does not match DUT N={n}"
    assert case["L"] == l, f"JSON L={case['L']} does not match DUT L={l}"

    streams = build_top_input_streams(case["A"], case["B"])
    feed_cycles = max(len(stream) for stream in streams)
    reduce_pulse_cycle = m
    last_cycle = (3 * n) +  m - 1
    first_bottom_cycle = n - 1

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    dut.rst.value = 1
    dut.en_i.value = 1
    dut.reduce_i.value = 0
    dut.data_top_i.value = 0

    for _ in range(2):
        await RisingEdge(dut.clk)

    dut.rst.value = 0

    payload = {
        "name": case["name"],
        "matrix_json": case["path"],
        "M": m,
        "N": n,
        "L": l,
        "feed_cycles": feed_cycles,
        "last_input_cycle": feed_cycles - 1,
        "reduce_pulse_cycle": reduce_pulse_cycle,
        "last_cycle": last_cycle,
        "cycles": {},
    }
    reduce_mode_by_cycle = {}

    for cycle in range(last_cycle + 1):
        top_bits = sample_streams_at_cycle(streams, cycle)
        reduce_bit = 1 if cycle == reduce_pulse_cycle else 0

        await FallingEdge(dut.clk)
        dut.reduce_i.value = reduce_bit
        dut.data_top_i.value = pack_bits(top_bits)
        await RisingEdge(dut.clk)
        await ReadOnly()

        bottom_data = collect_bottom_data(dut, cycle, first_bottom_cycle)
        register_matrix = collect_register_matrix(dut, n=n, total_cols=total_cols)
        register_matrix_readable = format_register_matrix(register_matrix)
        diag_data_out = collect_diag_data_out_row(dut, n=n)
        diag_reduce_inputs = collect_diag_reduce_inputs(dut, n=n)
        reduce_mode_row = format_reduce_mode_row(diag_reduce_inputs)
        reduce_mode_by_cycle[cycle] = reduce_mode_row

        cocotb.log.info(
            "t=%02d reduce_i=%d data_bottom=%s f_data_out=%s f_reduce_mode=%s",
            cycle,
            reduce_bit,
            bottom_data,
            diag_data_out,
            reduce_mode_row,
        )
        for row_idx, row_values in enumerate(register_matrix):
            cocotb.log.info("t=%02d row %d: %s", cycle, row_idx, row_values)

        payload["cycles"][f"t={cycle}"] = {
            "reduce_i": reduce_bit,
            "data_in_row": top_bits,
            "data_bottom_row": bottom_data,
            "diag_f_data_out_row": diag_data_out,
            "f_reduce_mode_row": reduce_mode_row,
            "register_matrix": register_matrix_readable,
        }

    for row in range(n):
        expected_cycle = expected_reduce_cycle(reduce_pulse_cycle, row)
        assert reduce_mode_by_cycle[expected_cycle][row] == 0, (
            f"Expected reduce to reach f[{row},{row}] at t={expected_cycle}"
        )
        if expected_cycle > 0:
            assert reduce_mode_by_cycle[expected_cycle - 1][row] == 1, (
                f"Expected reduce to be inactive at f[{row},{row}] before t={expected_cycle}"
            )
        if expected_cycle < last_cycle:
            assert reduce_mode_by_cycle[expected_cycle + 1][row] == 1, (
                f"Expected reduce pulse at f[{row},{row}] to last one cycle"
            )

    trace_json.parent.mkdir(parents=True, exist_ok=True)
    trace_json.write_text(json.dumps(payload, indent=2) + "\n")
