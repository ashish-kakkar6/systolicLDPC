`timescale 1ns / 1ps

module tb_osd_decode;
  localparam int M_MAX = 24;
  localparam int N_MAX = 221;
  localparam int N_PAD_MAX = 256;
  localparam int TOP_P_MAX = ((3 * M_MAX) < N_PAD_MAX) ? (3 * M_MAX) : N_PAD_MAX;
  localparam int COUNT_W = 16;
  localparam int SORT_IDX_W = (N_PAD_MAX <= 1) ? 1 : $clog2(N_PAD_MAX);
  localparam int SELECT_W = (M_MAX <= 1) ? 1 : $clog2(M_MAX + 1);
  localparam int SOLVER_SRC_DEPTH = (M_MAX < 64) ? 64 : M_MAX;
  localparam int SOLVER_ADDR_W = $clog2(SOLVER_SRC_DEPTH);
  localparam int CLOCK_PERIOD_NS = 10;
  localparam int TIMEOUT_CYCLES_DEFAULT = N_PAD_MAX + (10 * M_MAX) + 128;

  logic clk;
  logic rst;
  logic start_i;
  logic h_we_i;
  logic [$clog2(M_MAX)-1:0] h_waddr_i;
  logic [N_MAX-1:0] h_wdata_i;
  logic sigma_we_i;
  logic [$clog2(M_MAX)-1:0] sigma_waddr_i;
  logic sigma_wdata_i;
  logic estimate_we_i;
  logic [$clog2(N_PAD_MAX)-1:0] estimate_waddr_i;
  logic [31:0] estimate_wdata_i;
  logic cutoff_we_i;
  logic [31:0] cutoff_wdata_i;
  logic busy_o;
  logic done_o;
  logic error_o;
  logic [SELECT_W-1:0] selected_count_o;
  logic [SELECT_W-1:0] compacted_rows_o;
  logic [(M_MAX * SORT_IDX_W)-1:0] selected_indices_flat_o;
  logic reduced_write_valid_o;
  logic [SOLVER_ADDR_W-1:0] reduced_write_addr_o;
  logic [M_MAX-1:0] reduced_write_row_o;
  logic reduced_write_sigma_o;
  logic [M_MAX-1:0] x_hardware_o;
  logic [N_MAX-1:0] f_hardware_o;
  logic solver_start_o;
  logic [COUNT_W-1:0] solver_run_cycles_o;
  logic solver_trace_valid_o;
  logic solver_trace_bit_o;

  int elapsed_cycles;
  int timeout_cycles;
  int selected_fd;
  int reduced_fd;
  int sigma_fd;
  int trace_fd;
  int counts_fd;
  int x_fd;
  int f_fd;
  int solver_trace_delay;
  int solver_trace_remaining;
  bit completed;
  bit save_trace;

  string h_rows_file;
  string sigma_file;
  string estimate_file;
  string cutoff_file;
  string selected_out_file;
  string reduced_out_file;
  string sigma_out_file;
  string trace_out_file;
  string counts_out_file;
  string x_out_file;
  string f_out_file;

  osd_control_top #(
    .M_MAX(M_MAX),
    .N_MAX(N_MAX),
    .N_PAD_MAX(N_PAD_MAX),
    .TOP_P_MAX(TOP_P_MAX),
    .COUNT_W(COUNT_W)
  ) dut (
    .clk(clk),
    .rst(rst),
    .start_i(start_i),
    .h_we_i(h_we_i),
    .h_waddr_i(h_waddr_i),
    .h_wdata_i(h_wdata_i),
    .sigma_we_i(sigma_we_i),
    .sigma_waddr_i(sigma_waddr_i),
    .sigma_wdata_i(sigma_wdata_i),
    .estimate_we_i(estimate_we_i),
    .estimate_waddr_i(estimate_waddr_i),
    .estimate_wdata_i(estimate_wdata_i),
    .cutoff_we_i(cutoff_we_i),
    .cutoff_wdata_i(cutoff_wdata_i),
    .busy_o(busy_o),
    .done_o(done_o),
    .error_o(error_o),
    .selected_count_o(selected_count_o),
    .compacted_rows_o(compacted_rows_o),
    .selected_indices_flat_o(selected_indices_flat_o),
    .reduced_write_valid_o(reduced_write_valid_o),
    .reduced_write_addr_o(reduced_write_addr_o),
    .reduced_write_row_o(reduced_write_row_o),
    .reduced_write_sigma_o(reduced_write_sigma_o),
    .x_hardware_o(x_hardware_o),
    .f_hardware_o(f_hardware_o),
    .solver_start_o(solver_start_o),
    .solver_run_cycles_o(solver_run_cycles_o),
    .solver_trace_valid_o(solver_trace_valid_o),
    .solver_trace_bit_o(solver_trace_bit_o)
  );

  initial begin
    clk = 1'b0;
    forever #(CLOCK_PERIOD_NS / 2) clk = ~clk;
  end

  initial begin
    start_i = 1'b0;
    rst = 1'b1;
    h_we_i = 1'b0;
    h_waddr_i = '0;
    h_wdata_i = '0;
    sigma_we_i = 1'b0;
    sigma_waddr_i = '0;
    sigma_wdata_i = 1'b0;
    estimate_we_i = 1'b0;
    estimate_waddr_i = '0;
    estimate_wdata_i = '0;
    cutoff_we_i = 1'b0;
    cutoff_wdata_i = '0;
    elapsed_cycles = 0;
    timeout_cycles = TIMEOUT_CYCLES_DEFAULT;

    h_rows_file = "problem/h_rows.mem";
    sigma_file = "problem/sigma.mem";
    estimate_file = "problem/estimate.hex";
    cutoff_file = "problem/cutoff.hex";
    selected_out_file = "out/selected_indices_hw.txt";
    reduced_out_file = "out/h_reduced_hw.bin";
    sigma_out_file = "out/sigma_reduced_hw.bin";
    trace_out_file = "";
    counts_out_file = "out/counts_hw.txt";
    x_out_file = "out/x_hardware.bin";
    f_out_file = "out/F_hardware.bin";

    void'($value$plusargs("H_ROWS=%s", h_rows_file));
    void'($value$plusargs("SIGMA=%s", sigma_file));
    void'($value$plusargs("ESTIMATE=%s", estimate_file));
    void'($value$plusargs("CUTOFF=%s", cutoff_file));
    void'($value$plusargs("SELECTED_OUT=%s", selected_out_file));
    void'($value$plusargs("H_REDUCED_OUT=%s", reduced_out_file));
    void'($value$plusargs("SIGMA_REDUCED_OUT=%s", sigma_out_file));
    save_trace = $value$plusargs("X_TRACE_OUT=%s", trace_out_file);
    void'($value$plusargs("COUNTS_OUT=%s", counts_out_file));
    void'($value$plusargs("X_HARDWARE_OUT=%s", x_out_file));
    void'($value$plusargs("F_HARDWARE_OUT=%s", f_out_file));
    void'($value$plusargs("TIMEOUT_CYCLES=%d", timeout_cycles));

    for (int row = 0; row < M_MAX; row++) begin
      dut.u_store.h_row_mem[row] = '0;
      dut.u_store.sigma_mem[row] = 1'b0;
    end
    for (int idx = 0; idx < N_PAD_MAX; idx++) begin
      dut.u_store.estimate_mem[idx] = '0;
    end
    dut.u_store.cutoff_mem[0] = '0;

    $readmemb(h_rows_file, dut.u_store.h_row_mem, 0, M_MAX - 1);
    $readmemb(sigma_file, dut.u_store.sigma_mem, 0, M_MAX - 1);
    $readmemh(estimate_file, dut.u_store.estimate_mem, 0, N_PAD_MAX - 1);
    $readmemh(cutoff_file, dut.u_store.cutoff_mem, 0, 0);

    reduced_fd = $fopen(reduced_out_file, "w");
    sigma_fd = $fopen(sigma_out_file, "w");
    if (save_trace)
      trace_fd = $fopen(trace_out_file, "w");
    else
      trace_fd = 0;
    counts_fd = $fopen(counts_out_file, "w");
    if ((reduced_fd == 0) || (sigma_fd == 0) || (counts_fd == 0) || (save_trace && (trace_fd == 0)))
      $fatal(1, "tb_osd_decode: failed to open output files");

    repeat (2) @(posedge clk);
    rst = 1'b0;

    @(negedge clk);
    start_i = 1'b1;

    @(posedge clk);
    elapsed_cycles = 1;

    @(negedge clk);
    start_i = 1'b0;

    solver_trace_delay = 0;
    solver_trace_remaining = 0;
    completed = 1'b0;

    for (int cycle = 0; cycle < timeout_cycles; cycle++) begin
      @(posedge clk);

      if (reduced_write_valid_o) begin
        for (int bit_idx = 0; bit_idx < M_MAX; bit_idx++)
          $fwrite(reduced_fd, "%0d", reduced_write_row_o[bit_idx]);
        $fwrite(reduced_fd, "\n");
        $fwrite(sigma_fd, "%0d\n", reduced_write_sigma_o);
      end

      if (solver_start_o) begin
        solver_trace_delay = 1;
        solver_trace_remaining = int'(solver_run_cycles_o) + 1;
      end

      if (solver_trace_delay > 0) begin
        solver_trace_delay = solver_trace_delay - 1;
      end else if (save_trace && (solver_trace_remaining > 0)) begin
        $fwrite(trace_fd, "%0d\n", solver_trace_bit_o);
        solver_trace_remaining = solver_trace_remaining - 1;
      end

      if (done_o) begin
        selected_fd = $fopen(selected_out_file, "w");
        if (selected_fd == 0)
          $fatal(1, "tb_osd_decode: failed to open %s", selected_out_file);

        for (int idx = 0; idx < selected_count_o; idx++)
          $fwrite(selected_fd, "%0d\n", selected_indices_flat_o[(idx * SORT_IDX_W) +: SORT_IDX_W]);

        $fclose(selected_fd);
        x_fd = $fopen(x_out_file, "w");
        f_fd = $fopen(f_out_file, "w");
        if ((x_fd == 0) || (f_fd == 0))
          $fatal(1, "tb_osd_decode: failed to open hardware result files");
        for (int idx = 0; idx < selected_count_o; idx++)
          $fwrite(x_fd, "%0d", x_hardware_o[idx]);
        $fwrite(x_fd, "\n");
        for (int idx = 0; idx < N_MAX; idx++)
          $fwrite(f_fd, "%0d", f_hardware_o[idx]);
        $fwrite(f_fd, "\n");
        $fclose(x_fd);
        $fclose(f_fd);
        $fwrite(counts_fd, "selected_count=%0d\n", selected_count_o);
        $fwrite(counts_fd, "compacted_rows=%0d\n", compacted_rows_o);
        $fwrite(counts_fd, "elapsed_cycles=%0d\n", elapsed_cycles);
        $fwrite(counts_fd, "timeout_cycles=%0d\n", timeout_cycles);
        $fwrite(counts_fd, "solver_run_cycles=%0d\n", solver_run_cycles_o);
        $fclose(reduced_fd);
        $fclose(sigma_fd);
        if (save_trace)
          $fclose(trace_fd);
        $fclose(counts_fd);
        $display("osd_decode: completed in %0d cycles", elapsed_cycles);
        completed = 1'b1;
        break;
      end

      if (error_o) begin
        selected_fd = $fopen(selected_out_file, "w");
        if (selected_fd != 0) begin
          for (int idx = 0; idx < selected_count_o; idx++)
            $fwrite(selected_fd, "%0d\n", selected_indices_flat_o[(idx * SORT_IDX_W) +: SORT_IDX_W]);
          $fclose(selected_fd);
        end
        $fwrite(counts_fd, "selected_count=%0d\n", selected_count_o);
        $fwrite(counts_fd, "compacted_rows=%0d\n", compacted_rows_o);
        $fwrite(counts_fd, "elapsed_cycles=%0d\n", elapsed_cycles);
        $fwrite(counts_fd, "timeout_cycles=%0d\n", timeout_cycles);
        $fwrite(counts_fd, "solver_run_cycles=%0d\n", solver_run_cycles_o);
        $fclose(reduced_fd);
        $fclose(sigma_fd);
        if (save_trace)
          $fclose(trace_fd);
        $fclose(counts_fd);
        $fatal(1, "osd_decode: error_o asserted after %0d cycles", elapsed_cycles);
      end

      elapsed_cycles++;
    end

    if (completed) begin
      $finish;
    end else begin
      $fclose(reduced_fd);
      $fclose(sigma_fd);
      if (save_trace)
        $fclose(trace_fd);
      $fwrite(counts_fd, "elapsed_cycles=%0d\n", timeout_cycles);
      $fwrite(counts_fd, "timeout_cycles=%0d\n", timeout_cycles);
      $fwrite(counts_fd, "solver_run_cycles=%0d\n", solver_run_cycles_o);
      $fclose(counts_fd);
      $fatal(1, "osd_decode: timed out after %0d cycles", timeout_cycles);
    end
  end

endmodule
