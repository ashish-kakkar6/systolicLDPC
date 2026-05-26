from __future__ import annotations

import hashlib
import importlib.util
import re
from pathlib import Path

import numpy as np


THIS_DIR = Path(__file__).resolve().parent
MIN_COMMON = THIS_DIR.parent / "minsum_decode" / "common.py"
OSD_COMMON = THIS_DIR.parent / "osd_decode" / "common.py"
DEFAULT_CASE_MODULE = THIS_DIR / "case.py"
BP_SCORE_SHIFT = 5


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"failed to load helper module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MIN = _load_module(MIN_COMMON, "_minsum_decode_common")
_OSD = _load_module(OSD_COMMON, "_osd_decode_common")

REPO_ROOT = _MIN.REPO_ROOT
repo_relpath = _MIN.repo_relpath

LLR_W = _MIN.LLR_W
LLR_FRAC = _MIN.LLR_FRAC

load_python_namespace = _MIN.load_python_namespace
save_meta = _MIN.save_meta
load_meta = _MIN.load_meta
save_manifest = _MIN.save_manifest
load_manifest = _MIN.load_manifest
sha256_file = _MIN.sha256_file
case_timestamp = _MIN.case_timestamp
resolve_case_dir = _MIN.resolve_case_dir
update_latest_symlink = _MIN.update_latest_symlink
update_manifest = _MIN.update_manifest
preview_matrix = _MIN.preview_matrix
preview_vector = _MIN.preview_vector
load_counts = _MIN.load_counts
print_case_report = _MIN.print_case_report
ensure_dirs = _MIN.ensure_dirs
to_uint8_matrix = _MIN.to_uint8_matrix
to_uint8_vector = _MIN.to_uint8_vector
to_float_vector = _MIN.to_float_vector
quantize_llr = _MIN.quantize_llr
fixed_to_float = _MIN.fixed_to_float
hard_decision_from_llr = _MIN.hard_decision_from_llr
twos_hex_lines = _MIN.twos_hex_lines
bit_lines = _MIN.bit_lines
read_bit_vector = _MIN.read_bit_vector
read_signed_hex_vector = _MIN.read_signed_hex_vector
build_row_graph = _MIN.build_row_graph
minsum_reference = _MIN.minsum_reference

next_pow2 = _OSD.next_pow2
write_reversed_rows = _OSD.write_reversed_rows
write_sigma_column = _OSD.write_sigma_column
write_u4_hex = _OSD.write_u4_hex
stable_sorted_indices = _OSD.stable_sorted_indices
select_independent_columns = _OSD.select_independent_columns
gf2_solve = _OSD.gf2_solve
load_binary_rows = _OSD.load_binary_rows
load_int_lines = _OSD.load_int_lines


def compute_case_id(
    *,
    module_path: Path,
    h_mat: np.ndarray,
    sigma: np.ndarray,
    prior_q: np.ndarray,
    max_iter: int,
    score_shift: int,
) -> str:
    digest = hashlib.sha256()
    digest.update(repo_relpath(module_path).encode())
    digest.update(np.asarray(h_mat, dtype=np.uint8).tobytes())
    digest.update(np.asarray(sigma, dtype=np.uint8).tobytes())
    digest.update(np.asarray(prior_q, dtype=np.int64).tobytes())
    digest.update(int(max_iter).to_bytes(4, byteorder="big", signed=False))
    digest.update(int(score_shift).to_bytes(2, byteorder="big", signed=False))
    return f"{h_mat.shape[0]}x{h_mat.shape[1]}_bp_osd_{digest.hexdigest()[:8]}"


def render_tb(template: str, *, m: int, n: int, e: int, row_deg_max: int, n_pad_max: int) -> str:
    replacements = {
        r"localparam int M = \d+;": f"  localparam int M = {m};",
        r"localparam int N = \d+;": f"  localparam int N = {n};",
        r"localparam int E = \d+;": f"  localparam int E = {e};",
        r"localparam int ROW_DEG_MAX = \d+;": f"  localparam int ROW_DEG_MAX = {row_deg_max};",
        r"localparam int N_PAD_MAX = \d+;": f"  localparam int N_PAD_MAX = {n_pad_max};",
    }
    rendered = template
    for pattern, replacement in replacements.items():
        rendered, count = re.subn(pattern, replacement, rendered, count=1)
        if count != 1:
            raise ValueError(f"failed to replace `{pattern}` in tb template")
    return rendered


def quantize_bp_posterior_u4(values: np.ndarray, score_shift: int = BP_SCORE_SHIFT) -> np.ndarray:
    mags = np.abs(np.asarray(values, dtype=np.int64))
    quantized = np.right_shift(mags, int(score_shift))
    return np.clip(quantized, 0, 14).astype(np.uint8)


def write_hex_lines(values: np.ndarray, width: int, path: Path) -> None:
    path.write_text("\n".join(twos_hex_lines(values, width)) + "\n")


def bp_osd_rtl_sources(tb_path: Path) -> list[Path]:
    sources = [
        REPO_ROOT / "rtl/minsum_bp/minsum_pkg.sv",
        REPO_ROOT / "rtl/minsum_bp/minsum_row_engine.sv",
        REPO_ROOT / "rtl/minsum_bp/minsum_decode_top.sv",
        REPO_ROOT / "rtl/bp_osd/bp_osd_score_bridge.sv",
        REPO_ROOT / "rtl/bp_osd/bp_osd_decode_top.sv",
    ]
    sources.extend(_OSD.osd_decode_rtl_sources(tb_path)[:-1])
    sources.append(tb_path)
    return sources
