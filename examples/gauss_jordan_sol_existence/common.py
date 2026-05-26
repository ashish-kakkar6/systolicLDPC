from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import numpy as np


THIS_DIR = Path(__file__).resolve().parent
SHARED_COMMON = THIS_DIR.parent / "shared" / "reduced_solver_common.py"
DEFAULT_INPUT_MODULE = THIS_DIR / "input_mats.py"

_SPEC = importlib.util.spec_from_file_location("_reduced_solver_common", SHARED_COMMON)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"failed to load shared reduced-solver helpers from {SHARED_COMMON}")
_SHARED = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SHARED)

REPO_ROOT = _SHARED.REPO_ROOT
repo_relpath = _SHARED.repo_relpath
DEFAULT_TB_TEMPLATE = THIS_DIR / "tb_example_gauss_jordan_sol_existence.sv"

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
print_case_report = _SHARED.print_case_report
next_src_depth = _SHARED.next_src_depth
write_reversed_rows = _SHARED.write_reversed_rows
render_tb = _SHARED.render_solver_tb
load_trace = _SHARED.load_trace
load_counts = _SHARED.load_counts
preview_matrix = _SHARED.preview_matrix
preview_vector = _SHARED.preview_vector


def to_uint8_matrix(matrix, name: str) -> np.ndarray:
    dense = np.asarray(matrix, dtype=np.uint8)
    if dense.ndim != 2:
        raise ValueError(f"{name} must be 2D")
    if np.any((dense != 0) & (dense != 1)):
        raise ValueError(f"{name} must contain only 0/1 values")
    return dense


def ensure_dirs(case_dir: Path) -> dict[str, Path]:
    paths = {
        "case": case_dir,
        "data": case_dir / "data",
        "generated": case_dir / "generated",
        "out": case_dir / "out",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def compute_case_id(
    *,
    module_path: Path,
    a_mat: np.ndarray,
    b_mat: np.ndarray,
    reduce_enable: int,
    reduce_hop_delay: int,
    reduce_start: int,
    run_cycles: int,
) -> str:
    digest = hashlib.sha256()
    digest.update(repo_relpath(module_path).encode())
    digest.update(np.asarray(a_mat, dtype=np.uint8).tobytes())
    digest.update(np.asarray(b_mat, dtype=np.uint8).tobytes())
    digest.update(bytes([int(reduce_enable) & 0x1]))
    for value in (reduce_hop_delay, reduce_start, run_cycles):
        digest.update(int(value).to_bytes(4, byteorder="big", signed=False))
    return f"{a_mat.shape[0]}x{a_mat.shape[1]}_L{b_mat.shape[1]}_{digest.hexdigest()[:8]}"


def verify_manifest_inputs(case_dir: Path, manifest: dict) -> None:
    if manifest.get("workflow") != "gauss_jordan_sol_existence":
        raise ValueError(f"{case_dir} is not a gauss_jordan_sol_existence case")
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


def gf2_has_solution(a_mat: np.ndarray, b_mat: np.ndarray) -> bool:
    if a_mat.ndim != 2 or b_mat.ndim != 2:
        raise ValueError("A and B must be 2D")
    if b_mat.shape[1] != 1:
        raise ValueError("gauss_jordan_sol_existence expects B to have exactly one column")
    if a_mat.shape[0] != b_mat.shape[0]:
        raise ValueError("A and B must have the same number of rows")

    aug = np.concatenate(
        [a_mat.astype(np.uint8, copy=True), b_mat.astype(np.uint8, copy=True)],
        axis=1,
    )
    m_rows, n_cols_plus_one = aug.shape
    n_cols = n_cols_plus_one - 1
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
        pivot_row += 1
        if pivot_row == m_rows:
            break

    for row in range(m_rows):
        if not aug[row, :n_cols].any() and aug[row, n_cols]:
            return False
    return True


def gf2_has_solution_columns(a_mat: np.ndarray, b_mat: np.ndarray) -> np.ndarray:
    if a_mat.ndim != 2 or b_mat.ndim != 2:
        raise ValueError("A and B must be 2D")
    if a_mat.shape[0] != b_mat.shape[0]:
        raise ValueError("A and B must have the same number of rows")
    return np.array(
        [gf2_has_solution(a_mat, b_mat[:, [col]]) for col in range(b_mat.shape[1])],
        dtype=bool,
    )


def interpret_existence_from_trace(
    trace: np.ndarray,
    *,
    l_cols: int,
    configured_run_cycles: int,
) -> tuple[np.ndarray, np.ndarray, list[int | None]]:
    if trace.ndim != 2:
        raise ValueError("trace must be 2D")
    if trace.shape[1] != l_cols:
        raise ValueError(f"expected trace width {l_cols}, found {trace.shape[1]}")
    if trace.shape[0] < configured_run_cycles:
        raise ValueError(
            f"need at least {configured_run_cycles} trace rows, found {trace.shape[0]}"
        )

    # The driver writes data_bottom_o from bit L-1 down to bit 0, so reverse the
    # text trace back into logical column order before checking each RHS column.
    #
    # For solution existence, the criterion is per column over the forward-pass
    # window itself: a column is inconsistent iff any 1 reaches the bottom node
    # during the configured run cycles for that column's stream.
    bottom_trace = trace[:configured_run_cycles, :l_cols][:, ::-1].astype(np.uint8, copy=False)

    inconsistency_bits = np.any(bottom_trace != 0, axis=0).astype(np.uint8)
    has_solution = (inconsistency_bits == 0)
    first_one_cycle: list[int | None] = []
    for col in range(l_cols):
        hit_rows = np.flatnonzero(bottom_trace[:, col])
        first_one_cycle.append(None if hit_rows.size == 0 else int(hit_rows[0] + 1))
    return bottom_trace, has_solution.astype(bool, copy=False), first_one_cycle


def load_has_solution_vector(path: Path, l_cols: int) -> np.ndarray:
    bits = "".join(path.read_text().split())
    if len(bits) != l_cols:
        raise ValueError(f"{path} expected {l_cols} bits, found {len(bits)}")
    if set(bits) - {"0", "1"}:
        raise ValueError(f"{path} must contain only 0/1 digits")
    return np.array([bit == "1" for bit in bits], dtype=bool)


def load_first_one_cycle_vector(path: Path, l_cols: int) -> list[int | None]:
    lines = [line.strip() for line in path.read_text().splitlines()]
    if len(lines) != l_cols:
        raise ValueError(f"{path} expected {l_cols} rows, found {len(lines)}")
    result: list[int | None] = []
    for line in lines:
        value = int(line)
        result.append(None if value <= 0 else value)
    return result
