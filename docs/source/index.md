# systolicLDPC

```{toctree}
:maxdepth: 4
:hidden:

Introduction <self>
Installation <getting-started>
Usage <usage/index>
RTL <rtl/index>
Test <test/index>
QEC background <QEC-background/index>
```

## Summary
systolicLDPC is a modular research-oriented Python/system verilog library for decoding quantum error correcting (QEC) 
codes using systolic approaches. Given the syndrome measurements from a QEC circuit, a decoder finds the most probable set of errors (assuming independent error mechanisms).
The state of the art approaches for decoding qLDPC (quantum Low Density Parity Check) codes are BP-OSD (Belief Propagation - Ordered Statistics Decoding) and Union Find. 
Both of these and many other decoding algorithims have Gaussian Elimination over GF(2) as an important and most costly (in terms of runtime) subroutine. 

systolicLDPC provides modules for solving 

Real time quantum error correction (QEC) decoding demands low latency. Practical decoders must achieve low logical error rates
while operating within microsecond-scale feedback cycles. Although decoding
algorithms are advancing rapidly on CPUs and GPUs, FPGA-oriented decoder design
remains comparatively underexplored. One of the reasons is the complexity of
expressing decoder logic in a hardware description language (HDL) and lack of an evaluation and testing
framework early in the design process.

`systolicLDPC` is an open-source research software project for narrowing this
gap between decoding algorithm development and hardware realization. The repository
provides FPGA-oriented building blocks for scalable row-layered normalized
min-sum decoding, OSD-style post-processing, and clustering-style decoders for
quantum low-density parity-check (qLDPC) codes, with a focus on performing
binary linear algebra over GF(2) using systolic arrays.

## Statement Of Need

Decoder design should be informed not only by algorithmic performance, but also
by latency, memory movement, and hardware resource utilization. Researchers
therefore need a workflow that makes it easy to move from high-level decoder
ideas to synthesizable hardware prototypes. `systolicLDPC` addresses this need
by combining reusable RTL kernels, simulation flows, and Python wrappers for
building, running, and analyzing parameterized experiments.

## Functionality

The current repository focuses on linear-algebra kernels that dominate several
post-processing stages in qLDPC decoding, especially ordered-statistics
decoding (OSD) and clustering-style methods.

Two central computational tasks are:

1. **Solution existence.** Given a binary matrix
   $A \in \mathbb{F}_2^{m \times n}$ and a vector
   $y \in \mathbb{F}_2^m$, determine whether

   ```{math}
   y \in \mathrm{Im}(A).
   ```

2. **Solution recovery.** Given $y \in \mathrm{Im}(A)$, find any vector
   $x \in \mathbb{F}_2^n$ such that

   ```{math}
   Ax = y.
   ```

The main production RTL path in this repository implements these operations
through a systolic Gauss-Jordan architecture over GF(2).

## Documentation Map

- [Installing and getting started](getting-started.md)
- [Examples](examples.md)
- [RTL](rtl/index.md)
- [Test](test/index.md)
- [QEC background](QEC-background/index.md)

## Attribution

`systolicLDPC` is released under the GNU GPLv3. See
[`LICENSE`](../../LICENSE).

`systolicLDPC` is being prepared for submission. In the meantime, if it was
useful to you, please cite:

```bibtex
@misc{systolicLDPC,
  author = {Kakkar Ashish},
  title = {systolic approaches to decoding qLDPC codes},
  year = {2026},
  publisher = {GitHub},
  journal = {GitHub repository},
  howpublished = {\url{https://github.com/ashish-kakkar6/systolicLDPC}}
}
```
