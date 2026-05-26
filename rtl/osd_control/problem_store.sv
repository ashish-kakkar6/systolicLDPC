`timescale 1ns / 1ps

/*
 * Module: problem_store
 *
 * Store the full decoding problem in local memories:
 *   - H row memory
 *   - sigma row memory
 *   - quantized u4 score memory
 *   - quantized u4 cutoff register memory
 *
 * The memories are exposed through write ports plus narrow combinational read
 * ports used by the bucket ranker and score lookup path.
 */
module problem_store #(
  parameter int M_MAX = 24,
  parameter int N_MAX = 221,
  parameter int N_PAD_MAX = 256
) (
  input  logic                              clk,
  input  logic                              h_we_i,
  input  logic [$clog2(M_MAX)-1:0]         h_waddr_i,
  input  logic [N_MAX-1:0]                  h_wdata_i,
  input  logic                              sigma_we_i,
  input  logic [$clog2(M_MAX)-1:0]         sigma_waddr_i,
  input  logic                              sigma_wdata_i,
  input  logic                              estimate_we_i,
  input  logic [$clog2(N_PAD_MAX)-1:0]     estimate_waddr_i,
  input  logic [31:0]                       estimate_wdata_i,
  input  logic                              cutoff_we_i,
  input  logic [31:0]                       cutoff_wdata_i,
  input  logic [$clog2(N_PAD_MAX)-1:0]     estimate_sort_raddr_i,
  output logic [3:0]                        estimate_sort_rdata_o,
  input  logic [$clog2(N_PAD_MAX)-1:0]     estimate_lookup_raddr_i,
  output logic [3:0]                        estimate_lookup_rdata_o,
  output logic [(M_MAX * N_MAX)-1:0]        h_rows_flat_o,
  output logic [M_MAX-1:0]                  sigma_flat_o,
  output logic [3:0]                        cutoff_o
);

  logic [N_MAX-1:0] h_row_mem [0:M_MAX-1];
  logic             sigma_mem [0:M_MAX-1];
  logic [3:0]       estimate_mem [0:N_PAD_MAX-1];
  logic [3:0]       cutoff_mem [0:0];

  always_ff @(posedge clk) begin
    if (h_we_i)
      h_row_mem[h_waddr_i] <= h_wdata_i;
    if (sigma_we_i)
      sigma_mem[sigma_waddr_i] <= sigma_wdata_i;
    if (estimate_we_i)
      estimate_mem[estimate_waddr_i] <= estimate_wdata_i[3:0];
    if (cutoff_we_i)
      cutoff_mem[0] <= cutoff_wdata_i[3:0];
  end

  generate
    for (genvar row = 0; row < M_MAX; row++) begin : g_flat_rows
      assign h_rows_flat_o[(row * N_MAX) +: N_MAX] = h_row_mem[row];
      assign sigma_flat_o[row] = sigma_mem[row];
    end
  endgenerate

  assign estimate_sort_rdata_o = estimate_mem[estimate_sort_raddr_i];
  assign estimate_lookup_rdata_o = estimate_mem[estimate_lookup_raddr_i];
  assign cutoff_o = cutoff_mem[0];

endmodule
