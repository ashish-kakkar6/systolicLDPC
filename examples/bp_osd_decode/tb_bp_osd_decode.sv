`timescale 1ns / 1ps

module tb_bp_osd_decode;
  localparam int M = 24;
  localparam int N = 221;
  localparam int E = 568;
  localparam int ROW_DEG_MAX = 4;
  localparam int N_PAD_MAX = 256;
  localparam int TOP_P_MAX = N_PAD_MAX;
  localparam int LLR_W = 12;
  localparam int MAX_ITER_W = 8;
  localparam int CLOCK_PERIOD_NS = 10;
  localparam int TIMEOUT_CYCLES_DEFAULT = 100000;
  localparam int COUNT_W = 16;

  localparam int VAR_IDX_W = (N <= 1) ? 1 : $clog2(N);
  localparam int EDGE_IDX_W = (E <= 1) ? 1 : $clog2(E);
  localparam int CHK_IDX_W = (M <= 1) ? 1 : $clog2(M);
  localparam int ROW_PTR_DEPTH = M + 1;
  localparam int ROW_PTR_ADDR_W = (ROW_PTR_DEPTH <= 1) ? 1 : $clog2(ROW_PTR_DEPTH);
  localparam int ROW_PTR_W = ((E + 1) <= 1) ? 1 : $clog2(E + 1);
  localparam int SORT_IDX_W = (N_PAD_MAX <= 1) ? 1 : $clog2(N_PAD_MAX);
  localparam int SELECT_W = (M <= 1) ? 1 : $clog2(M + 1);

  logic clk;
  logic rst;
  logic start_i;
  logic [MAX_ITER_W-1:0] max_iter_i;

  logic bp_prior_we_i;
  logic [VAR_IDX_W-1:0] bp_prior_waddr_i;
  logic signed [LLR_W-1:0] bp_prior_wdata_i;
  logic bp_syndrome_we_i;
  logic [CHK_IDX_W-1:0] bp_syndrome_waddr_i;
  logic bp_syndrome_wdata_i;
  logic bp_row_ptr_we_i;
  logic [ROW_PTR_ADDR_W-1:0] bp_row_ptr_waddr_i;
  logic [ROW_PTR_W-1:0] bp_row_ptr_wdata_i;
  logic bp_edge_var_we_i;
  logic [EDGE_IDX_W-1:0] bp_edge_var_waddr_i;
  logic [VAR_IDX_W-1:0] bp_edge_var_wdata_i;

  logic osd_h_we_i;
  logic [CHK_IDX_W-1:0] osd_h_waddr_i;
  logic [N-1:0] osd_h_wdata_i;
  logic osd_sigma_we_i;
  logic [CHK_IDX_W-1:0] osd_sigma_waddr_i;
  logic osd_sigma_wdata_i;

  logic busy_o;
  logic done_o;
  logic error_o;
  logic [MAX_ITER_W-1:0] bp_iter_count_o;
  logic [N-1:0] bp_hard_decision_o;
  logic signed [N*LLR_W-1:0] bp_posterior_llr_flat_o;
  logic [SELECT_W-1:0] selected_count_o;
  logic [SELECT_W-1:0] compacted_rows_o;
  logic [M*SORT_IDX_W-1:0] selected_indices_flat_o;
  logic reduced_write_valid_o;
  logic [$clog2((M < 64) ? 64 : M)-1:0] reduced_write_addr_o;
  logic [M-1:0] reduced_write_row_o;
  logic reduced_write_sigma_o;
  logic [M-1:0] x_hardware_o;
  logic [N-1:0] f_hardware_o;
  logic solver_start_o;
  logic [COUNT_W-1:0] solver_run_cycles_o;
  logic solver_trace_valid_o;
  logic solver_trace_bit_o;

  logic signed [LLR_W-1:0] bp_prior_image [0:N-1];
  logic bp_syndrome_image [0:M-1];
  logic [ROW_PTR_W-1:0] bp_row_ptr_image [0:ROW_PTR_DEPTH-1];
  logic [VAR_IDX_W-1:0] bp_edge_var_image [0:E-1];
  logic [N-1:0] osd_h_image [0:M-1];
  logic osd_sigma_image [0:M-1];

  int elapsed_cycles;
  int timeout_cycles;
  int counts_fd;
  int bp_hard_fd;
  int bp_posterior_fd;
  int estimate_fd;
  int selected_fd;
  int reduced_fd;
  int sigma_fd;
  int x_fd;
  int f_fd;
  bit completed;

  string bp_prior_hex_file;
  string bp_syndrome_mem_file;
  string bp_row_ptr_hex_file;
  string bp_edge_var_hex_file;
  string osd_h_rows_file;
  string osd_sigma_file;
  string bp_hard_out_file;
  string bp_posterior_out_file;
  string estimate_out_file;
  string selected_out_file;
  string reduced_out_file;
  string sigma_out_file;
  string x_out_file;
  string f_out_file;
  string counts_out_file;

  bp_osd_decode_top #(
    .M(M),
    .N(N),
    .E(E),
    .ROW_DEG_MAX(ROW_DEG_MAX),
    .LLR_W(LLR_W),
    .MAX_ITER_W(MAX_ITER_W),
    .N_PAD_MAX(N_PAD_MAX),
    .M_MAX(M),
    .N_MAX(N),
    .TOP_P_MAX(TOP_P_MAX),
    .COUNT_W(COUNT_W)
  ) dut (
    .clk(clk),
    .rst(rst),
    .start_i(start_i),
    .max_iter_i(max_iter_i),
    .bp_prior_we_i(bp_prior_we_i),
    .bp_prior_waddr_i(bp_prior_waddr_i),
    .bp_prior_wdata_i(bp_prior_wdata_i),
    .bp_syndrome_we_i(bp_syndrome_we_i),
    .bp_syndrome_waddr_i(bp_syndrome_waddr_i),
    .bp_syndrome_wdata_i(bp_syndrome_wdata_i),
    .bp_row_ptr_we_i(bp_row_ptr_we_i),
    .bp_row_ptr_waddr_i(bp_row_ptr_waddr_i),
    .bp_row_ptr_wdata_i(bp_row_ptr_wdata_i),
    .bp_edge_var_we_i(bp_edge_var_we_i),
    .bp_edge_var_waddr_i(bp_edge_var_waddr_i),
    .bp_edge_var_wdata_i(bp_edge_var_wdata_i),
    .osd_h_we_i(osd_h_we_i),
    .osd_h_waddr_i(osd_h_waddr_i),
    .osd_h_wdata_i(osd_h_wdata_i),
    .osd_sigma_we_i(osd_sigma_we_i),
    .osd_sigma_waddr_i(osd_sigma_waddr_i),
    .osd_sigma_wdata_i(osd_sigma_wdata_i),
    .busy_o(busy_o),
    .done_o(done_o),
    .error_o(error_o),
    .bp_iter_count_o(bp_iter_count_o),
    .bp_hard_decision_o(bp_hard_decision_o),
    .bp_posterior_llr_flat_o(bp_posterior_llr_flat_o),
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
    rst = 1'b1;
    start_i = 1'b0;
    bp_prior_we_i = 1'b0;
    bp_prior_waddr_i = '0;
    bp_prior_wdata_i = '0;
    bp_syndrome_we_i = 1'b0;
    bp_syndrome_waddr_i = '0;
    bp_syndrome_wdata_i = 1'b0;
    bp_row_ptr_we_i = 1'b0;
    bp_row_ptr_waddr_i = '0;
    bp_row_ptr_wdata_i = '0;
    bp_edge_var_we_i = 1'b0;
    bp_edge_var_waddr_i = '0;
    bp_edge_var_wdata_i = '0;
    osd_h_we_i = 1'b0;
    osd_h_waddr_i = '0;
    osd_h_wdata_i = '0;
    osd_sigma_we_i = 1'b0;
    osd_sigma_waddr_i = '0;
    osd_sigma_wdata_i = 1'b0;
    max_iter_i = 30;
    timeout_cycles = TIMEOUT_CYCLES_DEFAULT;
    elapsed_cycles = 0;
    completed = 1'b0;

    bp_prior_hex_file = "problem/bp_prior_llr.hex";
    bp_syndrome_mem_file = "problem/bp_syndrome.mem";
    bp_row_ptr_hex_file = "problem/bp_row_ptr.hex";
    bp_edge_var_hex_file = "problem/bp_edge_var.hex";
    osd_h_rows_file = "problem/osd_h_rows.mem";
    osd_sigma_file = "problem/osd_sigma.mem";
    bp_hard_out_file = "out/bp_hard_hw.bin";
    bp_posterior_out_file = "out/bp_posterior_hw.hex";
    estimate_out_file = "out/estimate_from_bp_hw.hex";
    selected_out_file = "out/selected_indices_hw.txt";
    reduced_out_file = "out/h_reduced_hw.bin";
    sigma_out_file = "out/sigma_reduced_hw.bin";
    x_out_file = "out/x_hardware.bin";
    f_out_file = "out/F_hardware.bin";
    counts_out_file = "out/counts_hw.txt";

    void'($value$plusargs("BP_PRIOR_HEX=%s", bp_prior_hex_file));
    void'($value$plusargs("BP_SYNDROME_MEM=%s", bp_syndrome_mem_file));
    void'($value$plusargs("BP_ROW_PTR_HEX=%s", bp_row_ptr_hex_file));
    void'($value$plusargs("BP_EDGE_VAR_HEX=%s", bp_edge_var_hex_file));
    void'($value$plusargs("OSD_H_ROWS=%s", osd_h_rows_file));
    void'($value$plusargs("OSD_SIGMA=%s", osd_sigma_file));
    void'($value$plusargs("BP_HARD_OUT=%s", bp_hard_out_file));
    void'($value$plusargs("BP_POSTERIOR_OUT=%s", bp_posterior_out_file));
    void'($value$plusargs("ESTIMATE_OUT=%s", estimate_out_file));
    void'($value$plusargs("SELECTED_OUT=%s", selected_out_file));
    void'($value$plusargs("H_REDUCED_OUT=%s", reduced_out_file));
    void'($value$plusargs("SIGMA_REDUCED_OUT=%s", sigma_out_file));
    void'($value$plusargs("X_HARDWARE_OUT=%s", x_out_file));
    void'($value$plusargs("F_HARDWARE_OUT=%s", f_out_file));
    void'($value$plusargs("COUNTS_OUT=%s", counts_out_file));
    void'($value$plusargs("MAX_ITER=%d", max_iter_i));
    void'($value$plusargs("TIMEOUT_CYCLES=%d", timeout_cycles));

    for (int idx = 0; idx < N; idx++)
      bp_prior_image[idx] = '0;
    for (int idx = 0; idx < M; idx++) begin
      bp_syndrome_image[idx] = 1'b0;
      osd_h_image[idx] = '0;
      osd_sigma_image[idx] = 1'b0;
    end
    for (int idx = 0; idx < ROW_PTR_DEPTH; idx++)
      bp_row_ptr_image[idx] = '0;
    for (int idx = 0; idx < E; idx++)
      bp_edge_var_image[idx] = '0;

    $readmemh(bp_prior_hex_file, bp_prior_image, 0, N - 1);
    $readmemb(bp_syndrome_mem_file, bp_syndrome_image, 0, M - 1);
    $readmemh(bp_row_ptr_hex_file, bp_row_ptr_image, 0, ROW_PTR_DEPTH - 1);
    $readmemh(bp_edge_var_hex_file, bp_edge_var_image, 0, E - 1);
    $readmemb(osd_h_rows_file, osd_h_image, 0, M - 1);
    $readmemb(osd_sigma_file, osd_sigma_image, 0, M - 1);

    reduced_fd = $fopen(reduced_out_file, "w");
    sigma_fd = $fopen(sigma_out_file, "w");
    counts_fd = $fopen(counts_out_file, "w");
    if ((reduced_fd == 0) || (sigma_fd == 0) || (counts_fd == 0))
      $fatal(1, "tb_bp_osd_decode: failed to open output files");

    repeat (2) @(posedge clk);
    rst = 1'b0;

    for (int idx = 0; idx < N; idx++) begin
      @(negedge clk);
      bp_prior_we_i = 1'b1;
      bp_prior_waddr_i = idx[VAR_IDX_W-1:0];
      bp_prior_wdata_i = bp_prior_image[idx];
      @(posedge clk);
    end
    @(negedge clk);
    bp_prior_we_i = 1'b0;

    for (int idx = 0; idx < M; idx++) begin
      @(negedge clk);
      bp_syndrome_we_i = 1'b1;
      bp_syndrome_waddr_i = idx[CHK_IDX_W-1:0];
      bp_syndrome_wdata_i = bp_syndrome_image[idx];
      @(posedge clk);
    end
    @(negedge clk);
    bp_syndrome_we_i = 1'b0;

    for (int idx = 0; idx < ROW_PTR_DEPTH; idx++) begin
      @(negedge clk);
      bp_row_ptr_we_i = 1'b1;
      bp_row_ptr_waddr_i = idx[ROW_PTR_ADDR_W-1:0];
      bp_row_ptr_wdata_i = bp_row_ptr_image[idx];
      @(posedge clk);
    end
    @(negedge clk);
    bp_row_ptr_we_i = 1'b0;

    for (int idx = 0; idx < E; idx++) begin
      @(negedge clk);
      bp_edge_var_we_i = 1'b1;
      bp_edge_var_waddr_i = idx[EDGE_IDX_W-1:0];
      bp_edge_var_wdata_i = bp_edge_var_image[idx];
      @(posedge clk);
    end
    @(negedge clk);
    bp_edge_var_we_i = 1'b0;

    for (int idx = 0; idx < M; idx++) begin
      @(negedge clk);
      osd_h_we_i = 1'b1;
      osd_h_waddr_i = idx[CHK_IDX_W-1:0];
      osd_h_wdata_i = osd_h_image[idx];
      @(posedge clk);
    end
    @(negedge clk);
    osd_h_we_i = 1'b0;

    for (int idx = 0; idx < M; idx++) begin
      @(negedge clk);
      osd_sigma_we_i = 1'b1;
      osd_sigma_waddr_i = idx[CHK_IDX_W-1:0];
      osd_sigma_wdata_i = osd_sigma_image[idx];
      @(posedge clk);
    end
    @(negedge clk);
    osd_sigma_we_i = 1'b0;

    @(negedge clk);
    start_i = 1'b1;
    @(posedge clk);
    elapsed_cycles = 1;
    @(negedge clk);
    start_i = 1'b0;

    for (int cycle = 0; cycle < timeout_cycles; cycle++) begin
      @(posedge clk);

      if (reduced_write_valid_o) begin
        for (int bit_idx = 0; bit_idx < M; bit_idx++)
          $fwrite(reduced_fd, "%0d", reduced_write_row_o[bit_idx]);
        $fwrite(reduced_fd, "\n");
      end
      if (reduced_write_valid_o)
        $fwrite(sigma_fd, "%0d\n", reduced_write_sigma_o);

      if (done_o) begin
        bp_hard_fd = $fopen(bp_hard_out_file, "w");
        bp_posterior_fd = $fopen(bp_posterior_out_file, "w");
        estimate_fd = $fopen(estimate_out_file, "w");
        selected_fd = $fopen(selected_out_file, "w");
        x_fd = $fopen(x_out_file, "w");
        f_fd = $fopen(f_out_file, "w");
        if ((bp_hard_fd == 0) || (bp_posterior_fd == 0) || (estimate_fd == 0) ||
            (selected_fd == 0) || (x_fd == 0) || (f_fd == 0))
          $fatal(1, "tb_bp_osd_decode: failed to open completion output files");

        for (int idx = 0; idx < N; idx++)
          $fwrite(bp_hard_fd, "%0d\n", bp_hard_decision_o[idx]);
        for (int idx = 0; idx < N; idx++)
          $fwrite(bp_posterior_fd, "%03x\n", bp_posterior_llr_flat_o[(idx * LLR_W) +: LLR_W]);
        for (int idx = 0; idx < N_PAD_MAX; idx++)
          $fwrite(estimate_fd, "%0d\n", dut.u_osd.u_store.estimate_mem[idx][3:0]);
        for (int idx = 0; idx < selected_count_o; idx++)
          $fwrite(selected_fd, "%0d\n", selected_indices_flat_o[(idx * SORT_IDX_W) +: SORT_IDX_W]);
        for (int idx = 0; idx < selected_count_o; idx++)
          $fwrite(x_fd, "%0d", x_hardware_o[idx]);
        $fwrite(x_fd, "\n");
        for (int idx = 0; idx < N; idx++)
          $fwrite(f_fd, "%0d", f_hardware_o[idx]);
        $fwrite(f_fd, "\n");

        $fwrite(counts_fd, "elapsed_cycles=%0d\n", elapsed_cycles);
        $fwrite(counts_fd, "bp_iter_count=%0d\n", bp_iter_count_o);
        $fwrite(counts_fd, "selected_count=%0d\n", selected_count_o);
        $fwrite(counts_fd, "compacted_rows=%0d\n", compacted_rows_o);
        $fwrite(counts_fd, "solver_run_cycles=%0d\n", solver_run_cycles_o);
        $fwrite(counts_fd, "solver_start=%0d\n", solver_start_o);
        $fwrite(counts_fd, "error=%0d\n", error_o);

        $fclose(bp_hard_fd);
        $fclose(bp_posterior_fd);
        $fclose(estimate_fd);
        $fclose(selected_fd);
        $fclose(x_fd);
        $fclose(f_fd);
        $fclose(reduced_fd);
        $fclose(sigma_fd);
        $fclose(counts_fd);
        completed = 1'b1;
        break;
      end

      if (error_o) begin
        $fwrite(counts_fd, "elapsed_cycles=%0d\n", elapsed_cycles);
        $fwrite(counts_fd, "bp_iter_count=%0d\n", bp_iter_count_o);
        $fwrite(counts_fd, "selected_count=%0d\n", selected_count_o);
        $fwrite(counts_fd, "compacted_rows=%0d\n", compacted_rows_o);
        $fwrite(counts_fd, "solver_run_cycles=%0d\n", solver_run_cycles_o);
        $fwrite(counts_fd, "solver_start=%0d\n", solver_start_o);
        $fwrite(counts_fd, "error=%0d\n", error_o);
        $fclose(reduced_fd);
        $fclose(sigma_fd);
        $fclose(counts_fd);
        $fatal(1, "bp_osd_decode: error_o asserted after %0d cycles", elapsed_cycles);
      end

      elapsed_cycles = elapsed_cycles + 1;
    end

    if (completed) begin
      $finish;
    end else begin
      $fwrite(counts_fd, "elapsed_cycles=%0d\n", timeout_cycles);
      $fwrite(counts_fd, "error=%0d\n", error_o);
      $fclose(reduced_fd);
      $fclose(sigma_fd);
      $fclose(counts_fd);
      $fatal(1, "bp_osd_decode: timeout after %0d cycles", timeout_cycles);
    end
  end
endmodule
