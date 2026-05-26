`timescale 1ns / 1ps

/*
 * Module: pe_diag
 *
 * Diagonal processing element for the current Gauss-Jordan systolic-array
 * See docs/source/rtl/systolic-gauss-jordan-files/pe-diag.md
 *
 */
import gj_pkg::*;

module pe_diag (
  input  logic       clk, rst,
  input  logic       en_i,
  input  logic       data_i,
  input  logic       reduce_sig_i,
  output logic       data_o,
  output logic       state_o,
  output opcode_t    op_o,
  output logic       reduce_sig_o
);

  opcode_t op_out_next;
  logic    r, r_next, data_out_next;

  // The diagonal reduce signal is meant to be delayed only by the explicit
  // two-stage mesh pipeline. Forwarding it here directly
  // here so the PE itself does not add a hidden extra cycle.
  assign reduce_sig_o = rst ? 1'b0 : reduce_sig_i;

  always_comb begin
    r_next = r;
    data_out_next = 1'b0;
    op_out_next = OP_PASS;

    if (reduce_sig_i == 1'b1 && r == 1'b1) begin
      data_out_next = data_i;
      r_next = r;
      op_out_next = OP_SWAP;
    end else if (data_i == 1'b0) begin
      r_next = r;
      op_out_next = OP_PASS;
    end else if (data_i == 1'b1 && r == 1'b0) begin
      r_next = 1'b1;
      op_out_next = OP_LOCK;
    end else if (data_i == 1'b1 && r == 1'b1) begin
      r_next = r;
      op_out_next = OP_ADD;
    end
  end

  always_ff @(posedge clk) begin
      if (rst) begin
        r <= 1'b0;
        data_o <= 1'b0;
        op_o <= OP_PASS;
      end else if (en_i) begin
        r <= r_next;
        data_o <= data_out_next;
        op_o <= op_out_next;
      end
    end

  assign state_o = r;

endmodule
