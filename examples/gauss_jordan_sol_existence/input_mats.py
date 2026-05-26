import numpy as np


SEED = 20260525
M = 12
N = 18
L = 6
rng = np.random.default_rng(SEED)


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


def gf2_has_solution(a_mat: np.ndarray, b_vec: np.ndarray) -> bool:
    aug = np.concatenate([a_mat.copy(), b_vec.reshape(-1, 1).copy()], axis=1).astype(np.uint8, copy=False)
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


while True:
    base = rng.integers(0, 2, size=(M - 2, N), dtype=np.uint8)
    if gf2_rank(base) == (M - 2):
        break

A = np.vstack(
    [
        base,
        base[0] ^ base[1],
        base[2] ^ base[3],
    ]
).astype(np.uint8, copy=False)
assert gf2_rank(A) == (M - 2)

X_consistent = rng.integers(0, 2, size=(N, 3), dtype=np.uint8)
B_consistent = ((A @ X_consistent) % 2).astype(np.uint8, copy=False)

inconsistent_cols = []
while len(inconsistent_cols) < 3:
    cand = rng.integers(0, 2, size=(M, 1), dtype=np.uint8)
    if not gf2_has_solution(A, cand[:, 0]):
        inconsistent_cols.append(cand)

B = np.concatenate(
    [
        B_consistent[:, [0]],
        inconsistent_cols[0],
        B_consistent[:, [1]],
        inconsistent_cols[1],
        B_consistent[:, [2]],
        inconsistent_cols[2],
    ],
    axis=1,
).astype(np.uint8, copy=False)
