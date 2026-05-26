import json
from pathlib import Path


OP_PASS = 0b00
OP_SWAP = 0b01
OP_ADD = 0b10
OP_LOCK = 0b11
OPCODE_NAMES = {
    OP_PASS: "PASS",
    OP_SWAP: "SWAP",
    OP_ADD: "ADD",
    OP_LOCK: "LOCK",
}
TEST_DIR = Path(__file__).resolve().parent
SAMPLE_MATRIX_JSON = TEST_DIR / "vectors" / "trapeziod_dynamics_sample.json"


def pack_bits(bits):
    value = 0
    for idx, bit in enumerate(bits):
        value |= (int(bit) & 1) << idx
    return value


def pe_diag_golden(r_prev, data_i, reduce_i):
    if reduce_i == 1 and r_prev == 1:
        return {
            "r_next": r_prev,
            "data_o": data_i,
            "op_o": OP_SWAP,
            "reduce_o": reduce_i,
        }
    if data_i == 0:
        return {
            "r_next": r_prev,
            "data_o": 0,
            "op_o": OP_PASS,
            "reduce_o": reduce_i,
        }
    if r_prev == 0:
        return {
            "r_next": 1,
            "data_o": 0,
            "op_o": OP_LOCK,
            "reduce_o": reduce_i,
        }
    return {
        "r_next": 1,
        "data_o": 0,
        "op_o": OP_ADD,
        "reduce_o": reduce_i,
    }


def pe_col_golden(r_prev, data_i, op_i):
    action_op = OP_LOCK if op_i in (OP_SWAP, OP_LOCK) else op_i

    if action_op == OP_LOCK:
        return {
            "r_next": data_i,
            "data_o": r_prev,
            "op_o": op_i,
        }
    if action_op == OP_ADD:
        return {
            "r_next": r_prev,
            "data_o": r_prev ^ data_i,
            "op_o": op_i,
        }
    return {
        "r_next": r_prev,
        "data_o": data_i,
        "op_o": op_i,
    }


def diag_eval(r_prev, data_i):
    observed = pe_diag_golden(r_prev=r_prev, data_i=data_i, reduce_i=0)
    return observed["r_next"], observed["op_o"]


def col_eval(r_prev, data_i, op_i):
    observed = pe_col_golden(r_prev=r_prev, data_i=data_i, op_i=op_i)
    return observed["r_next"], observed["data_o"], observed["op_o"]


class TrapezoidModel:
    def __init__(self, n, l):
        self.n = n
        self.l = l
        self.total_cols = n + l
        self.diag_r = [0 for _ in range(n)]
        self.diag_op = [OP_PASS for _ in range(n)]
        self.col_r = {
            (row, col): 0
            for row in range(n)
            for col in range(row + 1, self.total_cols)
        }
        self.col_op = {
            (row, col): OP_PASS
            for row in range(n)
            for col in range(row + 1, self.total_cols)
        }
        self.col_data = {
            (row, col): 0
            for row in range(n)
            for col in range(row + 1, self.total_cols)
        }

    def eval_cycle(self, data_top):
        next_diag = self.diag_r[:]
        next_diag_op = self.diag_op[:]
        next_col = dict(self.col_r)
        next_col_op = dict(self.col_op)
        next_col_data = dict(self.col_data)

        for row in range(self.n):
            diag_data_i = data_top[row] if row == 0 else self.col_data[(row - 1, row)]
            next_diag[row], next_diag_op[row] = diag_eval(self.diag_r[row], diag_data_i)

            for col in range(row + 1, self.total_cols):
                data_i = data_top[col] if row == 0 else self.col_data[(row - 1, col)]
                op_i = self.diag_op[row] if col == row + 1 else self.col_op[(row, col - 1)]
                next_col[(row, col)], next_col_data[(row, col)], _ = col_eval(
                    self.col_r[(row, col)], data_i, op_i
                )
                next_col_op[(row, col)] = op_i

        self.diag_r = next_diag
        self.diag_op = next_diag_op
        self.col_r = next_col
        self.col_op = next_col_op
        self.col_data = next_col_data

        return [self.col_data[(self.n - 1, self.n + idx)] for idx in range(self.l)]


def load_matrix_case(path_str):
    path = Path(path_str)
    with path.open() as f:
        payload = json.load(f)

    a_mat = payload["A"]
    b_mat = payload["B"]

    if not a_mat or not a_mat[0]:
        raise AssertionError("A must be a non-empty MxN matrix")
    if not b_mat or not b_mat[0]:
        raise AssertionError("B must be a non-empty MxL matrix")

    m = len(a_mat)
    n = len(a_mat[0])
    l = len(b_mat[0])

    if any(len(row) != n for row in a_mat):
        raise AssertionError("A has ragged rows")
    if len(b_mat) != m:
        raise AssertionError("A and B must have the same number of rows")
    if any(len(row) != l for row in b_mat):
        raise AssertionError("B has ragged rows")

    for name, mat in (("A", a_mat), ("B", b_mat)):
        for row in mat:
            for bit in row:
                if bit not in (0, 1):
                    raise AssertionError(f"{name} must contain only GF(2) bits")

    return {
        "path": str(path),
        "name": payload.get("name", path.stem),
        "A": a_mat,
        "B": b_mat,
        "M": m,
        "N": n,
        "L": l,
    }


def load_sample_case():
    return load_matrix_case(str(SAMPLE_MATRIX_JSON))


def build_top_input_streams(a_mat, b_mat):
    m = len(a_mat)
    n = len(a_mat[0])
    l = len(b_mat[0])
    total_cols = n + l
    streams = []

    for global_col in range(total_cols):
        if global_col < n:
            column_bits = [a_mat[row][global_col] for row in range(m)]
            lead_zeros = global_col
        else:
            b_col = global_col - n
            column_bits = [b_mat[row][b_col] for row in range(m)]
            # Keep staggering through the lifted rectangle too. The first B
            # column starts at t = N, then later B columns start at
            # t = N+1, N+2, ... respectively.
            lead_zeros = n + b_col

        streams.append(([0] * lead_zeros) + column_bits)

    return streams


def build_input_rows(a_mat, b_mat):
    return [
        list(a_mat[row_idx]) + list(b_mat[row_idx])
        for row_idx in range(len(a_mat))
    ]


def sample_streams_at_cycle(streams, cycle):
    return [
        stream[cycle] if cycle < len(stream) else 0
        for stream in streams
    ]


def build_data_in_by_t(streams):
    feed_cycles = max(len(stream) for stream in streams)
    return {
        f"t={cycle}": sample_streams_at_cycle(streams, cycle)
        for cycle in range(feed_cycles)
    }


def data_in_at_cycle(data_in_by_t, cycle, width):
    return data_in_by_t.get(f"t={cycle}", [0] * width)


def format_register_matrix(registers):
    return {
        f"row {row_idx}": row_values
        for row_idx, row_values in enumerate(registers)
    }


def format_reduce_mode_row(reduce_inputs):
    return [0 if reduce_i else 1 for reduce_i in reduce_inputs]


def get_diag_scope(dut, row):
    return dut.g_row[row].g_col[row].g_diag.u_pe_diag


def get_apply_scope(dut, row, col):
    return dut.g_row[row].g_col[col].g_apply.u_pe_col


def collect_register_matrix(dut, n, total_cols):
    registers = []

    for row in range(n):
        row_registers = []
        for col in range(total_cols):
            if col < row:
                row_registers.append(None)
            elif col == row:
                row_registers.append(int(get_diag_scope(dut, row).r.value))
            else:
                row_registers.append(int(get_apply_scope(dut, row, col).r.value))
        registers.append(row_registers)

    return registers


def collect_diag_data_out_row(dut, n):
    return [
        int(get_diag_scope(dut, row).data_o.value)
        for row in range(n)
    ]


def collect_diag_reduce_inputs(dut, n):
    return [
        int(get_diag_scope(dut, row).reduce_sig_i.value)
        for row in range(n)
    ]
