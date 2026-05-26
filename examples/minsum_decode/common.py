from __future__ import annotations

import hashlib
import importlib.util
import re
from pathlib import Path

import numpy as np


THIS_DIR = Path(__file__).resolve().parent
SHARED_COMMON = THIS_DIR.parent / "shared" / "reduced_solver_common.py"
DEFAULT_CASE_MODULE = THIS_DIR / "case.py"

_SPEC = importlib.util.spec_from_file_location("_reduced_solver_common", SHARED_COMMON)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"failed to load shared helpers from {SHARED_COMMON}")
_SHARED = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SHARED)

REPO_ROOT = _SHARED.REPO_ROOT
repo_relpath = _SHARED.repo_relpath

load_python_namespace = _SHARED.load_python_namespace
save_meta = _SHARED.save_meta
load_meta = _SHARED.load_meta
save_manifest = _SHARED.save_manifest
load_manifest = _SHARED.load_manifest
sha256_file = _SHARED.sha256_file
case_timestamp = _SHARED.case_timestamp
resolve_case_dir = _SHARED.resolve_case_dir
update_latest_symlink = _SHARED.update_latest_symlink
update_manifest = _SHARED.update_manifest
preview_matrix = _SHARED.preview_matrix
preview_vector = _SHARED.preview_vector
load_counts = _SHARED.load_counts
print_case_report = _SHARED.print_case_report

LLR_W = 12
LLR_FRAC = 6
ALPHA_SHIFT = 2
DEFAULT_MAX_ITER = 8


def ensure_dirs(case_dir: Path) -> dict[str, Path]:
    paths = {
        "case": case_dir,
        "problem": case_dir / "problem",
        "generated": case_dir / "generated",
        "out": case_dir / "out",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def compute_case_id(*, module_path: Path, h_mat: np.ndarray, syndrome: np.ndarray, prior_q: np.ndarray, max_iter: int) -> str:
    digest = hashlib.sha256()
    digest.update(repo_relpath(module_path).encode())
    digest.update(np.asarray(h_mat, dtype=np.uint8).tobytes())
    digest.update(np.asarray(syndrome, dtype=np.uint8).tobytes())
    digest.update(np.asarray(prior_q, dtype=np.int64).tobytes())
    digest.update(int(max_iter).to_bytes(4, byteorder="big", signed=False))
    return f"{h_mat.shape[0]}x{h_mat.shape[1]}_minsum_{digest.hexdigest()[:8]}"


def render_tb(template: str, *, m: int, n: int, e: int, row_deg_max: int) -> str:
    replacements = {
        r"localparam int M = \d+;": f"  localparam int M = {m};",
        r"localparam int N = \d+;": f"  localparam int N = {n};",
        r"localparam int E = \d+;": f"  localparam int E = {e};",
        r"localparam int ROW_DEG_MAX = \d+;": f"  localparam int ROW_DEG_MAX = {row_deg_max};",
    }
    rendered = template
    for pattern, replacement in replacements.items():
        rendered, count = re.subn(pattern, replacement, rendered, count=1)
        if count != 1:
          raise ValueError(f"failed to replace `{pattern}` in tb template")
    return rendered


def to_uint8_matrix(values, name: str) -> np.ndarray:
    dense = np.asarray(values, dtype=np.uint8)
    if dense.ndim != 2:
        raise ValueError(f"{name} must be 2D")
    if np.any((dense != 0) & (dense != 1)):
        raise ValueError(f"{name} must contain only 0/1 values")
    return dense


def to_uint8_vector(values, name: str) -> np.ndarray:
    dense = np.asarray(values, dtype=np.uint8).reshape(-1)
    if np.any((dense != 0) & (dense != 1)):
        raise ValueError(f"{name} must contain only 0/1 values")
    return dense


def to_float_vector(values, name: str) -> np.ndarray:
    return np.asarray(values, dtype=np.float64).reshape(-1)


def quantize_llr(values: np.ndarray, llr_w: int = LLR_W, llr_frac: int = LLR_FRAC) -> np.ndarray:
    scale = 1 << llr_frac
    limit = 1 << (llr_w - 1)
    quantized = np.rint(values * scale).astype(np.int64)
    return np.clip(quantized, -limit, limit - 1)


def fixed_to_float(values: np.ndarray, frac_bits: int = LLR_FRAC) -> np.ndarray:
    return np.asarray(values, dtype=np.float64) / float(1 << frac_bits)


def hard_decision_from_llr(values: np.ndarray) -> np.ndarray:
    signs = np.sign(np.asarray(values, dtype=np.int64))
    signs = np.where(signs == 0, 1, signs)
    return ((1 - signs) // 2).astype(np.uint8)


def twos_hex_lines(values: np.ndarray, width: int) -> list[str]:
    mask = (1 << width) - 1
    digits = (width + 3) // 4
    return [f"{(int(value) & mask):0{digits}x}" for value in np.asarray(values).reshape(-1)]


def bit_lines(values: np.ndarray) -> list[str]:
    return [str(int(v)) for v in np.asarray(values).reshape(-1)]


def read_bit_vector(path: Path) -> np.ndarray:
    bits = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    return np.array([int(bit) for bit in bits], dtype=np.uint8)


def read_signed_hex_vector(path: Path, width: int) -> np.ndarray:
    sign_bit = 1 << (width - 1)
    full_scale = 1 << width
    result = []
    for line in path.read_text().splitlines():
        word = line.strip()
        if not word:
            continue
        value = int(word, 16)
        if value & sign_bit:
            value -= full_scale
        result.append(value)
    return np.array(result, dtype=np.int64)


def build_row_graph(h_mat: np.ndarray) -> dict[str, np.ndarray | int]:
    m_rows, _ = h_mat.shape
    row_ptr = [0]
    edge_var: list[int] = []
    row_deg_max = 0
    for row in range(m_rows):
        cols = np.flatnonzero(h_mat[row]).astype(np.int64)
        edge_var.extend(cols.tolist())
        row_ptr.append(len(edge_var))
        row_deg_max = max(row_deg_max, int(cols.size))
    if not edge_var:
        raise ValueError("H must contain at least one edge")
    return {
        "E": len(edge_var),
        "ROW_DEG_MAX": row_deg_max,
        "row_ptr": np.array(row_ptr, dtype=np.int64),
        "edge_var": np.array(edge_var, dtype=np.int64),
    }


def minsum_reference(h_mat: np.ndarray, syndrome: np.ndarray, prior_q: np.ndarray, max_iter: int) -> tuple[np.ndarray, np.ndarray]:
    graph = build_row_graph(h_mat)
    row_ptr = graph["row_ptr"]
    edge_var = graph["edge_var"]
    m_rows, n_cols = h_mat.shape
    llr_limit = 1 << (LLR_W - 1)

    def sat_llr(value: int) -> int:
        return max(-llr_limit, min(llr_limit - 1, int(value)))

    app = np.asarray(prior_q, dtype=np.int64).copy()
    c2v = np.zeros(int(graph["E"]), dtype=np.int64)

    for _ in range(max_iter):
        for row in range(m_rows):
            start = int(row_ptr[row])
            stop = int(row_ptr[row + 1])
            row_deg = stop - start
            if row_deg == 0:
                continue

            q_vals = np.zeros(row_deg, dtype=np.int64)
            old_vals = np.zeros(row_deg, dtype=np.int64)
            vars_for_row = np.zeros(row_deg, dtype=np.int64)
            parity_all = int(syndrome[row])
            min1_mag = (1 << (LLR_W - 1)) - 1
            min2_mag = min1_mag
            min1_slot = 0

            for slot, edge in enumerate(range(start, stop)):
                var = int(edge_var[edge])
                old_msg = int(c2v[edge])
                q_val = sat_llr(int(app[var]) - old_msg)
                sign = 1 if q_val < 0 else 0
                mag = abs(q_val)
                q_vals[slot] = q_val
                old_vals[slot] = old_msg
                vars_for_row[slot] = var
                parity_all ^= sign
                if mag < min1_mag:
                    min2_mag = min1_mag
                    min1_mag = mag
                    min1_slot = slot
                elif mag < min2_mag:
                    min2_mag = mag

            for slot, edge in enumerate(range(start, stop)):
                if row_deg <= 1:
                    ext_mag = 0
                elif slot == min1_slot:
                    ext_mag = min2_mag
                else:
                    ext_mag = min1_mag
                scaled_mag = max(0, ext_mag - (ext_mag >> ALPHA_SHIFT))
                ext_sign = parity_all ^ (1 if q_vals[slot] < 0 else 0)
                new_msg = -scaled_mag if ext_sign else scaled_mag
                var = int(vars_for_row[slot])
                app[var] = sat_llr(int(app[var]) - int(old_vals[slot]) + int(new_msg))
                c2v[edge] = new_msg

    posterior = np.asarray(app, dtype=np.int64)
    hard = hard_decision_from_llr(posterior)
    return posterior, hard
