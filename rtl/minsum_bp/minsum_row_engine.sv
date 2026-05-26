`timescale 1ns / 1ps

import minsum_pkg::*;

module minsum_row_engine #(
  parameter int ROW_DEG_MAX = 4,
  parameter int LLR_W = 12,
  parameter int ALPHA_SHIFT = 2
) (
  input  logic [((ROW_DEG_MAX <= 1) ? 1 : $clog2(ROW_DEG_MAX + 1))-1:0] row_deg_i,
  input  logic                                                             syndrome_bit_i,
  input  logic signed [(ROW_DEG_MAX * LLR_W)-1:0]                          row_q_flat_i,
  output logic signed [(ROW_DEG_MAX * LLR_W)-1:0]                          row_msg_flat_o
);

  localparam int ROW_DEG_W = (ROW_DEG_MAX <= 1) ? 1 : $clog2(ROW_DEG_MAX + 1);
  localparam int MAX_MAG = (1 << (LLR_W - 1)) - 1;

  integer slot_idx;

  function automatic logic signed [LLR_W-1:0] q_at(input int slot);
    q_at = $signed(row_q_flat_i[(slot * LLR_W) +: LLR_W]);
  endfunction

  function automatic int unsigned q_abs(input logic signed [LLR_W-1:0] value);
    int signed wide_value;
    wide_value = {{(32-LLR_W){value[LLR_W-1]}}, value};
    if (wide_value < 0)
      q_abs = -wide_value;
    else
      q_abs = wide_value;
  endfunction

  function automatic logic signed [LLR_W-1:0] int_to_llr(input integer value);
    int_to_llr = $signed(value[LLR_W-1:0]);
  endfunction

  always_comb begin
    logic parity_all;
    int unsigned min1_mag;
    int unsigned min2_mag;
    integer min1_slot;
    int unsigned row_deg;
    logic signs [0:ROW_DEG_MAX-1];
    int unsigned mags [0:ROW_DEG_MAX-1];

    row_msg_flat_o = '0;
    row_deg = int'($unsigned(row_deg_i));
    parity_all = syndrome_bit_i;
    min1_mag = MAX_MAG;
    min2_mag = MAX_MAG;
    min1_slot = 0;

    for (slot_idx = 0; slot_idx < ROW_DEG_MAX; slot_idx++) begin
      if (slot_idx < row_deg) begin
        signs[slot_idx] = (q_at(slot_idx) < 0) ? 1 : 0;
        mags[slot_idx] = q_abs(q_at(slot_idx));
        parity_all = parity_all ^ signs[slot_idx];
        if (mags[slot_idx] < min1_mag) begin
          min2_mag = min1_mag;
          min1_mag = mags[slot_idx];
          min1_slot = slot_idx;
        end else if (mags[slot_idx] < min2_mag) begin
          min2_mag = mags[slot_idx];
        end
      end else begin
        signs[slot_idx] = 0;
        mags[slot_idx] = MAX_MAG;
      end
    end

    for (slot_idx = 0; slot_idx < ROW_DEG_MAX; slot_idx++) begin
      logic signed [LLR_W-1:0] new_msg;
      int unsigned ext_mag;
      int unsigned scaled_mag;
      logic ext_sign;

      new_msg = '0;
      ext_mag = '0;
      scaled_mag = '0;
      ext_sign = 1'b0;
      if (slot_idx < row_deg) begin
        if (row_deg <= 1)
          ext_mag = 0;
        else if (slot_idx == min1_slot)
          ext_mag = min2_mag;
        else
          ext_mag = min1_mag;

        scaled_mag = alpha_scale_mag(ext_mag, ALPHA_SHIFT);
        ext_sign = parity_all ^ signs[slot_idx];
        if (ext_sign != 0)
          new_msg = -int_to_llr(scaled_mag);
        else
          new_msg = int_to_llr(scaled_mag);
      end
      row_msg_flat_o[(slot_idx * LLR_W) +: LLR_W] = new_msg;
    end
  end

endmodule
