`timescale 1ns / 1ps

/*
 * Module: controller_sol_existence
 *
 * Thin wrapper around controller.sv that computes per-column solution
 * existence directly in hardware from the streamed bottom trace.
 */
module controller_sol_existence #(
  parameter int N = 4,
  parameter int M = 4,
  parameter int L = 3,
  parameter int REDUCE_HOP_DELAY = 2,
  parameter int SRC_DEPTH = 64,
  parameter int COUNT_W = 16
) (
  input  logic                          clk,
  input  logic                          rst,
  input  logic                          start_i,
  input  logic                          reduce_enable_i,
  input  logic [COUNT_W-1:0]            rows_i,
  input  logic [COUNT_W-1:0]            reduce_start_i,
  input  logic [COUNT_W-1:0]            run_cycles_i,
  input  logic [$clog2(SRC_DEPTH)-1:0]  a_base_i,
  input  logic [$clog2(SRC_DEPTH)-1:0]  b_base_i,
  input  logic                          a_we_i,
  input  logic [N-1:0]                  a_wdata_i,
  input  logic [$clog2(SRC_DEPTH)-1:0]  a_waddr_i,
  input  logic                          b_we_i,
  input  logic [L-1:0]                  b_wdata_i,
  input  logic [$clog2(SRC_DEPTH)-1:0]  b_waddr_i,
  output logic                          busy_o,
  output logic                          done_o,
  output logic                          error_o,
  output logic [L-1:0]                  data_bottom_o,
  output logic [(N*L)-1:0]              b_regs_flat_o,
  output logic [L-1:0]                  has_solution_o,
  output logic [(L*COUNT_W)-1:0]        first_one_cycle_flat_o
) ;

  logic accepted_start;

  assign accepted_start = start_i && !busy_o;

  controller #(
    .N               (N),
    .M               (M),
    .L               (L),
    .REDUCE_HOP_DELAY(REDUCE_HOP_DELAY),
    .SRC_DEPTH       (SRC_DEPTH),
    .COUNT_W         (COUNT_W)
  ) u_controller (
    .clk            (clk),
    .rst            (rst),
    .start_i        (start_i),
    .reduce_enable_i(reduce_enable_i),
    .rows_i         (rows_i),
    .reduce_start_i (reduce_start_i),
    .run_cycles_i   (run_cycles_i),
    .a_base_i       (a_base_i),
    .b_base_i       (b_base_i),
    .a_we_i         (a_we_i),
    .a_wdata_i      (a_wdata_i),
    .a_waddr_i      (a_waddr_i),
    .b_we_i         (b_we_i),
    .b_wdata_i      (b_wdata_i),
    .b_waddr_i      (b_waddr_i),
    .busy_o         (busy_o),
    .done_o         (done_o),
    .error_o        (error_o),
    .data_bottom_o  (data_bottom_o),
    .b_regs_flat_o  (b_regs_flat_o)
  );

  solution_existence_monitor #(
    .L      (L),
    .COUNT_W(COUNT_W)
  ) u_solution_existence_monitor (
    .clk                   (clk),
    .rst                   (rst),
    .start_i               (accepted_start),
    .run_cycles_i          (run_cycles_i),
    .data_bottom_i         (data_bottom_o),
    .has_solution_o        (has_solution_o),
    .first_one_cycle_flat_o(first_one_cycle_flat_o)
  );

endmodule
