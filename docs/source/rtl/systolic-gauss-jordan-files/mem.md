# Memory (`mem.sv`)


Source file: `rtl/systolic_gauss_jordan/mem.sv`

Synchronous single-port memory used in wrappers around the mesh. 

## Parameters

- `WIDTH`
- `DEPTH`
- `FILE`

## Ports

- `clk`
- `we`
- `re`
- `wdata[WIDTH-1:0]`
- `waddr[$clog2(DEPTH)-1:0]`
- `raddr[$clog2(DEPTH)-1:0]`
- `rdata[WIDTH-1:0]`

Back to [Systolic Gauss-Jordan](../systolic-gauss-jordan.md).
