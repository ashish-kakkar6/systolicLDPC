import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge

from trapeziod_test_utils import (
    OP_ADD,
    OP_LOCK,
    OP_PASS,
    OPCODE_NAMES,
    pe_diag_golden,
)


async def reset_dut(dut):
    await FallingEdge(dut.clk)
    dut.rst.value = 1
    dut.en_i.value = 1
    dut.data_i.value = 0
    dut.reduce_sig_i.value = 0

    for _ in range(2):
        await RisingEdge(dut.clk)

    dut.rst.value = 0


async def step(dut, data_i, reduce_sig_i):
    await FallingEdge(dut.clk)
    dut.data_i.value = data_i
    dut.reduce_sig_i.value = reduce_sig_i
    await RisingEdge(dut.clk)
    await ReadOnly()

    return {
        "r": int(dut.r.value),
        "data_o": int(dut.data_o.value),
        "op_o": int(dut.op_o.value),
        "reduce_o": int(dut.reduce_sig_o.value),
    }


@cocotb.test()
async def pe_diag_truth_table_exhaustive(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.en_i.value = 1

    for reduce_sig_i in (0, 1):
        for r_prev in (0, 1):
            for data_i in (0, 1):
                await reset_dut(dut)

                if r_prev == 1:
                    preload = await step(dut, 1, 0)
                    assert preload["r"] == 1, "Failed to preload pe_diag.r to 1"
                    assert preload["op_o"] == OP_LOCK, (
                        "Expected preload cycle to lock the diagonal state"
                    )

                observed = await step(dut, data_i, reduce_sig_i)
                expected = pe_diag_golden(
                    r_prev=r_prev,
                    data_i=data_i,
                    reduce_i=reduce_sig_i,
                )

                mismatch_row = (
                    f"(reduce_sig_i={reduce_sig_i}, r_prev={r_prev}, data_i={data_i})"
                )

                assert observed["r"] == expected["r_next"], (
                    f"{mismatch_row}: expected r_next={expected['r_next']}, "
                    f"got {observed['r']}"
                )
                assert observed["data_o"] == expected["data_o"], (
                    f"{mismatch_row}: expected data_o={expected['data_o']}, "
                    f"got {observed['data_o']}"
                )
                assert observed["op_o"] == expected["op_o"], (
                    f"{mismatch_row}: expected op_o={OPCODE_NAMES[expected['op_o']]}, "
                    f"got {OPCODE_NAMES.get(observed['op_o'], observed['op_o'])}"
                )
                assert observed["reduce_o"] == expected["reduce_o"], (
                    f"{mismatch_row}: expected reduce_o={expected['reduce_o']}, "
                    f"got {observed['reduce_o']}"
                )
