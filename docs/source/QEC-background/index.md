# QEC background

## Decoding problem statement

A decoding problem is specified by:

- a parity check matrix $H \in \mathbb{F}_2^{M \times N}$
- an encoded logical action matrix $A \in \mathbb{F}_2^{K \times N}$
- a prior error probability vector $p = (p_0, \dots, p_{N-1})$ where error location $j$ is assumed to fail independently with probability $p_j$.

Let $e \in \mathbb{F}_2^N$ denote an unknown error on the physical qubits, and let
$\sigma \in \mathbb{F}_2^M$ be the observed syndrome:

```{math}
\sigma = H e
```

The decoding task is to infer a correction $\hat{e}$ that reproduces the syndrome
and preserves the equivalence class of the encoded logical operator:

```{math}
H \hat{e} = \sigma \qquad \text{and} \qquad A \hat{e} = A e.
```

In the examples in this repository, we work with CSS codes and use the usual
split `X/Z` decoding view. The syndrome is decomposed into $\sigma_X$ and
$\sigma_Z$, decoded independently using derived check matrices $H_X$ and $H_Z$
to obtain partial corrections $\hat{e}_X$ and $\hat{e}_Z$, which are then
combined into $\hat{e}$. This assumes independent $X$ and $Z$ errors and
greatly simplifies the decoder interface.

It is useful to associate to each bit a log-likelihood weight
$\omega_j = \log \frac{1-p_j}{p_j}$.
The decoding problem of interest is then to find the most-likely error (MLE)
that satisfies the syndrome:

```{math}
\hat{e} = \arg \min_{e \in \mathbb{F}_2^N,\; He=\sigma} w(e).
```

### BP (Belief Propagation)
The Tanner graph associated with $H$ is $G=(V,E)$, where variable nodes index
columns of $H$, check nodes index rows of $H$, and an edge exists whenever
$H_{ij}=1$.

The implementation shipped in this repository is not a floating-point
sum-product decoder. Instead, it uses a **row-layered normalized min-sum**
approximation, matching the hardware under `rtl/minsum_bp/` and the Python
reference in `examples/minsum_decode/common.py`.

For each active check row $i$ and adjacent variable $j$, the decoder forms an
on-the-fly variable-to-check message

```{math}
q_{ij} = a_j - r_{ij},
```

where $a_j$ is the current a-posteriori log-likelihood ratio (LLR) for bit
$j$, and $r_{ij}$ is the previous check-to-variable message on edge $(i,j)$.
The outgoing check-to-variable update is then approximated by

```{math}
r_{ij}^{\mathrm{new}} =
\alpha
\left(
(-1)^{\sigma_i}
\prod_{j' \in N(i)\setminus \{j\}} \operatorname{sgn}(q_{ij'})
\right)
\min_{j' \in N(i)\setminus \{j\}} |q_{ij'}|,
```

with normalized min-sum factor $\alpha = 0.75$ in the current code base. The
row is processed in a layered schedule, so the bit belief is updated in place:

```{math}
a_j \leftarrow a_j - r_{ij} + r_{ij}^{\mathrm{new}}.
```

After a fixed number of iterations, the final hard decision is taken
componentwise from the posterior LLR using

```{math}
\operatorname{HD}(x) = \frac{1}{2}\left(1 - \operatorname{sgn}(x)\right),
```

with the repository convention $\operatorname{sgn}(0)=+1$, so a zero LLR maps
to the no-flip decision.

### References

- David J. C. MacKay and Radford M. Neal, *Good Error-Correcting Codes Based on
  Very Sparse Matrices* (1999),
  [IEEE Transactions on Information Theory 45(2), 399-431](https://doi.org/10.1109/18.748992).

### OSD-0

To improve convergence, the soft decision vector output by BP can be
post-processed via ordered statistics decoding (OSD). In this repository, the
OSD-0 stage consumes the final BP reliability values and uses them to choose a
linearly independent column set for a reduced solve. This is the same general
BP+OSD workflow studied for quantum LDPC codes by Roffe, White, Burton, and
Campbell, and it is also exposed in the `ldpc` software package.


Given the soft decision vector output by BP, one chooses a reduced set $S$ such that the columns of
$H$ indexed by $S$ correspond to bits that are more likely to have flipped and
are linearly independent. The resulting reduced submatrix $H_{\text{red}}$ has
full rank and can be used by the systolic solver. After row compaction, the
reduced error is found by solving the square system

```{math}
\hat{e}_{\text{red}} = H_{\text{red}}^{-1} \sigma_{\text{red}}.
```

The full error $\hat{e}$ is then obtained by scattering $\hat{e}_{\text{red}}$
back into the selected coordinates and inserting $0$ on
$\{0, \dots, N-1\} \setminus S$.

The OSD-0 algorithm therefore consists of:

- sort the BP soft-decision output vector to obtain an index ordering from least
  to most reliable,
- select the first $\mathrm{rank}(H)$ linearly independent columns as the
  basis set $S$,
- solve for $\hat{e}_{\text{red}}$ using the restricted system
  $H_{\text{red}} \hat{e}_{\text{red}} = \sigma_{\text{red}}$,
- map the result back to the original bit ordering.

### References

- Joschka Roffe, David R. White, Simon Burton, and Earl Campbell,
  *Decoding across the quantum low-density parity-check code landscape* (2020),
  [Physical Review Research 2, 043423](https://doi.org/10.1103/PhysRevResearch.2.043423).
- Joschka Roffe, *LDPC: Python tools for low density parity check codes* (2022),
  [PyPI package](https://pypi.org/project/ldpc/) and
  [source repository](https://github.com/quantumgizmos/ldpc).



### Union-Find

The Union-Find decoder grows clusters around non-trivial syndrome nodes and
then searches for a correction inside each cluster. The search for valid
clusters over connected components of the decoding graph reduces the
computational bottleneck of the algorithm into two subroutines:
- a component-validity test
- a component-correction solver on valid components

which are precisely the solution-existence and solver subroutines efficiently
handled by the systolic solver.

### References

- Nicolas Delfosse, Vivien Londe, and Michael Beverland, *Toward a Union-Find
  decoder for quantum LDPC codes* (2022),
  [IEEE Transactions on Information Theory 68(5), 3187-3199](https://doi.org/10.1109/TIT.2022.3143452),
  [arXiv:2103.08049](https://arxiv.org/abs/2103.08049).
