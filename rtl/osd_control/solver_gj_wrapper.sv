`timescale 1ns / 1ps

/*
 * Module: solver_gj_wrapper
 *
 * Stable reduced-system wrapper around the production systolic Gauss-Jordan
 * controller. The solver consumes a padded reduced matrix A together with a
 * single reduced syndrome column B and forwards the bottom trace bitstream.
 */
module solver_gj_wrapper #(
  parameter int ROWS_MAX = 24,
  parameter int COLS_MAX = 24,
  parameter int COUNT_W = 16,
  parameter int SRC_DEPTH = 64
) (
  input  logic                          clk,
  input  logic                          rst,
  input  logic                          start_i,
  input  logic [COUNT_W-1:0]            rows_i,
  input  logic                          a_we_i,
  input  logic [$clog2(SRC_DEPTH)-1:0]  a_waddr_i,
  input  logic [COLS_MAX-1:0]           a_wdata_i,
  input  logic                          b_we_i,
  input  logic [$clog2(SRC_DEPTH)-1:0]  b_waddr_i,
  input  logic                          b_wdata_i,
  output logic                          busy_o,
  output logic                          done_o,
  output logic                          error_o,
  output logic                          trace_valid_o,
  output logic                          trace_bit_o
);

  logic data_bottom;
  logic [(COLS_MAX*1)-1:0] b_regs_flat_unused;

  controller #(
    .N(COLS_MAX),
    .M(ROWS_MAX),
    .L(1),
    .REDUCE_HOP_DELAY(3),
    .SRC_DEPTH(SRC_DEPTH),
    .COUNT_W(COUNT_W)
  ) u_solver (
    .clk(clk),
    .rst(rst),
    .start_i(start_i),
    .reduce_enable_i(1'b1),
    .rows_i(rows_i),
    .reduce_start_i(rows_i),
    .run_cycles_i(rows_i + COUNT_W'(3 * COLS_MAX)),
    .a_base_i('0),
    .b_base_i('0),
    .a_we_i(a_we_i),
    .a_wdata_i(a_wdata_i),
    .a_waddr_i(a_waddr_i),
    .b_we_i(b_we_i),
    .b_wdata_i(b_wdata_i),
    .b_waddr_i(b_waddr_i),
    .busy_o(busy_o),
    .done_o(done_o),
    .error_o(error_o),
    .data_bottom_o(data_bottom),
    .b_regs_flat_o(b_regs_flat_unused)
  );

  assign trace_valid_o = busy_o || done_o;
  assign trace_bit_o = data_bottom;

endmodule
