# Feeder (`input.sv`)

Source:
- `rtl/systolic_gauss_jordan/input.sv`

```{figure} ../../_static/figures/schedule-feeder.png
:alt: Scheduled feeder figure
:width: 85%

Scheduled feeder figure
```

## Function

`\input` is the production feeder. It owns the A/B memories, reads one row from
each memory per issue cycle, packs them as `{B_row, A_row}`, applies the
stagger delay bank, and drives the top edge of `trapeziod_mesh`.

The module keeps only the signals needed for execution:

- row count and base addresses
- write ports for A/B preload
- `reduce_i`
- `busy_o`, `error_o`, and `data_bottom_o`

## Internal stages

1. Read A and B rows from synchronous RAMs.
2. Form one combined row word `{B_row, A_row}`.
3. Delay column `col` by `col + 1`.
4. Gate delayed bits with delayed valid.
5. Drive `trapeziod_mesh`.
