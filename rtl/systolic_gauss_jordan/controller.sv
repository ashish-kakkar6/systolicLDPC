`timescale 1ns / 1ps

/*
 * Module: controller
 *
 * Top
 *
 * Responsibilities:
 *   - own one experiment start/done handshake
 *   - latch run configuration
 *   - emit the optional reduce pulse
 *   - stop at the configured run window
 *   - expose only the bottom trace plus control status
 *
 * Composition:
 *   controller =
 *     run control + input
 */
module controller #(
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
  input  logic                          reduce_enable_i,
  input  logic [COUNT_W-1:0]            rows_i,
  input  logic [COUNT_W-1:0]            reduce_start_i,
  input  logic [COUNT_W-1:0]            run_cycles_i,
  input  logic [$clog2(SRC_DEPTH)-1:0]  a_base_i,
  input  logic [$clog2(SRC_DEPTH)-1:0]  b_base_i,
  input  logic                          a_we_i,
  input  logic [N-1:0]                  a_wdata_i,
  input  logic [$clog2(SRC_DEPTH)-1:0]  a_waddr_i,
  input  logic                          b_we_i,
  input  logic [L-1:0]                  b_wdata_i,
  input  logic [$clog2(SRC_DEPTH)-1:0]  b_waddr_i,
  output logic                          busy_o,
  output logic                          done_o,
  output logic                          error_o,
  output logic [L-1:0]                  data_bottom_o,
  output logic [(N*L)-1:0]              b_regs_flat_o
);

  localparam logic [COUNT_W-1:0] RUN_BASE_CYCLES = COUNT_W'((3 * N) + L - 2);

  logic               run_active_q;
  logic [COUNT_W-1:0] reduce_start_q;
  logic [COUNT_W-1:0] run_cycles_q;
  logic [COUNT_W-1:0] cycle_q;
  logic               reduce_enable_q;
  logic               reduce_pulse_q;
  logic               control_error_q;
  logic               pipeline_busy;
  logic               pipeline_error;
  logic               pipeline_start;

  assign pipeline_start = start_i && !run_active_q;
  assign busy_o         = run_active_q || pipeline_busy;
  assign error_o        = control_error_q || pipeline_error;

  \input #(
    .N               (N),
    .M               (M),
    .L               (L),
    .REDUCE_HOP_DELAY(REDUCE_HOP_DELAY),
    .SRC_DEPTH       (SRC_DEPTH),
    .COUNT_W         (COUNT_W)
  ) u_input_pipeline (
    .clk        (clk),
    .rst        (rst),
    .start_i    (pipeline_start),
    .rows_i     (rows_i),
    .a_base_i   (a_base_i),
    .b_base_i   (b_base_i),
    .reduce_i   (reduce_pulse_q),
    .a_we_i     (a_we_i),
    .a_wdata_i  (a_wdata_i),
    .a_waddr_i  (a_waddr_i),
    .b_we_i     (b_we_i),
    .b_wdata_i  (b_wdata_i),
    .b_waddr_i  (b_waddr_i),
    .busy_o     (pipeline_busy),
    .error_o    (pipeline_error),
    .data_bottom_o(data_bottom_o),
    .b_regs_flat_o(b_regs_flat_o)
  );

  always_ff @(posedge clk) begin
    if (rst) begin
      run_active_q    <= 1'b0;
      reduce_start_q  <= '0;
      run_cycles_q    <= '0;
      cycle_q         <= '0;
      reduce_enable_q <= 1'b0;
      reduce_pulse_q  <= 1'b0;
      control_error_q <= 1'b0;
      done_o          <= 1'b0;
    end else begin
      done_o         <= 1'b0;
      reduce_pulse_q <= 1'b0;

      if (start_i && run_active_q)
        control_error_q <= 1'b1;

      if (!run_active_q && start_i) begin
        reduce_start_q  <= reduce_start_i;
        run_cycles_q    <= (run_cycles_i == '0) ? (RUN_BASE_CYCLES + rows_i) : run_cycles_i;
        cycle_q         <= '0;
        reduce_enable_q <= reduce_enable_i;
        control_error_q <= (rows_i == '0);

        if (rows_i == '0) begin
          run_active_q <= 1'b0;
          done_o       <= 1'b1;
        end else begin
          run_active_q <= 1'b1;
        end
      end else if (run_active_q) begin
        if (reduce_enable_q && (cycle_q == reduce_start_q))
          reduce_pulse_q <= 1'b1;

        if ((cycle_q + 1'b1) >= run_cycles_q) begin
          run_active_q <= 1'b0;
          cycle_q      <= '0;
          done_o       <= 1'b1;
        end else begin
          cycle_q <= cycle_q + 1'b1;
        end
      end
    end
  end

endmodule
