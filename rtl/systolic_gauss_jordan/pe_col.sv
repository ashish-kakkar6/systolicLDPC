`timescale 1ns / 1ps

/*
 * Module: pe_col
 *
 * Column processing element for the current Gauss-Jordan systolic-array.
 * See docs/source/rtl/systolic-gauss-jordan-files/pe-col.md
 *
 *    ---
 */
import gj_pkg::*;

module pe_col (
  input  logic       clk, rst,
  input  logic       en_i,
  input  logic       data_i,
  input  opcode_t    op_i,
  output opcode_t    op_o,
  output logic       data_o,
  output logic       state_o
);

  logic r;
  logic r_next;
  logic data_o_next;

  always_comb begin

    case (op_i)
      OP_ADD: begin
        data_o_next = r^data_i;
        r_next = r;
      end
      OP_SWAP: begin
        r_next = data_i;
        data_o_next = r;
      end
      OP_LOCK: begin
        r_next = data_i;
        data_o_next = r;
      end
      OP_PASS: begin
        r_next = r;
        data_o_next = data_i;
      end
      default: begin
        r_next = r;
        data_o_next = data_i;
      end
    endcase
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      r <= 1'b0;
      data_o <= 1'b0;
      op_o <= OP_PASS;
    end else if (en_i) begin
      op_o <= op_i;
      data_o <= data_o_next;
      r <= r_next;
    end
  end

  assign state_o = r;



endmodule
