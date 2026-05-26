from __future__ import annotations

import contextlib
import hashlib
import io
import json
import math
import re
import runpy
import struct
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.sparse import issparse


THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[1]
DRIVER_EXAMPLE_DIR = REPO_ROOT / "examples" / "example_gauss_jordan_driver"


def repo_relpath(path: Path) -> str:
    path = path.resolve()
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _normalize_public_value(value, *, base_dir: Path):
    if isinstance(value, Path):
        value = str(value)
    if isinstance(value, str):
        try:
            resolved = Path(value).expanduser().resolve(strict=False)
        except Exception:
            return value
        if resolved.is_absolute():
            try:
                return resolved.relative_to(base_dir.resolve()).as_posix()
            except ValueError:
                try:
                    return resolved.relative_to(REPO_ROOT).as_posix()
                except ValueError:
                    return value
        return value
    if isinstance(value, dict):
        return {key: _normalize_public_value(inner, base_dir=base_dir) for key, inner in value.items()}
    if isinstance(value, list):
        return [_normalize_public_value(inner, base_dir=base_dir) for inner in value]
    return value


def load_python_namespace(module_path: Path) -> dict:
    module_path = module_path.resolve()
    old_sys_path = list(sys.path)
    try:
        sys.path.insert(0, str(module_path.parent))
        with contextlib.redirect_stdout(io.StringIO()):
            return runpy.run_path(str(module_path))
    finally:
        sys.path[:] = old_sys_path


def ensure_dirs(case_dir: Path) -> dict[str, Path]:
    paths = {
        "case": case_dir,
        "reduced_data": case_dir / "reduced" / "data",
        "reduced_out": case_dir / "reduced" / "out",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def save_meta(path: Path, meta: dict) -> None:
    normalized = _normalize_public_value(meta, base_dir=path.parent)
    path.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n")


def load_meta(path: Path) -> dict:
    return json.loads(path.read_text())


def save_manifest(path: Path, manifest: dict) -> None:
    save_meta(path, manifest)


def load_manifest(path: Path) -> dict:
    return load_meta(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def case_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_case_dir(case_ref: Path) -> Path:
    case_dir = case_ref.expanduser().resolve()
    if not case_dir.exists():
        raise FileNotFoundError(f"case directory not found: {case_ref}")
    return case_dir


def update_latest_symlink(cases_root: Path, case_dir: Path) -> Path:
    latest = cases_root / "latest"
    for child in cases_root.iterdir() if cases_root.exists() else ():
        if child.name == "latest" or child.name.startswith("latest "):
            if child.is_symlink() or child.is_file():
                child.unlink()
            elif child.exists():
                backup = cases_root / "latest.backup"
                if backup.exists():
                    if backup.is_dir() and not backup.is_symlink():
                        shutil.rmtree(backup)
                    else:
                        backup.unlink()
                child.rename(backup)
    if latest.is_symlink() or latest.is_file():
        latest.unlink()
    elif latest.exists():
        backup = cases_root / "latest.backup"
        if backup.exists():
            if backup.is_dir() and not backup.is_symlink():
                shutil.rmtree(backup)
            else:
                backup.unlink()
        latest.rename(backup)
    latest.symlink_to(case_dir.name, target_is_directory=True)
    return latest


def update_manifest(path: Path, update_fn) -> dict:
    manifest = load_manifest(path)
    update_fn(manifest)
    save_manifest(path, manifest)
    return manifest


def to_uint8_dense(matrix, name: str) -> np.ndarray:
    if issparse(matrix):
        dense = matrix.toarray()
    else:
        dense = np.asarray(matrix)
    if dense.ndim != 2:
        raise ValueError(f"{name} must be 2D")
    dense = dense.astype(np.uint8, copy=False)
    if np.any((dense != 0) & (dense != 1)):
        raise ValueError(f"{name} must contain only 0/1 values")
    return dense


def to_float32_vector(values, name: str) -> np.ndarray:
    dense = np.asarray(values, dtype=np.float32)
    if dense.ndim != 1:
        raise ValueError(f"{name} must be 1D")
    return dense


def next_src_depth(m_rows: int) -> int:
    return max(64, m_rows)


def next_pow2(value: int) -> int:
    if value < 1:
        raise ValueError("value must be positive")
    return 1 << int(math.ceil(math.log2(value)))


def float32_to_bits(value: np.float32) -> int:
    return struct.unpack(">I", struct.pack(">f", float(value)))[0]


def read_indices(path: Path) -> np.ndarray:
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    return np.array([int(line) for line in lines], dtype=np.int64)


def write_reversed_rows(matrix: np.ndarray, path: Path) -> None:
    rows = ["".join(str(int(bit)) for bit in row[::-1]) for row in matrix]
    path.write_text("\n".join(rows) + "\n")


def render_solver_tb(template: str, *, n: int, m: int, l: int, reduce_hop_delay: int, src_depth: int) -> str:
    replacements = {
        r"localparam int N = \d+;": f"  localparam int N = {n};",
        r"localparam int M = \d+;": f"  localparam int M = {m};",
        r"localparam int L = \d+;": f"  localparam int L = {l};",
        r"localparam int REDUCE_HOP_DELAY = \d+;": f"  localparam int REDUCE_HOP_DELAY = {reduce_hop_delay};",
        r"localparam int SRC_DEPTH = \d+;": f"  localparam int SRC_DEPTH = {src_depth};",
    }
    rendered = template
    for pattern, replacement in replacements.items():
        rendered, count = re.subn(pattern, replacement, rendered, count=1)
        if count != 1:
            raise ValueError(f"failed to replace `{pattern}` in solver TB template")
    return rendered


def load_trace(path: Path) -> np.ndarray:
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"{path} is empty")
    width = len(lines[0])
    if any(len(line) != width for line in lines):
        raise ValueError(f"{path} has ragged rows")
    if any(set(line) - {"0", "1"} for line in lines):
        raise ValueError(f"{path} must contain only binary digits")
    return np.array([[int(bit) for bit in line] for line in lines], dtype=np.uint8)


def load_counts(path: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        if "=" in line:
            key, value = line.strip().split("=", 1)
            result[key] = int(value)
    return result


def interpret_bottom_trace(trace: np.ndarray, n_rows: int, l_cols: int) -> np.ndarray:
    needed_rows = n_rows + l_cols - 1
    if trace.shape[0] < needed_rows:
        raise ValueError(f"need at least {needed_rows} trace rows, found {trace.shape[0]}")
    if trace.shape[1] < l_cols:
        raise ValueError(f"need at least {l_cols} trace columns, found {trace.shape[1]}")
    window = trace[-needed_rows:][::-1]
    matrix = np.zeros((n_rows, l_cols), dtype=np.uint8)
    for row in range(n_rows):
        for col in range(l_cols):
            matrix[row, col] = window[row + col, col]
    return matrix


def preview_matrix(name: str, matrix: np.ndarray, max_rows: int = 6, max_cols: int = 8) -> str:
    rows = min(max_rows, matrix.shape[0])
    cols = min(max_cols, matrix.shape[1])
    preview = matrix[:rows, :cols]
    suffix = "\n..." if matrix.shape[0] > rows or matrix.shape[1] > cols else ""
    return f"{name}: shape={matrix.shape} nnz={int(matrix.sum())}\n{preview}{suffix}"


def preview_vector(name: str, vector: np.ndarray, max_items: int = 12) -> str:
    shown = vector[:max_items]
    suffix = " ..." if vector.size > max_items else ""
    return f"{name}: len={vector.size}\n{shown}{suffix}"


def emit_report(*lines: object) -> None:
    text = "\n".join(str(line) for line in lines if line is not None and str(line) != "")
    if text:
        print(text)


def print_case_report(case_dir: Path, *lines: object) -> None:
    emit_report(f"case: {repo_relpath(case_dir)}", *lines)


def print_batch_report(batch_dir: Path, *lines: object) -> None:
    emit_report(f"batch: {repo_relpath(batch_dir)}", *lines)


def gf2_rank(matrix: np.ndarray) -> int:
    a = matrix.copy().astype(np.uint8, copy=False)
    m_rows, n_cols = a.shape
    rank = 0
    for col in range(n_cols):
        pivot = None
        for row in range(rank, m_rows):
            if a[row, col]:
                pivot = row
                break
        if pivot is None:
            continue
        if pivot != rank:
            a[[rank, pivot]] = a[[pivot, rank]]
        for row in range(m_rows):
            if row != rank and a[row, col]:
                a[row, :] ^= a[rank, :]
        rank += 1
        if rank == m_rows:
            break
    return rank


def select_independent_columns(h_mat: np.ndarray, ranked_indices: np.ndarray) -> np.ndarray:
    selected: list[int] = []
    rank = 0
    for idx in ranked_indices.tolist():
        trial = h_mat[:, selected + [idx]]
        new_rank = gf2_rank(trial)
        if new_rank > rank:
            selected.append(int(idx))
            rank = new_rank
            if rank == h_mat.shape[0]:
                break
    return np.array(selected, dtype=np.int64)


def gf2_solve(a_mat: np.ndarray, b_vec: np.ndarray) -> np.ndarray:
    a = a_mat.copy().astype(np.uint8, copy=False)
    b = b_vec.reshape(-1, 1).copy().astype(np.uint8, copy=False)
    m_rows, n_cols = a.shape
    aug = np.concatenate([a, b], axis=1)
    pivot_cols: list[int] = []
    pivot_row = 0

    for col in range(n_cols):
        pivot = None
        for row in range(pivot_row, m_rows):
            if aug[row, col]:
                pivot = row
                break
        if pivot is None:
            continue
        if pivot != pivot_row:
            aug[[pivot_row, pivot]] = aug[[pivot, pivot_row]]
        for row in range(m_rows):
            if row != pivot_row and aug[row, col]:
                aug[row, :] ^= aug[pivot_row, :]
        pivot_cols.append(col)
        pivot_row += 1
        if pivot_row == m_rows:
            break

    for row in range(m_rows):
        if not aug[row, :n_cols].any() and aug[row, n_cols]:
            raise ValueError("GF(2) system is inconsistent")

    if len(pivot_cols) < n_cols:
        raise ValueError("GF(2) system is underdetermined for the selected columns")

    x = np.zeros(n_cols, dtype=np.uint8)
    for row, col in enumerate(pivot_cols):
        x[col] = aug[row, n_cols]
    return x


def gf2_solve_matrix(a_mat: np.ndarray, b_mat: np.ndarray) -> np.ndarray:
    b = np.asarray(b_mat, dtype=np.uint8)
    if b.ndim != 2:
        raise ValueError("b_mat must be 2D")
    if a_mat.shape[0] != b.shape[0]:
        raise ValueError("A and B must have the same number of rows")
    columns = [gf2_solve(a_mat, b[:, col]) for col in range(b.shape[1])]
    if not columns:
        return np.zeros((a_mat.shape[1], 0), dtype=np.uint8)
    return np.stack(columns, axis=1).astype(np.uint8, copy=False)
