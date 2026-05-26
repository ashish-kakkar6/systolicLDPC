`timescale 1ns / 1ps

/*
 * Module: trapeziod_mesh
 *
 * Pure structural trapezoidal Gauss-Jordan mesh.
 *
 * This file models the processing-element grid. The matrix-row count
 * <M> is carried only as documentation for the eventual feeder; the
 * structural mesh height is driven by <N>
 *
 * Parameters:
 *    N - Number of elimination columns in A, and therefore the number of
 *        diagonal cells / mesh rows.
 *    M - Number of streamed rows in A and B.  Unused in this structural mesh.
 *    L - Number of lifted columns to the right of the N x N triangular region.
 *
 * Ports:
 *    clk - State update clock shared by every cell.
 *    rst - Synchronous reset shared by every cell.
 *    reduce_i - External reduce/forward pulse launched into the first diagonal cell.
 *    data_top_i - Top-edge data inputs for all global columns, width N+L.
 *    data_bottom_o - Bottom-row d_out observations for the lifted rectangle.
 *
 *
 * Debugging Notes:
 *    The cocotb tests reach into the generated hierarchy, so the
 *    scopes `g_row`, `g_col`, `g_diag`, `g_apply`, `u_pe_diag`, `u_pe_col`,
 *    and the local signal name `data_in` are kept stable.
 */
import gj_pkg::*;

module trapeziod_mesh #(
  parameter int N = 4,
  parameter int M = 4,
  parameter int L = 3,
  parameter int REDUCE_HOP_DELAY = 2
) (
  input  logic             clk,
  input  logic             rst,
  input  logic             en_i,
  input  logic             reduce_i,
  input  logic [(N+L)-1:0] data_top_i,
  output logic [L-1:0]     data_bottom_o,
  output logic [N-1:0]     diag_data_out_o,
  output logic [N-1:0]     diag_reduce_in_o,
  output logic [(N*N)-1:0] a_regs_flat_o,
  output logic [(N*L)-1:0] b_regs_flat_o
);

  localparam int MESH_ROWS  = N;
  localparam int TOTAL_COLS = N + L;
  localparam opcode_t OP_IDENTITY = OP_PASS;

  // Vertical data bus:
  //   data_down_bus[row][col] is produced by cell (row,col) and consumed by
  //   the cell directly below at (row+1,col).
  logic data_down_bus [0:MESH_ROWS-1][0:TOTAL_COLS-1];

  // Horizontal control bus:
  //   op_bus[row][col] is produced by cell (row,col) and consumed by the cell
  //   immediately to the right at (row,col+1).
  opcode_t op_bus [0:MESH_ROWS-1][0:TOTAL_COLS-1];

  // Reduce path between diagonal cells.  Each row after row 0 receives the
  // previous diagonal cell's forwarded reduce bit through an explicit
  // registered pipeline.
  logic reduce_in_bus  [0:MESH_ROWS-1];
  logic reduce_out_bus [0:MESH_ROWS-1];
  localparam int REDUCE_PIPE_STAGES = (REDUCE_HOP_DELAY < 1) ? 1 : REDUCE_HOP_DELAY;
  logic reduce_pipe_q [1:MESH_ROWS-1][0:REDUCE_PIPE_STAGES-1];

  assign reduce_in_bus[0] = reduce_i;

  generate
    for (genvar reduce_row = 1; reduce_row < MESH_ROWS; reduce_row++) begin : g_reduce_path
      assign reduce_in_bus[reduce_row] = reduce_pipe_q[reduce_row][REDUCE_PIPE_STAGES-1];
    end
  endgenerate

  always_ff @(posedge clk) begin
    if (rst) begin
      for (int row_i = 1; row_i < MESH_ROWS; row_i++) begin
        for (int stage_i = 0; stage_i < REDUCE_PIPE_STAGES; stage_i++) begin
          reduce_pipe_q[row_i][stage_i] <= 1'b0;
        end
      end
    end else if (en_i) begin
      for (int row_i = 1; row_i < MESH_ROWS; row_i++) begin
        reduce_pipe_q[row_i][0] <= reduce_out_bus[row_i - 1];
        for (int stage_i = 1; stage_i < REDUCE_PIPE_STAGES; stage_i++) begin
          reduce_pipe_q[row_i][stage_i] <= reduce_pipe_q[row_i][stage_i - 1];
        end
      end
    end
  end

  generate
    for (genvar diag_row = 0; diag_row < MESH_ROWS; diag_row++) begin : g_diag_debug
      assign diag_reduce_in_o[diag_row] = reduce_in_bus[diag_row];
    end
  endgenerate

  generate
    for (genvar row = 0; row < MESH_ROWS; row++) begin : g_row
      for (genvar col = 0; col < TOTAL_COLS; col++) begin : g_col

        // The lower-left region is outside the trapezoid.  Tie it off so every
        // bus element has a defined value in simulation.
        if (col < row) begin : g_inactive
          assign data_down_bus[row][col] = 1'b0;
          assign op_bus[row][col]        = OP_IDENTITY;
          if (col < N) begin : g_a_export_inactive
            assign a_regs_flat_o[(row * N) + col] = 1'b0;
          end

        // Diagonal cell.  It consumes only vertical data and the row's
        // incoming reduce signal, and it emits the control opcode to the right.
        end else if (col == row) begin : g_diag
          logic data_in;
          logic data_out_local;
          logic state_local;

          if (row == 0) begin : g_diag_top
            assign data_in = data_top_i[col];
          end else begin : g_diag_from_above
            assign data_in = data_down_bus[row-1][col];
          end

          pe_diag u_pe_diag (
            .clk         (clk),
            .rst         (rst),
            .en_i        (en_i),
            .data_i      (data_in),
            .reduce_sig_i(reduce_in_bus[row]),
            .data_o      (data_out_local),
            .state_o     (state_local),
            .op_o        (op_bus[row][col]),
            .reduce_sig_o(reduce_out_bus[row])
          );

          // In forward mode the diagonal emits 0 downward; in reduce mode it
          // emits the stored bit, matching the h-cell sketch.
          assign data_down_bus[row][col] = data_out_local;
          assign diag_data_out_o[row] = data_out_local;
          assign a_regs_flat_o[(row * N) + col] = state_local;

        // Off-diagonal cell.  It consumes vertical data from above and the
        // horizontal control token from its left neighbor, then emits a new
        // vertical data bit and forwards control to the right.
        end else begin : g_apply
          logic    data_in;
          opcode_t op_in;
          logic    data_out_local;
          opcode_t op_out_local;
          logic    state_local;

          if (row == 0) begin : g_apply_top
            assign data_in = data_top_i[col];
          end else begin : g_apply_from_above
            assign data_in = data_down_bus[row-1][col];
          end

          assign op_in = op_bus[row][col-1];
          assign data_down_bus[row][col] = data_out_local;
          assign op_bus[row][col]        = op_out_local;

          pe_col u_pe_col (
            .clk   (clk),
            .rst   (rst),
            .en_i  (en_i),
            .data_i(data_in),
            .op_i  (op_in),
            .op_o  (op_out_local),
            .data_o(data_out_local),
            .state_o(state_local)
          );

          if (col >= N) begin : g_b_regs_export
            assign b_regs_flat_o[(row * L) + (col - N)] = state_local;
          end else begin : g_a_regs_export
            assign a_regs_flat_o[(row * N) + col] = state_local;
          end
        end
      end
    end
  endgenerate

  // Only the rectangle on the far right is architecturally observed at
  // the bottom boundary.
  generate
    for (genvar lift_col = 0; lift_col < L; lift_col++) begin : g_bottom_readout
      assign data_bottom_o[lift_col] = data_down_bus[MESH_ROWS-1][N + lift_col];
    end
  endgenerate

endmodule
