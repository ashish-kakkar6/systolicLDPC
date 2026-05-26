`timescale 1ns / 1ps

/*
 * Module: \input
 *
 * Input pipeline
 *
 * Responsibilities:
 *   - own A/B RAM instances
 *   - issue sequential row reads from both memories
 *   - pack each emitted row as {B_row, A_row}
 *   - apply the stagger schedule expected by trapeziod_mesh
 *   - expose only the bottom boundary trace
 *
 */
module \input #(
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
  input  logic [COUNT_W-1:0]            rows_i,
  input  logic [$clog2(SRC_DEPTH)-1:0]  a_base_i,
  input  logic [$clog2(SRC_DEPTH)-1:0]  b_base_i,
  input  logic                          reduce_i,
  input  logic                          a_we_i,
  input  logic [N-1:0]                  a_wdata_i,
  input  logic [$clog2(SRC_DEPTH)-1:0]  a_waddr_i,
  input  logic                          b_we_i,
  input  logic [L-1:0]                  b_wdata_i,
  input  logic [$clog2(SRC_DEPTH)-1:0]  b_waddr_i,
  output logic                          busy_o,
  output logic                          error_o,
  output logic [L-1:0]                  data_bottom_o,
  output logic [(N*L)-1:0]              b_regs_flat_o
);

  localparam int ADDR_W = $clog2(SRC_DEPTH);
  localparam int TOTAL_COLS = N + L;

  logic                 a_re;
  logic [ADDR_W-1:0]    a_raddr;
  logic [N-1:0]         a_rdata;
  logic                 b_re;
  logic [ADDR_W-1:0]    b_raddr;
  logic [L-1:0]         b_rdata;

  logic [COUNT_W-1:0]   rows_q;
  logic [COUNT_W-1:0]   issue_count_q;
  logic [COUNT_W-1:0]   emit_index_q;
  logic [ADDR_W-1:0]    a_base_q;
  logic [ADDR_W-1:0]    b_base_q;
  logic                 response_valid_q;
  logic                 busy_q;
  logic                 error_q;
  logic                 issue_read;
  logic [TOTAL_COLS-1:0] row_data;
  logic [TOTAL_COLS-1:0] staggered_top_data;

  assign row_data = {b_rdata, a_rdata};

  assign issue_read = (!busy_q && start_i && (rows_i != '0))
                   || (busy_q && (issue_count_q < rows_q));

  assign a_re    = issue_read;
  assign b_re    = issue_read;
  assign a_raddr = (!busy_q && start_i) ? a_base_i : (a_base_q + issue_count_q[ADDR_W-1:0]);
  assign b_raddr = (!busy_q && start_i) ? b_base_i : (b_base_q + issue_count_q[ADDR_W-1:0]);

  assign busy_o  = busy_q;
  assign error_o = error_q;

  mem #(
    .WIDTH(N),
    .DEPTH(SRC_DEPTH)
  ) u_a_mem (
    .clk  (clk),
    .we   (a_we_i),
    .re   (a_re),
    .wdata(a_wdata_i),
    .waddr(a_waddr_i),
    .raddr(a_raddr),
    .rdata(a_rdata)
  );

  mem #(
    .WIDTH(L),
    .DEPTH(SRC_DEPTH)
  ) u_b_mem (
    .clk  (clk),
    .we   (b_we_i),
    .re   (b_re),
    .wdata(b_wdata_i),
    .waddr(b_waddr_i),
    .raddr(b_raddr),
    .rdata(b_rdata)
  );

  always_ff @(posedge clk) begin
    if (rst) begin
      rows_q           <= '0;
      issue_count_q    <= '0;
      emit_index_q     <= '0;
      a_base_q         <= '0;
      b_base_q         <= '0;
      response_valid_q <= 1'b0;
      busy_q           <= 1'b0;
      error_q          <= 1'b0;
    end else begin
      if (start_i && busy_q)
        error_q <= 1'b1;

      if (!busy_q && start_i) begin
        rows_q           <= rows_i;
        issue_count_q    <= (rows_i != '0) ? COUNT_W'(1) : '0;
        emit_index_q     <= '0;
        a_base_q         <= a_base_i;
        b_base_q         <= b_base_i;
        response_valid_q <= (rows_i != '0);
        busy_q           <= (rows_i != '0);
        error_q          <= (rows_i == '0);
      end else if (response_valid_q) begin
        if (issue_read)
          issue_count_q <= issue_count_q + 1'b1;

        if ((emit_index_q + 1'b1) >= rows_q) begin
          response_valid_q <= 1'b0;
          busy_q           <= 1'b0;
        end else begin
          emit_index_q <= emit_index_q + 1'b1;
        end
      end
    end
  end

  generate
    for (genvar col = 0; col < TOTAL_COLS; col++) begin : g_stagger_col
      logic delayed_data;
      logic delayed_valid;

      delay_line #(
        .W    (1),
        .DEPTH(col + 1)
      ) u_data_delay (
        .clk (clk),
        .rst (rst),
        .op_i(row_data[col]),
        .op_o(delayed_data)
      );

      delay_line #(
        .W    (1),
        .DEPTH(col + 1)
      ) u_valid_delay (
        .clk (clk),
        .rst (rst),
        .op_i(response_valid_q),
        .op_o(delayed_valid)
      );

      assign staggered_top_data[col] = delayed_valid ? delayed_data : 1'b0;
    end
  endgenerate

  trapeziod_mesh #(
    .N               (N),
    .M               (M),
    .L               (L),
    .REDUCE_HOP_DELAY(REDUCE_HOP_DELAY)
  ) u_mesh (
    .clk            (clk),
    .rst            (rst),
    .en_i           (1'b1),
    .reduce_i       (reduce_i),
    .data_top_i     (staggered_top_data),
    .data_bottom_o  (data_bottom_o),
    .diag_data_out_o(),
    .diag_reduce_in_o(),
    .a_regs_flat_o  (),
    .b_regs_flat_o  (b_regs_flat_o)
  );

endmodule
