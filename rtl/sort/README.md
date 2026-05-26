# sort RTL

Sorting and ranking blocks used by the decoder-side examples.

## Files

- [rank_indexed_u4.sv](rank_indexed_u4.sv)
  Stable smallest-first top-`P` ranker for quantized `u4` scores. This is the
  low-cycle path used by `osd_decode`. It reads one score at a time, keeps only
  the exact best `P` score/index pairs, and serves ranked indices back through
  narrow address/data ports.

## Current split

- Use the `u4` top-`P` ranker when the controller only needs the first ranked
  candidates and low score precision is acceptable.
- Prefer the memory-backed `u4` ranker when large `N_PAD` makes packed
  score/index buses unnecessarily wide and when keeping all `N_PAD` ranked
  entries would waste cycles.
