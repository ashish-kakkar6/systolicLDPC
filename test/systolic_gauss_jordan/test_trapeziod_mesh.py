import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge

from trapeziod_test_utils import (
    OP_ADD,
    OP_LOCK,
    OPCODE_NAMES,
    TrapezoidModel,
    build_top_input_streams,
    get_apply_scope,
    get_diag_scope,
    load_sample_case,
    pack_bits,
    sample_streams_at_cycle,
)


def first_cycle_with_opcode(trace, key, opcode):
    for cycle, snapshot in enumerate(trace):
        if snapshot[key] == opcode:
            return cycle
    raise AssertionError(f"Did not observe {OPCODE_NAMES[opcode]} on {key}")


@cocotb.test()
async def trapeziod_mesh_forward_regression(dut):
    case = load_sample_case()
    l = len(dut.data_bottom_o)
    total_cols = len(dut.data_top_i)
    n = total_cols - l

    assert case["N"] == n
    assert case["L"] == l

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    dut.rst.value = 1
    dut.en_i.value = 1
    dut.reduce_i.value = 0
    dut.data_top_i.value = 0

    for _ in range(2):
        await RisingEdge(dut.clk)

    dut.rst.value = 0

    model = TrapezoidModel(n=n, l=l)
    streams = build_top_input_streams(case["A"], case["B"])
    feed_cycles = max(len(stream) for stream in streams)
    event_trace = []

    for cycle in range(feed_cycles):
        bits = sample_streams_at_cycle(streams, cycle)
        expected_bottom = model.eval_cycle(bits)

        await FallingEdge(dut.clk)
        dut.reduce_i.value = 0
        dut.data_top_i.value = pack_bits(bits)
        await RisingEdge(dut.clk)
        await ReadOnly()

        got_bottom = [(int(dut.data_bottom_o.value) >> idx) & 1 for idx in range(l)]
        assert got_bottom == expected_bottom, (
            f"cycle {cycle}: bottom-row readout mismatch, "
            f"expected {expected_bottom}, got {got_bottom}"
        )

        snapshot = {"cycle": cycle, "f00_op_o": int(get_diag_scope(dut, 0).op_o.value)}
        for col in range(1, total_cols):
            scope = get_apply_scope(dut, 0, col)
            snapshot[f"g0{col}_op_i"] = int(scope.op_i.value)
            snapshot[f"g0{col}_op_o"] = int(scope.op_o.value)
        event_trace.append(snapshot)

    lock_launch_cycle = first_cycle_with_opcode(event_trace, "f00_op_o", OP_LOCK)
    add_launch_cycle = first_cycle_with_opcode(event_trace, "f00_op_o", OP_ADD)

    for col in range(1, total_cols):
        expected_cycle = lock_launch_cycle + (col - 1)
        assert expected_cycle < len(event_trace), (
            f"LOCK did not have enough cycles to reach g[0,{col}]"
        )
        observed = event_trace[expected_cycle][f"g0{col}_op_i"]
        assert observed == OP_LOCK, (
            f"Expected LOCK at g[0,{col}].op_i on cycle {expected_cycle}, "
            f"got {OPCODE_NAMES.get(observed, observed)}"
        )

    for col in range(1, total_cols):
        expected_cycle = add_launch_cycle + (col - 1)
        assert expected_cycle < len(event_trace), (
            f"ADD did not have enough cycles to reach g[0,{col}]"
        )
        observed = event_trace[expected_cycle][f"g0{col}_op_i"]
        assert observed == OP_ADD, (
            f"Expected ADD at g[0,{col}].op_i on cycle {expected_cycle}, "
            f"got {OPCODE_NAMES.get(observed, observed)}"
        )
