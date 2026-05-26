`timescale 1ns / 1ps

module tb_minsum_decode;
  localparam int M = 3;
  localparam int N = 6;
  localparam int E = 9;
  localparam int ROW_DEG_MAX = 3;
  localparam int ROW_PTR_DEPTH = M + 1;
  localparam int LLR_W = 12;
  localparam int MAX_ITER_W = 8;
  localparam int CLOCK_PERIOD_NS = 10;
  localparam int TIMEOUT_CYCLES_DEFAULT = 128;

  localparam int VAR_IDX_W = (N <= 1) ? 1 : $clog2(N);
  localparam int EDGE_IDX_W = (E <= 1) ? 1 : $clog2(E);
  localparam int CHK_IDX_W = (M <= 1) ? 1 : $clog2(M);
  localparam int ROW_PTR_ADDR_W = (ROW_PTR_DEPTH <= 1) ? 1 : $clog2(ROW_PTR_DEPTH);
  localparam int ROW_PTR_W = ((E + 1) <= 1) ? 1 : $clog2(E + 1);

  logic clk;
  logic rst;
  logic start_i;
  logic result_mode_i;
  logic [MAX_ITER_W-1:0] max_iter_i;
  logic prior_we_i;
  logic [VAR_IDX_W-1:0] prior_waddr_i;
  logic signed [LLR_W-1:0] prior_wdata_i;
  logic syndrome_we_i;
  logic [CHK_IDX_W-1:0] syndrome_waddr_i;
  logic syndrome_wdata_i;
  logic row_ptr_we_i;
  logic [ROW_PTR_ADDR_W-1:0] row_ptr_waddr_i;
  logic [ROW_PTR_W-1:0] row_ptr_wdata_i;
  logic edge_var_we_i;
  logic [EDGE_IDX_W-1:0] edge_var_waddr_i;
  logic [VAR_IDX_W-1:0] edge_var_wdata_i;
  logic busy_o;
  logic done_o;
  logic error_o;
  logic [MAX_ITER_W-1:0] iter_count_o;
  logic [N-1:0] hard_decision_o;
  logic [(N * LLR_W)-1:0] posterior_llr_flat_o;

  logic signed [LLR_W-1:0] prior_image [0:N-1];
  logic syndrome_image [0:M-1];
  logic [ROW_PTR_W-1:0] row_ptr_image [0:ROW_PTR_DEPTH-1];
  logic [VAR_IDX_W-1:0] edge_var_image [0:E-1];

  int elapsed_cycles;
  int timeout_cycles;
  int counts_fd;
  int hard_fd;
  int posterior_fd;

  string prior_hex_file;
  string syndrome_mem_file;
  string row_ptr_hex_file;
  string edge_var_hex_file;
  string counts_out_file;
  string hard_out_file;
  string posterior_out_file;
  int result_mode_raw;

  minsum_decode_top #(
    .M(M),
    .N(N),
    .E(E),
    .ROW_DEG_MAX(ROW_DEG_MAX),
    .LLR_W(LLR_W),
    .MAX_ITER_W(MAX_ITER_W)
  ) dut (
    .clk(clk),
    .rst(rst),
    .start_i(start_i),
    .result_mode_i(result_mode_i),
    .max_iter_i(max_iter_i),
    .prior_we_i(prior_we_i),
    .prior_waddr_i(prior_waddr_i),
    .prior_wdata_i(prior_wdata_i),
    .syndrome_we_i(syndrome_we_i),
    .syndrome_waddr_i(syndrome_waddr_i),
    .syndrome_wdata_i(syndrome_wdata_i),
    .row_ptr_we_i(row_ptr_we_i),
    .row_ptr_waddr_i(row_ptr_waddr_i),
    .row_ptr_wdata_i(row_ptr_wdata_i),
    .edge_var_we_i(edge_var_we_i),
    .edge_var_waddr_i(edge_var_waddr_i),
    .edge_var_wdata_i(edge_var_wdata_i),
    .busy_o(busy_o),
    .done_o(done_o),
    .error_o(error_o),
    .iter_count_o(iter_count_o),
    .hard_decision_o(hard_decision_o),
    .posterior_llr_flat_o(posterior_llr_flat_o)
  );

  initial begin
    clk = 1'b0;
    forever #(CLOCK_PERIOD_NS / 2) clk = ~clk;
  end

  initial begin
    rst = 1'b1;
    start_i = 1'b0;
    prior_we_i = 1'b0;
    prior_waddr_i = '0;
    prior_wdata_i = '0;
    syndrome_we_i = 1'b0;
    syndrome_waddr_i = '0;
    syndrome_wdata_i = 1'b0;
    row_ptr_we_i = 1'b0;
    row_ptr_waddr_i = '0;
    row_ptr_wdata_i = '0;
    edge_var_we_i = 1'b0;
    edge_var_waddr_i = '0;
    edge_var_wdata_i = '0;
    max_iter_i = 1;
    result_mode_i = 1'b0;
    result_mode_raw = 0;
    timeout_cycles = TIMEOUT_CYCLES_DEFAULT;
    elapsed_cycles = 0;

    prior_hex_file = "problem/prior_llr.hex";
    syndrome_mem_file = "problem/syndrome.mem";
    row_ptr_hex_file = "problem/row_ptr.hex";
    edge_var_hex_file = "problem/edge_var.hex";
    counts_out_file = "out/counts_hw.txt";
    hard_out_file = "out/hard_decision_hw.bin";
    posterior_out_file = "out/posterior_llr_hw.hex";

    void'($value$plusargs("PRIOR_HEX=%s", prior_hex_file));
    void'($value$plusargs("SYNDROME_MEM=%s", syndrome_mem_file));
    void'($value$plusargs("ROW_PTR_HEX=%s", row_ptr_hex_file));
    void'($value$plusargs("EDGE_VAR_HEX=%s", edge_var_hex_file));
    void'($value$plusargs("COUNTS_OUT=%s", counts_out_file));
    void'($value$plusargs("HARD_OUT=%s", hard_out_file));
    void'($value$plusargs("POSTERIOR_OUT=%s", posterior_out_file));
    void'($value$plusargs("MAX_ITER=%d", max_iter_i));
    void'($value$plusargs("TIMEOUT_CYCLES=%d", timeout_cycles));
    void'($value$plusargs("RESULT_MODE=%d", result_mode_raw));
    result_mode_i = (result_mode_raw != 0);

    for (int idx = 0; idx < N; idx++)
      prior_image[idx] = '0;
    for (int idx = 0; idx < M; idx++)
      syndrome_image[idx] = 1'b0;
    for (int idx = 0; idx < ROW_PTR_DEPTH; idx++)
      row_ptr_image[idx] = '0;
    for (int idx = 0; idx < E; idx++)
      edge_var_image[idx] = '0;

    $readmemh(prior_hex_file, prior_image, 0, N - 1);
    $readmemb(syndrome_mem_file, syndrome_image, 0, M - 1);
    $readmemh(row_ptr_hex_file, row_ptr_image, 0, ROW_PTR_DEPTH - 1);
    $readmemh(edge_var_hex_file, edge_var_image, 0, E - 1);

    repeat (2) @(posedge clk);
    rst = 1'b0;

    for (int idx = 0; idx < N; idx++) begin
      @(negedge clk);
      prior_we_i = 1'b1;
      prior_waddr_i = idx[VAR_IDX_W-1:0];
      prior_wdata_i = prior_image[idx];
      @(posedge clk);
    end
    @(negedge clk);
    prior_we_i = 1'b0;

    for (int idx = 0; idx < M; idx++) begin
      @(negedge clk);
      syndrome_we_i = 1'b1;
      syndrome_waddr_i = idx[CHK_IDX_W-1:0];
      syndrome_wdata_i = syndrome_image[idx];
      @(posedge clk);
    end
    @(negedge clk);
    syndrome_we_i = 1'b0;

    for (int idx = 0; idx < ROW_PTR_DEPTH; idx++) begin
      @(negedge clk);
      row_ptr_we_i = 1'b1;
      row_ptr_waddr_i = idx[ROW_PTR_ADDR_W-1:0];
      row_ptr_wdata_i = row_ptr_image[idx];
      @(posedge clk);
    end
    @(negedge clk);
    row_ptr_we_i = 1'b0;

    for (int idx = 0; idx < E; idx++) begin
      @(negedge clk);
      edge_var_we_i = 1'b1;
      edge_var_waddr_i = idx[EDGE_IDX_W-1:0];
      edge_var_wdata_i = edge_var_image[idx];
      @(posedge clk);
    end
    @(negedge clk);
    edge_var_we_i = 1'b0;

    @(negedge clk);
    start_i = 1'b1;
    @(posedge clk);
    elapsed_cycles = 1;
    @(negedge clk);
    start_i = 1'b0;

    for (int cycle = 0; cycle < timeout_cycles; cycle++) begin
      @(posedge clk);
      if (done_o) begin
        hard_fd = $fopen(hard_out_file, "w");
        posterior_fd = $fopen(posterior_out_file, "w");
        counts_fd = $fopen(counts_out_file, "w");
        if ((hard_fd == 0) || (posterior_fd == 0) || (counts_fd == 0))
          $fatal(1, "tb_minsum_decode: failed to open output files");
        for (int idx = 0; idx < N; idx++)
          $fwrite(hard_fd, "%0d\n", hard_decision_o[idx]);
        for (int idx = 0; idx < N; idx++)
          $fwrite(posterior_fd, "%03x\n", posterior_llr_flat_o[(idx * LLR_W) +: LLR_W]);
        $fwrite(counts_fd, "elapsed_cycles=%0d\n", elapsed_cycles);
        $fwrite(counts_fd, "iter_count=%0d\n", iter_count_o);
        $fwrite(counts_fd, "error=%0d\n", error_o);
        $fclose(hard_fd);
        $fclose(posterior_fd);
        $fclose(counts_fd);
        $finish;
      end
      elapsed_cycles = elapsed_cycles + 1;
    end

    $fatal(1, "tb_minsum_decode: timeout after %0d cycles", timeout_cycles);
  end

endmodule
