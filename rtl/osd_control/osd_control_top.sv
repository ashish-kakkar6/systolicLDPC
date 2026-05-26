`timescale 1ns / 1ps

/*
 * Module: osd_control_top
 *
 * Integration top for the modular OSD control pipeline:
 *   problem_store -> control -> sorter/solver wrappers -> output
 *
 * The score path is intentionally narrow:
 *   - the store serves one u4 score at a time to the top-P ranker
 *   - the controller performs score lookups by address during ranked selection
 */
module osd_control_top #(
  parameter int M_MAX = 24,
  parameter int N_MAX = 221,
  parameter int N_PAD_MAX = 256,
  parameter int TOP_P_MAX = ((3 * M_MAX) < N_PAD_MAX) ? (3 * M_MAX) : N_PAD_MAX,
  parameter int COUNT_W = 16,
  parameter int SORT_IDX_W = (N_PAD_MAX <= 1) ? 1 : $clog2(N_PAD_MAX),
  parameter int SELECT_W = (M_MAX <= 1) ? 1 : $clog2(M_MAX + 1),
  parameter int SOLVER_SRC_DEPTH = (M_MAX < 64) ? 64 : M_MAX,
  parameter int SOLVER_ADDR_W = $clog2((M_MAX < 64) ? 64 : M_MAX)
) (
  input  logic                          clk,
  input  logic                          rst,
  input  logic                          start_i,
  input  logic                          h_we_i,
  input  logic [$clog2(M_MAX)-1:0]      h_waddr_i,
  input  logic [N_MAX-1:0]              h_wdata_i,
  input  logic                          sigma_we_i,
  input  logic [$clog2(M_MAX)-1:0]      sigma_waddr_i,
  input  logic                          sigma_wdata_i,
  input  logic                          estimate_we_i,
  input  logic [$clog2(N_PAD_MAX)-1:0]  estimate_waddr_i,
  input  logic [31:0]                   estimate_wdata_i,
  input  logic                          cutoff_we_i,
  input  logic [31:0]                   cutoff_wdata_i,
  output logic                          busy_o,
  output logic                          done_o,
  output logic                          error_o,
  output logic [SELECT_W-1:0]           selected_count_o,
  output logic [SELECT_W-1:0]           compacted_rows_o,
  output logic [(M_MAX * SORT_IDX_W)-1:0] selected_indices_flat_o,
  output logic                          reduced_write_valid_o,
  output logic [SOLVER_ADDR_W-1:0]      reduced_write_addr_o,
  output logic [M_MAX-1:0]              reduced_write_row_o,
  output logic                          reduced_write_sigma_o,
  output logic [M_MAX-1:0]              x_hardware_o,
  output logic [N_MAX-1:0]              f_hardware_o,
  output logic                          solver_start_o,
  output logic [COUNT_W-1:0]            solver_run_cycles_o,
  output logic                          solver_trace_valid_o,
  output logic                          solver_trace_bit_o
) ;

  logic [(M_MAX * N_MAX)-1:0]    h_rows_flat;
  logic [M_MAX-1:0]              sigma_flat;
  logic [3:0]                    cutoff_word;
  logic [SORT_IDX_W-1:0]         estimate_sort_raddr;
  logic [3:0]                    estimate_sort_rdata;
  logic [SORT_IDX_W-1:0]         estimate_lookup_raddr;
  logic [3:0]                    estimate_lookup_rdata;

  problem_store #(
    .M_MAX(M_MAX),
    .N_MAX(N_MAX),
    .N_PAD_MAX(N_PAD_MAX)
  ) u_store (
    .clk(clk),
    .h_we_i(h_we_i),
    .h_waddr_i(h_waddr_i),
    .h_wdata_i(h_wdata_i),
    .sigma_we_i(sigma_we_i),
    .sigma_waddr_i(sigma_waddr_i),
    .sigma_wdata_i(sigma_wdata_i),
    .estimate_we_i(estimate_we_i),
    .estimate_waddr_i(estimate_waddr_i),
    .estimate_wdata_i(estimate_wdata_i),
    .cutoff_we_i(cutoff_we_i),
    .cutoff_wdata_i(cutoff_wdata_i),
    .estimate_sort_raddr_i(estimate_sort_raddr),
    .estimate_sort_rdata_o(estimate_sort_rdata),
    .estimate_lookup_raddr_i(estimate_lookup_raddr),
    .estimate_lookup_rdata_o(estimate_lookup_rdata),
    .h_rows_flat_o(h_rows_flat),
    .sigma_flat_o(sigma_flat),
    .cutoff_o(cutoff_word)
  );

  control #(
    .M_MAX(M_MAX),
    .N_MAX(N_MAX),
    .N_PAD_MAX(N_PAD_MAX),
    .TOP_P_MAX(TOP_P_MAX),
    .COUNT_W(COUNT_W),
    .SORT_IDX_W(SORT_IDX_W),
    .SELECT_W(SELECT_W),
    .SOLVER_SRC_DEPTH(SOLVER_SRC_DEPTH),
    .SOLVER_ADDR_W(SOLVER_ADDR_W)
  ) u_controller (
    .clk(clk),
    .rst(rst),
    .start_i(start_i),
    .h_rows_flat_i(h_rows_flat),
    .sigma_flat_i(sigma_flat),
    .estimate_sort_raddr_o(estimate_sort_raddr),
    .estimate_sort_rdata_i(estimate_sort_rdata),
    .estimate_lookup_raddr_o(estimate_lookup_raddr),
    .estimate_lookup_rdata_i(estimate_lookup_rdata),
    .cutoff_i(cutoff_word),
    .busy_o(busy_o),
    .done_o(done_o),
    .error_o(error_o),
    .selected_count_o(selected_count_o),
    .compacted_rows_o(compacted_rows_o),
    .selected_indices_flat_o(selected_indices_flat_o),
    .reduced_write_valid_o(reduced_write_valid_o),
    .reduced_write_addr_o(reduced_write_addr_o),
    .reduced_write_row_o(reduced_write_row_o),
    .reduced_write_sigma_o(reduced_write_sigma_o),
    .x_hardware_o(x_hardware_o),
    .f_hardware_o(f_hardware_o),
    .solver_start_o(solver_start_o),
    .solver_run_cycles_o(solver_run_cycles_o),
    .solver_trace_valid_o(solver_trace_valid_o),
    .solver_trace_bit_o(solver_trace_bit_o)
  );

endmodule
