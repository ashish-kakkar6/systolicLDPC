`timescale 1ns / 1ps

module tb_example_gauss_jordan;
    localparam int N = 4;
    localparam int M = 4;
    localparam int L = 2;
    localparam int REDUCE_HOP_DELAY = 3;
  localparam int REDUCE_START_CYCLE = M;
    localparam int SRC_DEPTH = 64;
  localparam int COUNT_W = 16;
  localparam int CLOCK_PERIOD_NS = 10;
  localparam int RUN_CYCLES_DEFAULT = (3 * N) + M + L - 1;
  localparam int TIMEOUT_CYCLES_DEFAULT = RUN_CYCLES_DEFAULT + 32;

  logic clk;
  logic rst;
  logic start_i;
  logic reduce_enable_i;
  logic [COUNT_W-1:0] rows_i;
  logic [COUNT_W-1:0] reduce_start_i;
  logic [COUNT_W-1:0] run_cycles_i;
  logic [$clog2(SRC_DEPTH)-1:0] a_base_i;
  logic [$clog2(SRC_DEPTH)-1:0] b_base_i;
  logic a_we_i;
  logic [N-1:0] a_wdata_i;
  logic [$clog2(SRC_DEPTH)-1:0] a_waddr_i;
  logic b_we_i;
  logic [L-1:0] b_wdata_i;
  logic [$clog2(SRC_DEPTH)-1:0] b_waddr_i;
  logic busy_o;
  logic done_o;
  logic error_o;
  logic [L-1:0] data_bottom_o;

  int elapsed_cycles;
  int timeout_cycles;
  int waves_en;
  int bottom_fd;
  int counts_fd;

  string a_bin_file;
  string b_bin_file;
  string bottom_bin_file;
  string wave_file;
  string counts_out_file;

  controller #(
    .N               (N),
    .M               (M),
    .L               (L),
    .REDUCE_HOP_DELAY(REDUCE_HOP_DELAY),
    .SRC_DEPTH       (SRC_DEPTH),
    .COUNT_W         (COUNT_W)
  ) dut (
    .clk          (clk),
    .rst          (rst),
    .start_i      (start_i),
    .reduce_enable_i(reduce_enable_i),
    .rows_i       (rows_i),
    .reduce_start_i(reduce_start_i),
    .run_cycles_i (run_cycles_i),
    .a_base_i     (a_base_i),
    .b_base_i     (b_base_i),
    .a_we_i       (a_we_i),
    .a_wdata_i    (a_wdata_i),
    .a_waddr_i    (a_waddr_i),
    .b_we_i       (b_we_i),
    .b_wdata_i    (b_wdata_i),
    .b_waddr_i    (b_waddr_i),
    .busy_o       (busy_o),
    .done_o       (done_o),
    .error_o      (error_o),
    .data_bottom_o(data_bottom_o)
  );

  initial begin
    clk = 1'b0;
    forever #(CLOCK_PERIOD_NS / 2) clk = ~clk;
  end

  initial begin
    rows_i = COUNT_W'(M);
    reduce_start_i = COUNT_W'(REDUCE_START_CYCLE);
    run_cycles_i = COUNT_W'(RUN_CYCLES_DEFAULT);
    reduce_enable_i = 1'b1;
    a_base_i = '0;
    b_base_i = '0;
    start_i = 1'b0;
    a_we_i = 1'b0;
    a_wdata_i = '0;
    a_waddr_i = '0;
    b_we_i = 1'b0;
    b_wdata_i = '0;
    b_waddr_i = '0;
    rst = 1'b1;
    elapsed_cycles = 0;
    timeout_cycles = TIMEOUT_CYCLES_DEFAULT;
    waves_en = 0;

    a_bin_file = "data/a_rows.bin";
    b_bin_file = "data/b_rows.bin";
    bottom_bin_file = "out/data_bottom_trace.bin";
    wave_file = "out/tb_example_gauss_jordan.fst";
    counts_out_file = "out/solver_counts.txt";

    void'($value$plusargs("A_BIN=%s", a_bin_file));
    void'($value$plusargs("B_BIN=%s", b_bin_file));
    void'($value$plusargs("BOTTOM_BIN=%s", bottom_bin_file));
    void'($value$plusargs("COUNTS_OUT=%s", counts_out_file));
    void'($value$plusargs("TIMEOUT_CYCLES=%d", timeout_cycles));
    void'($value$plusargs("WAVES=%d", waves_en));
    void'($value$plusargs("WAVE_FILE=%s", wave_file));
    void'($value$plusargs("REDUCE_ENABLE=%d", reduce_enable_i));
    void'($value$plusargs("REDUCE_START=%d", reduce_start_i));
    void'($value$plusargs("RUN_CYCLES=%d", run_cycles_i));

    if (waves_en != 0) begin
      $dumpfile(wave_file);
      $dumpvars(0, tb_example_gauss_jordan);
    end

    for (int idx = 0; idx < SRC_DEPTH; idx++) begin
      dut.u_input_pipeline.u_a_mem.mem[idx] = '0;
      dut.u_input_pipeline.u_b_mem.mem[idx] = '0;
    end

    $readmemb(a_bin_file, dut.u_input_pipeline.u_a_mem.mem, 0, M - 1);
    $readmemb(b_bin_file, dut.u_input_pipeline.u_b_mem.mem, 0, M - 1);

    $display("gauss_jordan_solve: A=%s B=%s", a_bin_file, b_bin_file);
    $display("gauss_jordan_solve: rows=%0d N=%0d L=%0d", M, N, L);
    $display(
      "gauss_jordan_solve: reduce_enable=%0d reduce_start=%0d reduce_hop_delay=%0d run_cycles=%0d",
      reduce_enable_i, reduce_start_i, REDUCE_HOP_DELAY, run_cycles_i
    );

    bottom_fd = $fopen(bottom_bin_file, "w");
    if (bottom_fd == 0)
      $fatal(1, "gauss_jordan_solve: failed to open %s", bottom_bin_file);
    counts_fd = $fopen(counts_out_file, "w");
    if (counts_fd == 0)
      $fatal(1, "gauss_jordan_solve: failed to open %s", counts_out_file);

    repeat (2) @(posedge clk);
    rst <= 1'b0;

    @(negedge clk);
    start_i <= 1'b1;

    @(posedge clk);
    elapsed_cycles = 1;

    @(negedge clk);
    start_i <= 1'b0;

    for (int cycle = 0; cycle < timeout_cycles; cycle++) begin
      @(posedge clk);

      for (int bit_idx = L - 1; bit_idx >= 0; bit_idx--)
        $fwrite(bottom_fd, "%0d", data_bottom_o[bit_idx]);
      $fwrite(bottom_fd, "\n");

      if (done_o) begin
        $fclose(bottom_fd);
        $fwrite(counts_fd, "elapsed_cycles=%0d\n", elapsed_cycles);
        $fwrite(counts_fd, "timeout_cycles=%0d\n", timeout_cycles);
        $fwrite(counts_fd, "configured_run_cycles=%0d\n", run_cycles_i);
        $fclose(counts_fd);
        $display("gauss_jordan_solve: completed in %0d cycles", elapsed_cycles);
        $finish;
      end

      if (error_o) begin
        $fclose(bottom_fd);
        $fwrite(counts_fd, "elapsed_cycles=%0d\n", elapsed_cycles);
        $fwrite(counts_fd, "timeout_cycles=%0d\n", timeout_cycles);
        $fwrite(counts_fd, "configured_run_cycles=%0d\n", run_cycles_i);
        $fclose(counts_fd);
        $fatal(1, "gauss_jordan_solve: error_o asserted after %0d cycles", elapsed_cycles);
      end

      elapsed_cycles++;
    end

    $fclose(bottom_fd);
    $fwrite(counts_fd, "elapsed_cycles=%0d\n", timeout_cycles);
    $fwrite(counts_fd, "timeout_cycles=%0d\n", timeout_cycles);
    $fwrite(counts_fd, "configured_run_cycles=%0d\n", run_cycles_i);
    $fclose(counts_fd);
    $fatal(1, "gauss_jordan_solve: timed out after %0d cycles", timeout_cycles);
  end

endmodule
