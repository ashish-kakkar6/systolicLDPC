#!/usr/bin/env python3
"""Print the register matrix for each cycle in a trapezoid trace JSON file."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


DEFAULT_TRACE = (
    Path(__file__).resolve().parent
    / "sim_build"
    / "trapeziod_full_trace_reduce_M4_N5_L4"
    / "trapeziod_full_trace_reduce.json"
)


def sort_cycle_key(key: str) -> int:
    match = re.search(r"(\d+)$", key)
    if not match:
        raise ValueError(f"Could not parse cycle number from key: {key}")
    return int(match.group(1))


def sort_row_key(key: str) -> int:
    match = re.search(r"(\d+)$", key)
    if not match:
        raise ValueError(f"Could not parse row number from key: {key}")
    return int(match.group(1))


def format_matrix(matrix_rows: list[list[object]]) -> str:
    formatted_rows = []
    for row in matrix_rows:
        row_items = ", ".join("None" if item is None else str(item) for item in row)
        formatted_rows.append(f"  [{row_items}]")
    return "[\n" + ",\n".join(formatted_rows) + "\n]"


def main() -> int:
    trace_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TRACE

    with trace_path.open() as f:
        trace = json.load(f)

    cycles = trace["cycles"]
    for cycle_key in sorted(cycles.keys(), key=sort_cycle_key):
        cycle_num = sort_cycle_key(cycle_key)
        register_matrix = cycles[cycle_key]["register_matrix"]
        matrix_rows = [
            register_matrix[row_key]
            for row_key in sorted(register_matrix.keys(), key=sort_row_key)
        ]
        print(f"cycle {cycle_num} :")
        print(format_matrix(matrix_rows))
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
