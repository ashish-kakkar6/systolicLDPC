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
`systolicLDPC` is an open-source research library for real time decoding quantum error correcting (QEC) 
codes using systolic approaches. 


## Introduction
Given the syndrome measurements from a QEC circuit, a decoder finds the most probable set of errors that could have caused it, 
under a set of assumptions about the error mechanisms. Practical decoders need to achieve low logical error rates while maintaining a high throughput and low latency. 
The latency floor is set by the requirement for corrections to be computed faster than new syndrome data arrives in each QEC cycle.
While different qubit modalities have different time scales associated with their QEC feedback cycles, superconducting processors need microsecond-scale feedback latency. 
This has led to a surge in research on field-programmable gate array (FPGA)
decoder design for quantum LDPC codes, including recent work by
[Maurya et al. (2026)](https://arxiv.org/abs/2511.21660) and
[Báscones, Garcia-Herrero, and Valls (2025)](https://doi.org/10.1140/epjqt/s40507-025-00446-y).

Systolic arrays are stronger alternatives to traditional computational approaches for specific algorithms  as they limit latency bottlenecks by passing data through a localized array of processing elements (PE) in parallel.
The structure of systolic arrays allows for all PE's to be run simultaneously rather than sequentially. The data can be fed in a timed and interleaved way resulting
in a pipelined mechanism to compute the output. The regularity of such systolic architectures enables a spatial dataflow implementation in which the entire
network is physically unrolled onto the FPGA fabric, following the classical
systolic-architecture viewpoint of
[Kung (1982)](https://doi.org/10.1109/MC.1982.1653825). 

## Statement Of Need

Although research in CPU decoding algorithms is advancing rapidly, on their realization on FPGA's remains comparatively underexplored. One of the reasons
is the complexity of expressing decoder logic in a hardware description language (HDL) and lack of an evaluation and testing
framework early in the design process. Researchers need a workflow that makes it easy to move from high-level decoder ideas to synthesizable hardware prototypes.

`systolicLDPC` is an open-source research software project for narrowing this gap between decoding algorithm development and hardware realization. The repository
provides FPGA-oriented building blocks for combining reusable RTL kernels, simulation flows, and Python wrappers for hardware deployable QEC decoding experiments. 


## Functionality

`systolicLDPC` currently exposes two main hardware capabilities: a production
systolic solver over $\mathrm{GF}(2)$, and decoder pipelines that use that
solver as a post-processing kernel.

### 1. Systolic solver over $\mathrm{GF}(2)$

The core solver implements systolic Gauss-Jordan elimination. This operation
appears repeatedly in qLDPC decoding whenever a reduced linear system must be
checked or solved.

Two central solver-facing subroutines are supported:

1. **Solution existence.** Given a binary matrix
   $A \in \mathbb{F}_2^{m \times n}$ and $l$ right-hand sides
   $b \in \mathbb{F}_2^{m}$, determine for each column whether there exists
   $x \in \mathbb{F}_2^n$ such that

   ```{math}
   A x = b.
   ```

   The hardware returns a Boolean vector of length $l$, where `True` means a
   solution exists, in `2 n + m + l - 1` clock cycles.

2. **Solve.** Given a matrix of $l$ right-hand sides
   $B \in \mathbb{F}_2^{m \times l}$ for which solutions exist, compute a set
   of solution vectors $X \in \mathbb{F}_2^{n \times l}$ such that

   ```{math}
   A X = B.
   ```

   The hardware returns the $l$ solution vectors in
   `3 n + m + l - 1` clock cycles.

The solver RTL is documented in [RTL: Systolic Gauss-Jordan](rtl/systolic-gauss-jordan.md).
The available runnable flows are:

- [Usage: Gauss-Jordan solve](usage/gauss-jordan-solve.md)
- [Usage: Gauss-Jordan solution existence](usage/gauss-jordan-sol-existence.md)

### 2. Decoder pipelines

The second major capability is end-to-end decoder construction around the same
systolic solver. In the current repository, this path consists of a small
message-passing module and a reduced-system OSD module.

1. **OSD.** Given a Stim-derived parity-check matrix $H$, a vector of error priors,
   and a measured syndrome $\sigma$, ordered statistics decoding (OSD) ranks
   candidate columns, selects the first $\mathrm{rank}(H)$ linearly
   independent ones, and solves the resulting reduced system on the systolic
   kernel.

   In the present hardware flow, the RTL controller performs the following steps:

   - reliability-score ranking,
   - linear-independence filtering,
   - row compaction,
   - reduced solve,
   - reconstruction of the full error estimate.

   The runnable hardware-oriented example is
   [Usage: OSD decode](usage/osd-decode.md).

2. **BP-OSD.** The most complete decoder flow in the repository prepends OSD
   with a message-passing front-end. The current implementation is a
   row-layered normalized min-sum decoder. It runs for a fixed iteration count, produces posterior LLRs, and forwards
   their derived probabilities directly into the OSD stage in hardware.

   The decoder therefore follows the sequence:

   - run layered normalized min-sum on the Tanner graph of $H$,
   - form a hard decision and posterior reliability vector,
   - rank bits by BP-derived probabilities,
   - solve the reduced OSD system on the systolic solver.

   The BP front-end RTL is documented in [RTL: Min-sum BP](rtl/minsum-bp.md).
   The available runnable flows are:

   - [Usage: Layered min-sum decode](usage/minsum-decode.md)
   - [Usage: BP-OSD decode](usage/bp-osd-decode.md)

### References

- H. T. Kung, *Why systolic architectures?* (1982),
  [Computer 15(1), 37-46](https://doi.org/10.1109/MC.1982.1653825).
- Satvik Maurya, Thilo Maurer, Markus Bühler, Drew Vandeth, and Michael E. Beverland,
  *FPGA-tailored algorithms for real-time decoding of quantum LDPC codes* (2026),
  [arXiv:2511.21660](https://arxiv.org/abs/2511.21660).
- Diego Báscones, Francisco Garcia-Herrero, and Javier Valls,
  *Exploring the FPGA and ASIC design space of belief propagation and ordered
  statistics decoders for quantum error correction codes* (2025),
  [EPJ Quantum Technology 12, 140](https://doi.org/10.1140/epjqt/s40507-025-00446-y).
## Documentation Map

- [Installing and getting started](getting-started.md)
- [Usage](usage/index.md)
- [RTL](rtl/index.md)
- [Test](test/index.md)
- [QEC background](QEC-background/index.md)

## Attribution

`systolicLDPC` is released under the GNU GPLv3. See
[`LICENSE`](../../LICENSE).

This project is actively being developed.

If `systolicLDPC` was useful to you, please cite:

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
