`timescale 1ns / 1ps

/*
 * Module: mem
 *
 * Simple synchronous single-port memory with optional file initialization.
 *
 * Parameters:
 *    WIDTH - Data width in bits.
 *    DEPTH - Number of addressable words.
 *    FILE - Optional hex initialization file loaded with $readmemh.
 *
 * Inputs:
 *    clk - State update clock.
 *    we - Write enable.
 *    re - Read enable.
 *    wdata - Write data bus.
 *    waddr - Write address.
 *    raddr - Read address.
 *
 * Outputs:
 *    rdata - Registered read data output.
 *
 * Behavior:
 *    we - Writes <wdata> into location <waddr> on the positive edge of <clk>.
 *    re - Loads <rdata> from location <raddr> on the positive edge of <clk>.
 *    FILE - When not empty, initializes the memory array at time zero.
 */

module mem #(
  parameter int WIDTH = 8,
  parameter int DEPTH = 64,
  parameter FILE = ""
) (
  input  logic                     clk,
  input  logic                     we,
  input  logic                     re,
  input  logic [WIDTH-1:0]         wdata,
  input  logic [$clog2(DEPTH)-1:0] waddr,
  input  logic [$clog2(DEPTH)-1:0] raddr,
  output logic [WIDTH-1:0]         rdata
);

  logic [WIDTH-1:0] mem [0:DEPTH-1];

  initial begin
    if (FILE != "")
      $readmemh(FILE, mem);
  end

  always_ff @(posedge clk) begin
    if (we)
      mem[waddr] <= wdata;
    if (re)
      rdata <= mem[raddr];
  end

endmodule
