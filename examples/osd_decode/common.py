from __future__ import annotations

import contextlib
import hashlib
import io
import json
import math
import re
import runpy
import shutil
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.sparse import issparse


THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[1]
DEFAULT_CASE_MODULE = THIS_DIR / "case.py"
DEFAULT_STIM_MODULE = THIS_DIR / "stim_example.py"


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
        "problem": case_dir / "problem",
        "generated": case_dir / "generated",
        "out": case_dir / "out",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def ensure_batch_dirs(batch_dir: Path) -> dict[str, Path]:
    paths = {
        "batch": batch_dir,
        "problem": batch_dir / "problem",
        "generated": batch_dir / "generated",
        "shots": batch_dir / "shots",
        "out": batch_dir / "out",
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


def compute_case_id(
    *,
    module_path: Path,
    h_mat: np.ndarray,
    sigma: np.ndarray,
    estimate_u4: np.ndarray,
    cutoff_u4: int,
    top_p_max: int,
) -> str:
    digest = hashlib.sha256()
    digest.update(repo_relpath(module_path).encode())
    digest.update(np.asarray(h_mat, dtype=np.uint8).tobytes())
    digest.update(np.asarray(sigma, dtype=np.uint8).tobytes())
    digest.update(np.asarray(estimate_u4, dtype=np.uint8).tobytes())
    digest.update(bytes([int(cutoff_u4) & 0xF]))
    digest.update(int(top_p_max).to_bytes(4, "big", signed=False))
    return f"{h_mat.shape[0]}x{h_mat.shape[1]}_{digest.hexdigest()[:8]}"


def compute_batch_id(
    *,
    module_path: Path,
    h_mat: np.ndarray,
    sigmas: np.ndarray,
    actual_observables: np.ndarray,
    estimate_u4: np.ndarray,
    cutoff_u4: int,
    top_p_max: int,
) -> str:
    digest = hashlib.sha256()
    digest.update(repo_relpath(module_path).encode())
    digest.update(np.asarray(h_mat, dtype=np.uint8).tobytes())
    digest.update(np.asarray(sigmas, dtype=np.uint8).tobytes())
    digest.update(np.asarray(actual_observables, dtype=np.uint8).tobytes())
    digest.update(np.asarray(estimate_u4, dtype=np.uint8).tobytes())
    digest.update(bytes([int(cutoff_u4) & 0xF]))
    digest.update(int(top_p_max).to_bytes(4, "big", signed=False))
    return f"{h_mat.shape[0]}x{h_mat.shape[1]}_shots{sigmas.shape[0]}_{digest.hexdigest()[:8]}"


def case_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_case_dir(case_ref: Path) -> Path:
    case_dir = case_ref.expanduser().resolve()
    if not case_dir.exists():
        raise FileNotFoundError(f"case directory not found: {case_ref}")
    return case_dir


def update_latest_symlink(cases_root: Path, case_dir: Path) -> Path:
    latest = cases_root / "latest"
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


def verify_manifest_inputs(case_dir: Path, manifest: dict) -> None:
    if manifest.get("workflow") != "osd_decode":
        raise ValueError(f"{case_dir} is not an osd_decode case")
    if manifest.get("case_id") != case_dir.name:
        raise ValueError(f"{case_dir} does not match manifest case_id")
    stages = manifest.get("stages", {})
    if not stages.get("built", False):
        raise ValueError(f"{case_dir} is not marked built")
    for key, rel_path in manifest.get("files", {}).items():
        if key not in manifest.get("hashes", {}):
            continue
        file_path = case_dir / rel_path
        if not file_path.exists():
            raise FileNotFoundError(f"manifest file missing: {file_path}")
        actual_hash = sha256_file(file_path)
        expected_hash = manifest["hashes"][key]
        if actual_hash != expected_hash:
            raise ValueError(f"manifest mismatch for {file_path}; rerun build.py")


def verify_batch_manifest_inputs(batch_dir: Path, manifest: dict) -> None:
    if manifest.get("workflow") != "osd_decode_batch":
        raise ValueError(f"{batch_dir} is not an osd_decode_batch directory")
    if manifest.get("batch_id") != batch_dir.name:
        raise ValueError(f"{batch_dir} does not match manifest batch_id")
    stages = manifest.get("stages", {})
    if not stages.get("built", False):
        raise ValueError(f"{batch_dir} is not marked built")
    for key, rel_path in manifest.get("files", {}).items():
        if key not in manifest.get("hashes", {}):
            continue
        file_path = batch_dir / rel_path
        if not file_path.exists():
            raise FileNotFoundError(f"manifest file missing: {file_path}")
        actual_hash = sha256_file(file_path)
        expected_hash = manifest["hashes"][key]
        if actual_hash != expected_hash:
            raise ValueError(f"manifest mismatch for {file_path}; rerun build_batch.py")


def update_manifest(path: Path, update_fn) -> dict:
    manifest = load_manifest(path)
    update_fn(manifest)
    save_manifest(path, manifest)
    return manifest


def emit_report(*lines: object) -> None:
    text = "\n".join(str(line) for line in lines if line is not None and str(line) != "")
    if text:
        print(text)


def print_case_report(case_dir: Path, *lines: object) -> None:
    emit_report(f"case: {repo_relpath(case_dir)}", *lines)


def print_batch_report(batch_dir: Path, *lines: object) -> None:
    emit_report(f"batch: {repo_relpath(batch_dir)}", *lines)


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


def next_pow2(value: int) -> int:
    if value < 1:
        raise ValueError("value must be positive")
    return 1 << int(math.ceil(math.log2(value)))


def float32_to_bits(value: np.float32) -> int:
    return struct.unpack(">I", struct.pack(">f", float(value)))[0]


def bits_to_float32(bits: int) -> np.float32:
    return np.float32(struct.unpack(">f", struct.pack(">I", bits & 0xFFFF_FFFF))[0])


def write_reversed_rows(matrix: np.ndarray, path: Path) -> None:
    rows = ["".join(str(int(bit)) for bit in row[::-1]) for row in matrix]
    path.write_text("\n".join(rows) + "\n")


def write_sigma_column(sigma: np.ndarray, path: Path) -> None:
    path.write_text("\n".join(str(int(bit)) for bit in sigma[:, 0]) + "\n")


def write_score_hex(values: np.ndarray, path: Path) -> None:
    path.write_text("\n".join(f"{float32_to_bits(value):08x}" for value in values) + "\n")


def write_cutoff_hex(value: np.float32, path: Path) -> None:
    path.write_text(f"{float32_to_bits(value):08x}\n")


def quantize_scores_u4(values: np.ndarray, cutoff: np.float32) -> tuple[np.ndarray, np.uint8, dict[str, float]]:
    scores = np.asarray(values, dtype=np.float32)
    if scores.ndim != 1:
        raise ValueError("values must be 1D")
    if scores.size == 0:
        raise ValueError("values must be non-empty")

    low = float(min(float(np.min(scores)), float(cutoff)))
    high = float(max(float(np.max(scores)), float(cutoff)))

    if high <= low:
        quantized = np.zeros(scores.shape, dtype=np.uint8)
        cutoff_q = np.uint8(0)
    else:
        scale = 14.0 / (high - low)
        quantized = np.floor((scores - low) * scale + 1.0e-6).clip(0.0, 14.0).astype(np.uint8)
        cutoff_scaled = int(math.ceil((float(cutoff) - low) * scale - 1.0e-6))
        cutoff_q = np.uint8(min(14, max(0, cutoff_scaled)))

    return quantized, cutoff_q, {"low": low, "high": high, "sentinel": 15.0}


def write_u4_hex(values: np.ndarray, path: Path) -> None:
    packed = np.asarray(values, dtype=np.uint8)
    if packed.ndim != 1:
        raise ValueError("u4 values must be 1D")
    if np.any(packed > 15):
        raise ValueError("u4 values must be in the range 0..15")
    path.write_text("\n".join(f"{int(value):x}" for value in packed) + "\n")


def write_u4_scalar_hex(value: int, path: Path) -> None:
    if value < 0 or value > 15:
        raise ValueError("u4 scalar must be in the range 0..15")
    path.write_text(f"{int(value):x}\n")


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


def stable_sorted_indices(values: np.ndarray) -> np.ndarray:
    return np.argsort(values, kind="stable")


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
        raise ValueError("GF(2) system is underdetermined")

    x = np.zeros(n_cols, dtype=np.uint8)
    for row, col in enumerate(pivot_cols):
        x[col] = aug[row, n_cols]
    return x


def render_tb(template: str, *, m_max: int, n_max: int, n_pad_max: int) -> str:
    replacements = {
        r"localparam int M_MAX = \d+;": f"  localparam int M_MAX = {m_max};",
        r"localparam int N_MAX = \d+;": f"  localparam int N_MAX = {n_max};",
        r"localparam int N_PAD_MAX = \d+;": f"  localparam int N_PAD_MAX = {n_pad_max};",
    }
    rendered = template
    for pattern, replacement in replacements.items():
        rendered, count = re.subn(pattern, replacement, rendered, count=1)
        if count != 1:
            raise ValueError(f"failed to replace `{pattern}` in TB template")
    return rendered


def load_binary_rows(path: Path) -> np.ndarray:
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if not lines:
        return np.zeros((0, 0), dtype=np.uint8)
    width = len(lines[0])
    if any(len(line) != width for line in lines):
        raise ValueError(f"{path} has ragged rows")
    return np.array([[int(bit) for bit in line] for line in lines], dtype=np.uint8)


def load_int_lines(path: Path) -> np.ndarray:
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    return np.array([int(line) for line in lines], dtype=np.int64)


def load_counts(path: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in path.read_text().splitlines():
        if "=" in line:
            key, value = line.strip().split("=", 1)
            result[key] = int(value)
    return result


def load_trace(path: Path) -> np.ndarray:
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if not lines:
        return np.zeros((0, 1), dtype=np.uint8)
    if any(set(line) - {"0", "1"} for line in lines):
        raise ValueError(f"{path} must contain only binary digits")
    return np.array([[int(bit) for bit in line] for line in lines], dtype=np.uint8)


def interpret_bottom_trace(trace: np.ndarray, n_rows: int, l_cols: int) -> np.ndarray:
    needed_rows = n_rows + l_cols - 1
    if trace.shape[0] < needed_rows:
        raise ValueError(f"need at least {needed_rows} trace rows, found {trace.shape[0]}")
    window = trace[-needed_rows:][::-1]
    matrix = np.zeros((n_rows, l_cols), dtype=np.uint8)
    for row in range(n_rows):
        for col in range(l_cols):
            matrix[row, col] = window[row + col, col]
    return matrix


def osd_decode_rtl_sources(tb_path: Path) -> list[Path]:
    return [
        REPO_ROOT / "rtl/osd_control/problem_store.sv",
        REPO_ROOT / "rtl/osd_control/ranker_u4_wrapper.sv",
        REPO_ROOT / "rtl/osd_control/solver_gj_wrapper.sv",
        REPO_ROOT / "rtl/osd_control/control.sv",
        REPO_ROOT / "rtl/osd_control/osd_control_top.sv",
        REPO_ROOT / "rtl/sort/rank_indexed_u4.sv",
        REPO_ROOT / "rtl/systolic_gauss_jordan/gj_pkg.sv",
        REPO_ROOT / "rtl/systolic_gauss_jordan/delay_line.sv",
        REPO_ROOT / "rtl/systolic_gauss_jordan/mem.sv",
        REPO_ROOT / "rtl/systolic_gauss_jordan/pe_diag.sv",
        REPO_ROOT / "rtl/systolic_gauss_jordan/pe_col.sv",
        REPO_ROOT / "rtl/systolic_gauss_jordan/trapeziod_mesh.sv",
        REPO_ROOT / "rtl/systolic_gauss_jordan/input.sv",
        REPO_ROOT / "rtl/systolic_gauss_jordan/controller.sv",
        tb_path,
    ]
