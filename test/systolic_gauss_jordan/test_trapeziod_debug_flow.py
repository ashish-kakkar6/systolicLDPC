import json
import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge

from trapeziod_test_utils import (
    OPCODE_NAMES,
    build_top_input_streams,
    load_matrix_case,
    load_sample_case,
    pack_bits,
    sample_streams_at_cycle,
)


def env_int(name, default):
    value = os.environ.get(name, "")
    return default if value == "" else int(value)


def env_path(name):
    value = os.environ.get(name, "")
    return None if value == "" else Path(value)


def logic_token(value):
    bits = str(value).strip().lower()
    if len(bits) == 1:
        if bits in ("0", "1"):
            return int(bits)
        return bits
    if all(bit in ("0", "1") for bit in bits):
        return int(bits, 2)
    return bits


def opcode_token(value):
    token = logic_token(value)
    if isinstance(token, int):
        return OPCODE_NAMES.get(token, token)
    return token


def get_diag_block(dut, row):
    return dut.g_row[row].g_col[row].g_diag


def get_diag_scope(dut, row):
    return get_diag_block(dut, row).u_pe_diag


def get_apply_block(dut, row, col):
    return dut.g_row[row].g_col[col].g_apply


def get_apply_scope(dut, row, col):
    return get_apply_block(dut, row, col).u_pe_col


def collect_register_matrix(dut, n, total_cols):
    rows = []
    for row in range(n):
        row_bits = []
        for col in range(total_cols):
            if col < row:
                row_bits.append(None)
            elif col == row:
                row_bits.append(logic_token(get_diag_scope(dut, row).r.value))
            else:
                row_bits.append(logic_token(get_apply_scope(dut, row, col).r.value))
        rows.append(row_bits)
    return rows


def collect_diag_reduce_inputs(dut, n):
    return [logic_token(get_diag_scope(dut, row).reduce_sig_i.value) for row in range(n)]


def collect_diag_data_out_row(dut, n):
    return [logic_token(get_diag_scope(dut, row).data_o.value) for row in range(n)]


def collect_lifted_bottom_row(dut, l):
    packed = int(dut.data_bottom_o.value)
    return [(packed >> idx) & 1 for idx in range(l)]


def collect_full_bottom_row(dut, n, total_cols):
    bottom_row = n - 1
    observed = []
    for col in range(total_cols):
        if col < bottom_row:
            observed.append(0)
        elif col == bottom_row:
            observed.append(logic_token(get_diag_scope(dut, bottom_row).data_o.value))
        else:
            observed.append(logic_token(get_apply_scope(dut, bottom_row, col).data_o.value))
    return observed


def collect_cell_debug(dut, n, total_cols):
    cells = {}
    for row in range(n):
        for col in range(row, total_cols):
            key = f"r{row}_c{col}"
            if col == row:
                block = get_diag_block(dut, row)
                scope = block.u_pe_diag
                cells[key] = {
                    "kind": "diag",
                    "data_i": logic_token(block.data_in.value),
                    "state": logic_token(scope.r.value),
                    "data_o": logic_token(scope.data_o.value),
                    "op_o": opcode_token(scope.op_o.value),
                    "reduce_i": logic_token(scope.reduce_sig_i.value),
                    "reduce_o": logic_token(scope.reduce_sig_o.value),
                }
            else:
                block = get_apply_block(dut, row, col)
                scope = block.u_pe_col
                cells[key] = {
                    "kind": "col",
                    "data_i": logic_token(block.data_in.value),
                    "state": logic_token(scope.r.value),
                    "data_o": logic_token(scope.data_o.value),
                    "op_i": opcode_token(block.op_in.value),
                    "op_o": opcode_token(scope.op_o.value),
                }
    return cells


def dense_rows_from_registers(register_matrix, n, total_cols):
    rows = []
    for row in register_matrix:
        dense = []
        for col in range(total_cols):
            value = row[col]
            dense.append(0 if value is None else value)
        rows.append(dense)
    a_rows = [row[:n] for row in rows]
    b_rows = [row[n:] for row in rows]
    return rows, a_rows, b_rows


def recover_bottom_emitted_rows(bottom_full_rows, base_cycle, row_count, total_cols):
    recovered = []
    for row_idx in range(row_count):
        row_bits = []
        for col in range(total_cols):
            sample_cycle = base_cycle + row_idx + col
            if sample_cycle >= len(bottom_full_rows):
                row_bits.append(None)
            else:
                row_bits.append(bottom_full_rows[sample_cycle][col])
        recovered.append(row_bits)
    return recovered


def load_expected_reduce(path, n, l):
    if path is None or not path.exists():
        return None

    payload = json.loads(path.read_text())
    expected_a = payload.get("A")
    expected_b = payload.get("B")

    row_count = 0
    if expected_a is not None:
        row_count = len(expected_a)
    if expected_b is not None:
        row_count = max(row_count, len(expected_b))

    expected_rows = []
    for row_idx in range(row_count):
        row_bits = [None] * (n + l)
        if expected_a is not None and row_idx < len(expected_a):
            if len(expected_a[row_idx]) != n:
                raise AssertionError(
                    f"Expected reduce A row {row_idx} has width {len(expected_a[row_idx])}, expected {n}"
                )
            row_bits[:n] = expected_a[row_idx]
        if expected_b is not None and row_idx < len(expected_b):
            if len(expected_b[row_idx]) != l:
                raise AssertionError(
                    f"Expected reduce B row {row_idx} has width {len(expected_b[row_idx])}, expected {l}"
                )
            row_bits[n:] = expected_b[row_idx]
        expected_rows.append(row_bits)

    return {
        "path": str(path),
        "payload": payload,
        "rows": expected_rows,
    }


def compare_rows(observed_rows, expected_rows):
    mismatches = []
    if expected_rows is None:
        return mismatches

    for row_idx, expected_row in enumerate(expected_rows["rows"]):
        if row_idx >= len(observed_rows):
            mismatches.append(
                {
                    "row": row_idx,
                    "col": None,
                    "expected": expected_row,
                    "observed": None,
                    "reason": "missing observed row",
                }
            )
            continue

        observed_row = observed_rows[row_idx]
        for col_idx, expected_bit in enumerate(expected_row):
            if expected_bit is None:
                continue
            observed_bit = observed_row[col_idx]
            if observed_bit != expected_bit:
                mismatches.append(
                    {
                        "row": row_idx,
                        "col": col_idx,
                        "expected": expected_bit,
                        "observed": observed_bit,
                    }
                )
    return mismatches


async def reset_mesh(dut):
    await FallingEdge(dut.clk)
    dut.rst.value = 1
    dut.en_i.value = 1
    dut.reduce_i.value = 0
    dut.data_top_i.value = 0

    for _ in range(2):
        await RisingEdge(dut.clk)

    dut.rst.value = 0
    await ReadOnly()


async def run_trace_case(dut, *, case_name, a_mat, b_mat, reduce_enable, reduce_start_cycle, last_cycle):
    total_cols = len(dut.data_top_i)
    l = len(dut.data_bottom_o)
    n = total_cols - l
    streams = build_top_input_streams(a_mat, b_mat)
    feed_cycles = max(len(stream) for stream in streams)

    await reset_mesh(dut)

    cycles = {}
    bottom_full_rows = []

    for cycle in range(last_cycle + 1):
        top_bits = sample_streams_at_cycle(streams, cycle)
        reduce_bit = 1 if (reduce_enable and cycle == reduce_start_cycle) else 0

        await FallingEdge(dut.clk)
        dut.reduce_i.value = reduce_bit
        dut.data_top_i.value = pack_bits(top_bits)
        await RisingEdge(dut.clk)
        await ReadOnly()

        register_matrix = collect_register_matrix(dut, n=n, total_cols=total_cols)
        diag_reduce_inputs = collect_diag_reduce_inputs(dut, n=n)
        diag_data_out_row = collect_diag_data_out_row(dut, n=n)
        full_bottom_row = collect_full_bottom_row(dut, n=n, total_cols=total_cols)
        bottom_full_rows.append(full_bottom_row)

        cycles[f"t={cycle}"] = {
            "reduce_i": reduce_bit,
            "data_in_row": top_bits,
            "lifted_bottom_row": collect_lifted_bottom_row(dut, l=l),
            "full_bottom_row": full_bottom_row,
            "diag_reduce_inputs": diag_reduce_inputs,
            "diag_data_out_row": diag_data_out_row,
            "register_matrix": {
                f"row {row_idx}": row_bits
                for row_idx, row_bits in enumerate(register_matrix)
            },
            "cell_debug": collect_cell_debug(dut, n=n, total_cols=total_cols),
        }

    final_register_matrix = collect_register_matrix(dut, n=n, total_cols=total_cols)
    final_dense_rows, final_a_rows, final_b_rows = dense_rows_from_registers(
        final_register_matrix, n=n, total_cols=total_cols
    )

    return {
        "name": case_name,
        "reduce_enable": reduce_enable,
        "reduce_start_cycle": reduce_start_cycle,
        "last_cycle": last_cycle,
        "feed_cycles": feed_cycles,
        "cycles": cycles,
        "bottom_full_rows": bottom_full_rows,
        "final_register_matrix": {
            f"row {row_idx}": row_bits
            for row_idx, row_bits in enumerate(final_register_matrix)
        },
        "final_dense_rows": final_dense_rows,
        "final_a_rows": final_a_rows,
        "final_b_rows": final_b_rows,
    }


def write_text_trace(path, payload):
    with path.open("w") as handle:
        handle.write("=== trapeziod debug flow ===\n")
        handle.write(json.dumps(payload["config"], indent=2))
        handle.write("\n\n")

        for phase_name in ("forward_no_reduce", "reduce_debug"):
            phase = payload[phase_name]
            handle.write(f"=== {phase_name} ===\n")
            handle.write(
                f"reduce_enable={int(phase['reduce_enable'])} "
                f"reduce_start_cycle={phase['reduce_start_cycle']} "
                f"last_cycle={phase['last_cycle']}\n"
            )

            for cycle_key, cycle_payload in phase["cycles"].items():
                handle.write(f"{cycle_key}\n")
                handle.write(f"  reduce_i={cycle_payload['reduce_i']}\n")
                handle.write(f"  data_in_row={cycle_payload['data_in_row']}\n")
                handle.write(f"  full_bottom_row={cycle_payload['full_bottom_row']}\n")
                handle.write(f"  lifted_bottom_row={cycle_payload['lifted_bottom_row']}\n")
                handle.write(f"  diag_reduce_inputs={cycle_payload['diag_reduce_inputs']}\n")
                handle.write(f"  diag_data_out_row={cycle_payload['diag_data_out_row']}\n")
                for row_label, row_bits in cycle_payload["register_matrix"].items():
                    handle.write(f"  {row_label}: {row_bits}\n")
                handle.write("  opflow/state\n")
                for cell_name, cell_payload in cycle_payload["cell_debug"].items():
                    handle.write(f"    {cell_name}: {cell_payload}\n")
                handle.write("\n")

            handle.write(f"final_a_rows={phase['final_a_rows']}\n")
            handle.write(f"final_b_rows={phase['final_b_rows']}\n\n")

        reduce_capture = payload["reduce_capture"]
        handle.write("=== reduce capture ===\n")
        handle.write(
            f"reconstruction_base_cycle={reduce_capture['reconstruction_base_cycle']}\n"
        )
        for row_idx, observed in enumerate(reduce_capture["observed_rows"]):
            handle.write(f"observed row {row_idx}: {observed}\n")
            expected_rows = reduce_capture.get("expected_rows")
            if expected_rows is not None and row_idx < len(expected_rows):
                handle.write(f"expected row {row_idx}: {expected_rows[row_idx]}\n")
        handle.write(f"mismatch_count={len(reduce_capture['mismatches'])}\n")
        for mismatch in reduce_capture["mismatches"]:
            handle.write(f"mismatch: {mismatch}\n")


@cocotb.test()
async def trapeziod_debug_flow(dut):
    trace_json = env_path("DEBUG_TRACE_JSON")
    trace_txt = env_path("DEBUG_TRACE_TXT")
    matrix_json = env_path("DEBUG_MATRIX_JSON")
    expected_reduce_json = env_path("DEBUG_EXPECTED_REDUCED_JSON")
    strict = env_int("DEBUG_STRICT", 0) != 0

    case = load_sample_case() if matrix_json is None else load_matrix_case(str(matrix_json))

    total_cols = len(dut.data_top_i)
    l = len(dut.data_bottom_o)
    n = total_cols - l
    m = case["M"]

    assert case["N"] == n, f"JSON N={case['N']} does not match DUT N={n}"
    assert case["L"] == l, f"JSON L={case['L']} does not match DUT L={l}"

    forward_last_cycle = env_int("DEBUG_FORWARD_RUN_CYCLES", (2 * n) + m + l - 1)
    reduce_last_cycle = env_int("DEBUG_REDUCE_RUN_CYCLES", (3 * n) + m + l - 2)
    reduce_start_cycle = env_int("DEBUG_REDUCE_START", m)
    expected_reduce = load_expected_reduce(expected_reduce_json, n=n, l=l)

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.en_i.value = 1

    forward_trace = await run_trace_case(
        dut,
        case_name="forward_no_reduce",
        a_mat=case["A"],
        b_mat=case["B"],
        reduce_enable=False,
        reduce_start_cycle=reduce_start_cycle,
        last_cycle=forward_last_cycle,
    )
    reduce_trace = await run_trace_case(
        dut,
        case_name="reduce_debug",
        a_mat=case["A"],
        b_mat=case["B"],
        reduce_enable=True,
        reduce_start_cycle=reduce_start_cycle,
        last_cycle=reduce_last_cycle,
    )

    observed_rows = recover_bottom_emitted_rows(
        reduce_trace["bottom_full_rows"],
        base_cycle=reduce_start_cycle + n,
        row_count=n,
        total_cols=total_cols,
    )
    mismatches = compare_rows(observed_rows, expected_reduce)

    payload = {
        "config": {
            "matrix_json": case["path"],
            "expected_reduced_json": None if expected_reduce is None else expected_reduce["path"],
            "M": m,
            "N": n,
            "L": l,
            "reduce_hop_delay": env_int("DEBUG_REDUCE_HOP_DELAY", 2),
            "forward_last_cycle": forward_last_cycle,
            "reduce_last_cycle": reduce_last_cycle,
            "reduce_start_cycle": reduce_start_cycle,
            "strict": strict,
        },
        "forward_no_reduce": forward_trace,
        "reduce_debug": reduce_trace,
        "reduce_capture": {
            "reconstruction_base_cycle": reduce_start_cycle + n,
            "observed_rows": observed_rows,
            "expected_rows": None if expected_reduce is None else expected_reduce["rows"],
            "mismatches": mismatches,
        },
    }

    if trace_json is not None:
        trace_json.parent.mkdir(parents=True, exist_ok=True)
        trace_json.write_text(json.dumps(payload, indent=2) + "\n")

    if trace_txt is not None:
        trace_txt.parent.mkdir(parents=True, exist_ok=True)
        write_text_trace(trace_txt, payload)

    cocotb.log.info("forward final A rows: %s", forward_trace["final_a_rows"])
    cocotb.log.info("reduce final A rows: %s", reduce_trace["final_a_rows"])
    cocotb.log.info("recovered reduced bottom rows: %s", observed_rows)
    if expected_reduce is not None:
        cocotb.log.info("expected reduced rows: %s", expected_reduce["rows"])
        cocotb.log.info("reduced-row mismatch count: %d", len(mismatches))

    if strict and mismatches:
        raise AssertionError(
            "Recovered reduced bottom rows differ from expected reduced matrix; "
            f"first mismatch: {mismatches[0]}"
        )
