import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge

from trapeziod_test_utils import (
    OP_ADD,
    OP_LOCK,
    OP_PASS,
    OP_SWAP,
    OPCODE_NAMES,
    pe_col_golden,
)


async def reset_dut(dut):
    await FallingEdge(dut.clk)
    dut.rst.value = 1
    dut.en_i.value = 1
    dut.data_i.value = 0
    dut.op_i.value = OP_PASS

    for _ in range(2):
        await RisingEdge(dut.clk)

    dut.rst.value = 0


async def step(dut, data_i, op_i):
    await FallingEdge(dut.clk)
    dut.data_i.value = data_i
    dut.op_i.value = op_i
    await RisingEdge(dut.clk)
    await ReadOnly()

    return {
        "r": int(dut.r.value),
        "data_o": int(dut.data_o.value),
        "op_o": int(dut.op_o.value),
    }


@cocotb.test()
async def pe_col_truth_table_exhaustive(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.en_i.value = 1

    opcodes = [OP_PASS, OP_SWAP, OP_ADD, OP_LOCK]

    for r_prev in (0, 1):
        for data_i in (0, 1):
            for op_i in opcodes:
                await reset_dut(dut)

                if r_prev == 1:
                    preload = await step(dut, 1, OP_LOCK)
                    assert preload["r"] == 1, "Failed to preload pe_col.r to 1"

                observed = await step(dut, data_i, op_i)
                expected = pe_col_golden(r_prev=r_prev, data_i=data_i, op_i=op_i)

                mismatch_row = (
                    f"(r_prev={r_prev}, data_i={data_i}, op_i={OPCODE_NAMES[op_i]})"
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
