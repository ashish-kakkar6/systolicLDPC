# Decoder

```{toctree}
:maxdepth: 1
:hidden:

Layered min-sum decode <minsum-decode>
OSD decode pipeline <osd-decode>
```

These pages document the decoding-oriented example flows that layer ranking and
reduction logic around the systolic solver.

- [Layered min-sum decode](minsum-decode.md)
- Scalable row-layered normalized min-sum with compressed row storage,
  fixed-point `app_llr` and `c2v` state, and explicit syndrome/observable
  validation in the example flow.
- [OSD decode pipeline](osd-decode.md)
- Full stored-problem flow with hardware-side ranking, reduced-system
  construction, and solve.

## Min-sum Implementation Note

The shipped decoder-side message-passing path in this repository is now the
row-layered normalized min-sum implementation under
`rtl/minsum_bp/`. The public example flow uses:

- compressed row storage via `row_ptr` and `edge_var`
- one active row engine at a time in the reference RTL
- layered updates of `app_llr` and `c2v`
- fixed-point normalization with `alpha = 0.75`
