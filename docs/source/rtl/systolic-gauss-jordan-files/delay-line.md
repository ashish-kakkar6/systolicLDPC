# Delay Line (`delay_line.sv`)
Source file: `rtl/systolic_gauss_jordan/delay_line.sv`

Delay primitive that supports timing alignment of `op_i`/`op_o` signals.

![Delay line block figure](../../_static/figures/systolic_lifted_gauss_jordan_delay_line.svg)


## Parameters

- `W`: packed signal width
- `DEPTH`: number of registered delays, with `DEPTH == 0` as pass-through

## Ports

- `clk`: clock signal
- `rst`: reset
- `op_i[W-1:0]`: op in
- `op_o[W-1:0]`:  op out

## Behaviour

`op_o` is a delayed copy in `op_i`.

Back to [Systolic Gauss-Jordan](../systolic-gauss-jordan.md).
