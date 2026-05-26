`timescale 1ns / 1ps

/*
 * Module: delay_line
 *
 * Reusable synchronous delay primitive.
 *
 * Parameters:
 *    W - Packed signal width.
 *    DEPTH - Number of registered delay stages.  DEPTH == 0 is pass-through.
 *
 * Inputs:
 *    clk - State update clock.
 *    rst - Synchronous reset for all delay stages.
 *    op_i - Input signal.
 *
 * Outputs:
 *    op_o - Delayed copy of <op_i>.
 *
 */
module delay_line #(
  parameter int W = 1,
  parameter int DEPTH = 1
) (
  input  logic         clk,
  input  logic         rst,
  input  logic [W-1:0] op_i,
  output logic [W-1:0] op_o
);

  generate
    if (DEPTH == 0) begin : g_passthrough
      assign op_o = op_i;
    end else begin : g_pipeline
      logic [W-1:0] stage_q [DEPTH];
      integer idx;

      always_ff @(posedge clk) begin
        if (rst) begin
          for (idx = 0; idx < DEPTH; idx = idx + 1) begin
            stage_q[idx] <= '0;
          end
        end else begin
          stage_q[0] <= op_i;
          for (idx = 1; idx < DEPTH; idx = idx + 1) begin
            stage_q[idx] <= stage_q[idx-1];
          end
        end
      end

      assign op_o = stage_q[DEPTH-1];
    end
  endgenerate

endmodule
