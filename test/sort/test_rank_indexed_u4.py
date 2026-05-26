import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from sort_test_utils import rank_indexed_u4


def pack_u4(values):
    packed = 0
    for idx, value in enumerate(values):
        packed |= (int(value) & 0xF) << (idx * 4)
    return packed


async def run_case(dut, values):
    dut.start_i.value = 0
    dut.ranked_raddr.value = 0
    dut.scores_i.value = pack_u4(values)
    await RisingEdge(dut.clk)
    dut.start_i.value = 1
    await RisingEdge(dut.clk)
    dut.start_i.value = 0

    for _ in range(64):
        await RisingEdge(dut.clk)
        if int(dut.done_o.value):
            top_p = int(dut.TOP_P.value)
            expected = rank_indexed_u4(values, top_p=top_p)
            observed = []
            for idx in range(top_p):
                dut.ranked_raddr.value = idx
                await Timer(1, unit="ns")
                observed.append(int(dut.ranked_rdata.value))
            assert observed == expected, (
                f"ranked indices mismatch: expected={expected} observed={observed}"
            )
            return

    raise AssertionError("rank_indexed_u4 did not finish within 64 cycles")


@cocotb.test()
async def rank_indexed_u4_directed_and_random(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst.value = 1
    dut.start_i.value = 0
    dut.scores_i.value = 0
    await RisingEdge(dut.clk)
    dut.rst.value = 0

    await run_case(dut, [5, 1, 15, 1, 3, 3, 0, 14])

    rng = random.Random(20260522)
    for _ in range(25):
        values = [rng.randrange(16) for _ in range(8)]
        await run_case(dut, values)
