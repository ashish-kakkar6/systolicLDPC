`timescale 1ns / 1ps

module rank_indexed_u4_tb;
  localparam int N = 8;
  localparam int TOP_P = 5;
  localparam int IDX_W = (N <= 1) ? 1 : $clog2(N);

  logic                   clk;
  logic                   rst;
  logic                   start_i;
  logic [(N * 4)-1:0]     scores_i;
  logic [IDX_W-1:0]       score_raddr;
  logic [3:0]             score_rdata;
  logic [IDX_W-1:0]       ranked_raddr;
  logic [IDX_W-1:0]       ranked_rdata;
  logic                   busy_o;
  logic                   done_o;

  assign score_rdata = scores_i[(score_raddr * 4) +: 4];

  rank_indexed_u4 #(
    .N(N),
    .IDX_W(IDX_W),
    .TOP_P(TOP_P)
  ) u_rank (
    .clk(clk),
    .rst(rst),
    .start_i(start_i),
    .score_raddr_o(score_raddr),
    .score_rdata_i(score_rdata),
    .ranked_raddr_i(ranked_raddr),
    .busy_o(busy_o),
    .done_o(done_o),
    .ranked_rdata_o(ranked_rdata)
  );

endmodule
