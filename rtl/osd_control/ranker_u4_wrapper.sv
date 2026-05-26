`timescale 1ns / 1ps

/*
 * Module: ranker_u4_wrapper
 *
 * Stable wrapper around the low-precision u4 top-P ranker.
 *
 * The wrapper keeps the sorter on a narrow memory-backed interface:
 *   - one score read address/data port
 *   - one ranked-index read address/data port
 */
module ranker_u4_wrapper #(
  parameter int N_PAD_MAX = 256,
  parameter int IDX_W = (N_PAD_MAX <= 1) ? 1 : $clog2(N_PAD_MAX),
  parameter int TOP_P_MAX = N_PAD_MAX
) (
  input  logic                         clk,
  input  logic                         rst,
  input  logic                         start_i,
  output logic [IDX_W-1:0]             score_raddr_o,
  input  logic [3:0]                   score_rdata_i,
  input  logic [IDX_W-1:0]             ranked_raddr_i,
  output logic                         busy_o,
  output logic                         done_o,
  output logic [IDX_W-1:0]             ranked_rdata_o
);

  rank_indexed_u4 #(
    .N(N_PAD_MAX),
    .IDX_W(IDX_W),
    .TOP_P(TOP_P_MAX)
  ) u_rank (
    .clk(clk),
    .rst(rst),
    .start_i(start_i),
    .score_raddr_o(score_raddr_o),
    .score_rdata_i(score_rdata_i),
    .ranked_raddr_i(ranked_raddr_i),
    .busy_o(busy_o),
    .done_o(done_o),
    .ranked_rdata_o(ranked_rdata_o)
  );

endmodule
