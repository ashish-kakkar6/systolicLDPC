# QEC background

## Decoding problem statement

A decoding problem is specified by:

- a parity check matrix $H \in \mathbb{F}_2^{M \times N}$
- an encoded logical operator matrix $A \in \mathbb{F}_2^{K \times N}$
- a prior probability vector $p = (p_0, \dots, p_{N-1})$

Each error location $j \in \{0, \dots, N-1\}$ is assumed to fail
independently with probability $p_j$.

Let $e \in \mathbb{F}_2^N$ denote an unknown error on the physical qubits and let

```{math}
\sigma = H e \in \mathbb{F}_2^M
```

be the observed syndrome.

The decoding task is to infer a correction $\hat{e}$ such that

```{math}
H \hat{e} = \sigma \qquad \text{and} \qquad A \hat{e} = A e.
```

This means that after the correction $\hat{e}$, the encoded logical qubits are in the code space and the correction preserves the 
equivalence class the logical qubits belong to. 

In the entirety of examples, we are working with CSS codes and the above notation presumes that we are working with the so called XZ-decoding, the syndrome $\sigma$ is split into $\sigma_X$ and $\sigma_Z$.
These are decoded independently using derived check matrices $H_X$ and $H_Z$
to obtain partial corrections $\hat{e}_X$ and $\hat{e}_Z$, which are then
combined into $\hat{e}$. This reduces the decoding problem to smaller objects by assuming $X$ and $Z$ errors are 
independent.

### BP-OSD

BP-OSD is the leading method for decoding qLDPC uses belief propagation to produce soft information and then applies
ordered-statistics decoding as a post-processing step
[Roffe, White, Burton, Campbell 2020].

Because a parity-check matrix $H$ need not have full column rank, the syndrome
equation cannot in general be solved by a direct inverse of $H$. Instead one
chooses a basis set $S \subseteq \{0, \dots, N-1\}$ such that the columns of
$H$ indexed by $S$ are linearly independent. The resulting submatrix $H_S$ has
full column rank and can be used to solve for the basis bits. If
$T = \{0, \dots, N-1\} \setminus S$ is the remainder set, the OSD-0 candidate
has the form

```{math}
H_S \hat{e}_S = \sigma \qquad \text{and} \qquad \hat{e}_T = 0.
```

The quality of the correction depends on the choice of $S$. A random basis is
usually suboptimal. OSD instead uses the BP soft-decision vector to select a
basis containing bits that are more likely to have flipped.

The OSD-0 procedure is:

1. Rank bit indices from most likely to least likely using the BP soft
   decisions.
2. Reorder the columns of $H$ according to that ranking.
3. Select the first $\mathrm{rank}(H)$ linearly independent columns as the
   basis set $S$.
4. Solve for $\hat{e}_S$ using the restricted system $H_S \hat{e}_S = \sigma$.
5. Set $\hat{e}_T = 0$ and map the result back to the original bit ordering.

OSD post-processing is typically used when BP fails to converge within a fixed
iteration budget. The resulting correction always satisfies the syndrome
equation by construction.

Reference:

- Joschka Roffe, David R. White, Simon Burton, and Earl Campbell,
  *Decoding across the quantum low-density parity-check code landscape* (2020),
  [Phys. Rev. Research 2, 043423](http://dx.doi.org/10.1103/PhysRevResearch.2.043423).

```bibtex
@article{Panteleev_2021,
  title = {Degenerate Quantum LDPC Codes With Good Finite Length Performance},
  volume = {5},
  ISSN = {2521-327X},
  url = {http://dx.doi.org/10.22331/q-2021-11-22-585},
  DOI = {10.22331/q-2021-11-22-585},
  journal = {Quantum},
  publisher = {Verein zur Forderung des Open Access Publizierens in den Quantenwissenschaften},
  author = {Panteleev, Pavel and Kalachev, Gleb},
  year = {2021},
  month = nov,
  pages = {585}
}
```


### Union-Find

For $X$-error decoding against $Z$ checks, let $H_Z$ denote the relevant check
matrix and let $T = (V, E)$ be its Tanner graph
[Delfosse, Londe, Beverland 2021]. This is a bipartite graph with vertex set

```{math}
V = V_Q \cup V_C,
```

where $V_Q = \{q_1, \dots, q_N\}$ is the qubit set and
$V_C = \{c_1, \dots, c_{r_Z}\}$ is the set of $Z$ checks.

It is convenient to represent an $X$ error $e_X \in \mathbb{F}_2^N$ by its
support $x \subseteq V_Q$. The induced syndrome $\sigma(x) \subseteq V_C$ is
the set of check nodes incident to an odd number of vertices in $x$.

The union-find decoder grows clusters around non-trivial syndrome nodes and
then searches for a correction inside each cluster. A vertex set
$E \subseteq V$ is said to be valid for a syndrome $\sigma$ if there exists

```{math}
\tilde{x} \subseteq V_Q \cap \mathrm{Int}(E)
\qquad \text{such that} \qquad
\sigma(\tilde{x}) = \sigma \cap E.
```

Here $\mathrm{Int}(E)$ denotes the interior qubit set used by the decoder. A
correction $\tilde{x}$ satisfying this condition is called a valid correction
in $E$.

Validity factorizes over connected components. If

```{math}
E = E_1 \cup \cdots \cup E_m
```

is the decomposition of $E$ into connected components, then $E$ is valid if
and only if every $E_i$ is valid. Likewise, a correction in $E$ is valid if
and only if its restriction to each $E_i$ is valid.

The decoder can therefore be summarized as follows:

1. Initialize the active set with the non-trivial syndrome nodes.
2. While some connected component is invalid, grow the active set by one graph
   neighborhood.
3. For each valid connected component, compute a local correction matching the
   syndrome restricted to that component.
4. Return the union of the local corrections.

This separates the algorithm into two subroutines:

- a component-validity test
- a component-correction solver on valid components

For a general CSS code, both subroutines reduce to solving linear systems over
$\mathbb{F}_2$.

Reference:

- Nicolas Delfosse, Vivien Londe, and Michael Beverland, *Toward a Union-Find
  decoder for quantum LDPC codes* (2021), [arXiv:2103.08049](https://arxiv.org/abs/2103.08049).
