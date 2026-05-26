`timescale 1ns / 1ps

/*
 * Module: solution_existence_monitor
 *
 * Watches the bottom trace for one configured forward-pass window and records
 * whether each RHS column ever emitted a 1 at the bottom node.
 */
module solution_existence_monitor #(
  parameter int L = 1,
  parameter int COUNT_W = 16
) (
  input  logic                      clk,
  input  logic                      rst,
  input  logic                      start_i,
  input  logic [COUNT_W-1:0]        run_cycles_i,
  input  logic [L-1:0]              data_bottom_i,
  output logic [L-1:0]              has_solution_o,
  output logic [(L*COUNT_W)-1:0]    first_one_cycle_flat_o
);

  logic                  active_q;
  logic [COUNT_W-1:0]    sample_count_q;
  logic [L-1:0]          seen_one_q;
  logic [COUNT_W-1:0]    first_one_cycle_q [0:L-1];

  assign has_solution_o = ~seen_one_q;

  generate
    genvar col;
    for (col = 0; col < L; col++) begin : g_pack
      assign first_one_cycle_flat_o[(col*COUNT_W) +: COUNT_W] = first_one_cycle_q[col];
    end
  endgenerate

  always_ff @(posedge clk) begin
    int col;
    if (rst) begin
      active_q       <= 1'b0;
      sample_count_q <= '0;
      seen_one_q     <= '0;
      for (col = 0; col < L; col++)
        first_one_cycle_q[col] <= '0;
    end else begin
      if (start_i) begin
        active_q       <= (run_cycles_i != '0);
        sample_count_q <= '0;
        seen_one_q     <= '0;
        for (col = 0; col < L; col++)
          first_one_cycle_q[col] <= '0;
      end else if (active_q) begin
        for (col = 0; col < L; col++) begin
          if (data_bottom_i[col] && !seen_one_q[col]) begin
            seen_one_q[col] <= 1'b1;
            first_one_cycle_q[col] <= sample_count_q + COUNT_W'(1);
          end
        end

        if ((sample_count_q + COUNT_W'(1)) >= run_cycles_i) begin
          active_q <= 1'b0;
        end else begin
          sample_count_q <= sample_count_q + COUNT_W'(1);
        end
      end
    end
  end

endmodule
