from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import numpy as np


THIS_DIR = Path(__file__).resolve().parent
SHARED_COMMON = THIS_DIR.parent / "shared" / "reduced_solver_common.py"
DEFAULT_INPUT_MODULE = THIS_DIR / "input_mats.py"
DEFAULT_TB_TEMPLATE = THIS_DIR / "tb_example_gauss_jordan.sv"

_SPEC = importlib.util.spec_from_file_location("_reduced_solver_common", SHARED_COMMON)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"failed to load shared reduced-solver helpers from {SHARED_COMMON}")
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
print_case_report = _SHARED.print_case_report
next_src_depth = _SHARED.next_src_depth
write_reversed_rows = _SHARED.write_reversed_rows
render_tb = _SHARED.render_solver_tb
load_trace = _SHARED.load_trace
load_counts = _SHARED.load_counts
interpret_bottom_trace = _SHARED.interpret_bottom_trace
preview_matrix = _SHARED.preview_matrix
gf2_rank = _SHARED.gf2_rank
gf2_solve_matrix = _SHARED.gf2_solve_matrix


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
    if manifest.get("workflow") != "gauss_jordan_solve":
        raise ValueError(f"{case_dir} is not a gauss_jordan_solve case")
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


def interpret_solution_from_trace(trace: np.ndarray, *, n_rows: int, l_cols: int) -> tuple[np.ndarray, np.ndarray]:
    solver_trace = interpret_bottom_trace(trace, n_rows=n_rows, l_cols=l_cols)
    x_hardware = np.flip(np.flip(solver_trace, axis=0), axis=1).astype(np.uint8, copy=False)
    return solver_trace, x_hardware


def gf2_equation_holds(a_mat: np.ndarray, x_mat: np.ndarray, b_mat: np.ndarray) -> bool:
    if a_mat.ndim != 2 or x_mat.ndim != 2 or b_mat.ndim != 2:
        return False
    if a_mat.shape[1] != x_mat.shape[0]:
        return False
    if a_mat.shape[0] != b_mat.shape[0] or x_mat.shape[1] != b_mat.shape[1]:
        return False
    return bool(np.array_equal((a_mat @ x_mat) % 2, b_mat))
