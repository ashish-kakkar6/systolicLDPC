`timescale 1ns / 1ps

module minsum_decode_top #(
  parameter int M = 3,
  parameter int N = 6,
  parameter int E = 9,
  parameter int ROW_DEG_MAX = 3,
  parameter int LLR_W = 12,
  parameter int LLR_FRAC = 6,
  parameter int ALPHA_SHIFT = 2,
  parameter int MAX_ITER_W = 8
) (
  input  logic                              clk,
  input  logic                              rst,
  input  logic                              start_i,
  input  logic                              result_mode_i,
  input  logic [MAX_ITER_W-1:0]             max_iter_i,
  input  logic                              prior_we_i,
  input  logic [((N <= 1) ? 1 : $clog2(N))-1:0] prior_waddr_i,
  input  logic signed [LLR_W-1:0]           prior_wdata_i,
  input  logic                              syndrome_we_i,
  input  logic [((M <= 1) ? 1 : $clog2(M))-1:0] syndrome_waddr_i,
  input  logic                              syndrome_wdata_i,
  input  logic                              row_ptr_we_i,
  input  logic [((((M + 1) <= 1) ? 1 : $clog2(M + 1)))-1:0] row_ptr_waddr_i,
  input  logic [(((E + 1) <= 1) ? 1 : $clog2(E + 1))-1:0]   row_ptr_wdata_i,
  input  logic                              edge_var_we_i,
  input  logic [((E <= 1) ? 1 : $clog2(E))-1:0]             edge_var_waddr_i,
  input  logic [((N <= 1) ? 1 : $clog2(N))-1:0]             edge_var_wdata_i,
  output logic                              busy_o,
  output logic                              done_o,
  output logic                              error_o,
  output logic [MAX_ITER_W-1:0]             iter_count_o,
  output logic [N-1:0]                      hard_decision_o,
  output logic [(N * LLR_W)-1:0]            posterior_llr_flat_o
);

  localparam int VAR_IDX_W = (N <= 1) ? 1 : $clog2(N);
  localparam int EDGE_IDX_W = (E <= 1) ? 1 : $clog2(E);
  localparam int CHK_IDX_W = (M <= 1) ? 1 : $clog2(M);
  localparam int ROW_PTR_DEPTH = M + 1;
  localparam int ROW_PTR_ADDR_W = (ROW_PTR_DEPTH <= 1) ? 1 : $clog2(ROW_PTR_DEPTH);
  localparam int ROW_PTR_W = ((E + 1) <= 1) ? 1 : $clog2(E + 1);
  localparam int ROW_DEG_W = (ROW_DEG_MAX <= 1) ? 1 : $clog2(ROW_DEG_MAX + 1);
  localparam int WIDE_W = LLR_W + 2;
  typedef logic [ROW_PTR_W-1:0] row_ptr_t;
  localparam row_ptr_t ROW_DEG_MAX_LIMIT = row_ptr_t'(ROW_DEG_MAX);

  typedef enum logic [2:0] {
    S_IDLE       = 3'd0,
    S_INIT_APP   = 3'd1,
    S_INIT_C2V   = 3'd2,
    S_ROW_PREP   = 3'd3,
    S_ROW_GATHER = 3'd4,
    S_ROW_EMIT   = 3'd5,
    S_FINAL      = 3'd6
  } state_t;

  state_t state_q;
  logic error_q;
  logic [MAX_ITER_W-1:0] iter_q;
  logic [MAX_ITER_W-1:0] target_iter_q;

  logic signed [LLR_W-1:0] prior_mem     [0:N-1];
  logic                    syndrome_mem  [0:M-1];
  logic [ROW_PTR_W-1:0]    row_ptr_mem   [0:ROW_PTR_DEPTH-1];
  logic [VAR_IDX_W-1:0]    edge_var_mem  [0:E-1];

  logic signed [LLR_W-1:0] app_mem       [0:N-1];
  logic signed [LLR_W-1:0] c2v_mem       [0:E-1];
  logic signed [LLR_W-1:0] posterior_q   [0:N-1];
  logic [N-1:0]            hard_q;

  logic [VAR_IDX_W-1:0]    row_var_buf   [0:ROW_DEG_MAX-1];
  logic [EDGE_IDX_W-1:0]   row_edge_buf  [0:ROW_DEG_MAX-1];
  logic signed [LLR_W-1:0] row_old_buf   [0:ROW_DEG_MAX-1];
  logic signed [LLR_W-1:0] row_q_buf     [0:ROW_DEG_MAX-1];
  logic signed [(ROW_DEG_MAX * LLR_W)-1:0] row_q_flat;
  logic signed [(ROW_DEG_MAX * LLR_W)-1:0] row_msg_flat;
  logic [ROW_PTR_W-1:0] calc_edge_idx;
  logic [VAR_IDX_W-1:0] calc_var_idx;
  logic [ROW_PTR_W-1:0] calc_stop_idx;
  logic [ROW_PTR_W-1:0] calc_deg;

  integer init_idx_q;
  integer row_idx_q;
  logic [ROW_PTR_W-1:0] row_start_q;
  logic [ROW_DEG_W-1:0] row_deg_q;
  logic [ROW_DEG_W-1:0] row_slot_q;
  integer final_idx_q;

  integer ff_idx;

  function automatic logic signed [WIDE_W-1:0] extend_llr(input logic signed [LLR_W-1:0] value);
    extend_llr = {{(WIDE_W-LLR_W){value[LLR_W-1]}}, value};
  endfunction

  function automatic logic signed [LLR_W-1:0] sat_llr(input logic signed [WIDE_W-1:0] value);
    localparam logic signed [WIDE_W-1:0] MAX_LLR_WIDE = (1 <<< (LLR_W - 1)) - 1;
    localparam logic signed [WIDE_W-1:0] MIN_LLR_WIDE = -(1 <<< (LLR_W - 1));
    if (value > MAX_LLR_WIDE)
      sat_llr = {1'b0, {(LLR_W - 1){1'b1}}};
    else if (value < MIN_LLR_WIDE)
      sat_llr = {1'b1, {(LLR_W - 1){1'b0}}};
    else
      sat_llr = value[LLR_W-1:0];
  endfunction

  function automatic logic hard_decide_from_llr(input logic signed [LLR_W-1:0] value);
    if (value < 0)
      hard_decide_from_llr = 1'b1;
    else
      hard_decide_from_llr = 1'b0;
  endfunction

  function automatic logic signed [LLR_W-1:0] row_msg_at(input logic [ROW_DEG_W-1:0] slot_idx);
    row_msg_at = $signed(row_msg_flat[(slot_idx * LLR_W) +: LLR_W]);
  endfunction

  genvar row_slot_gen;
  generate
    for (row_slot_gen = 0; row_slot_gen < ROW_DEG_MAX; row_slot_gen++) begin : g_row_flat
      assign row_q_flat[(row_slot_gen * LLR_W) +: LLR_W] = row_q_buf[row_slot_gen];
    end
  endgenerate

  minsum_row_engine #(
    .ROW_DEG_MAX(ROW_DEG_MAX),
    .LLR_W(LLR_W),
    .ALPHA_SHIFT(ALPHA_SHIFT)
  ) u_row_engine (
    .row_deg_i(row_deg_q[ROW_DEG_W-1:0]),
    .syndrome_bit_i((row_idx_q >= 0 && row_idx_q < M) ? syndrome_mem[row_idx_q] : 1'b0),
    .row_q_flat_i(row_q_flat),
    .row_msg_flat_o(row_msg_flat)
  );

  assign busy_o = (state_q != S_IDLE);
  assign error_o = error_q;
  assign iter_count_o = iter_q;
  assign hard_decision_o = hard_q;

  generate
    for (genvar out_var = 0; out_var < N; out_var++) begin : g_posterior_flat
      assign posterior_llr_flat_o[(out_var * LLR_W) +: LLR_W] = posterior_q[out_var];
    end
  endgenerate

  always_ff @(posedge clk) begin
    if (rst) begin
      state_q <= S_IDLE;
      done_o <= 1'b0;
      error_q <= 1'b0;
      iter_q <= '0;
      target_iter_q <= '0;
      init_idx_q <= 0;
      row_idx_q <= 0;
      row_start_q <= 0;
      row_deg_q <= 0;
      row_slot_q <= 0;
      final_idx_q <= 0;
      hard_q <= '0;
      for (ff_idx = 0; ff_idx < N; ff_idx++) begin
        prior_mem[ff_idx] <= '0;
        app_mem[ff_idx] <= '0;
        posterior_q[ff_idx] <= '0;
      end
      for (ff_idx = 0; ff_idx < M; ff_idx++)
        syndrome_mem[ff_idx] <= 1'b0;
      for (ff_idx = 0; ff_idx < ROW_PTR_DEPTH; ff_idx++)
        row_ptr_mem[ff_idx] <= '0;
      for (ff_idx = 0; ff_idx < E; ff_idx++) begin
        edge_var_mem[ff_idx] <= '0;
        c2v_mem[ff_idx] <= '0;
      end
      for (ff_idx = 0; ff_idx < ROW_DEG_MAX; ff_idx++) begin
        row_var_buf[ff_idx] <= '0;
        row_edge_buf[ff_idx] <= '0;
        row_old_buf[ff_idx] <= '0;
        row_q_buf[ff_idx] <= '0;
      end
    end else begin
      done_o <= 1'b0;

      if (prior_we_i)
        prior_mem[prior_waddr_i] <= prior_wdata_i;
      if (syndrome_we_i)
        syndrome_mem[syndrome_waddr_i] <= syndrome_wdata_i;
      if (row_ptr_we_i)
        row_ptr_mem[row_ptr_waddr_i] <= row_ptr_wdata_i;
      if (edge_var_we_i)
        edge_var_mem[edge_var_waddr_i] <= edge_var_wdata_i;

      case (state_q)
        S_IDLE: begin
          if (start_i) begin
            if (max_iter_i == '0) begin
              error_q <= 1'b1;
            end else begin
              error_q <= 1'b0;
              iter_q <= '0;
              target_iter_q <= max_iter_i;
              init_idx_q <= 0;
              hard_q <= '0;
              state_q <= S_INIT_APP;
            end
          end
        end

        S_INIT_APP: begin
          app_mem[init_idx_q] <= prior_mem[init_idx_q];
          posterior_q[init_idx_q] <= '0;
          if (init_idx_q == (N - 1)) begin
            init_idx_q <= 0;
            state_q <= S_INIT_C2V;
          end else begin
            init_idx_q <= init_idx_q + 1;
          end
        end

        S_INIT_C2V: begin
          c2v_mem[init_idx_q] <= '0;
          if (init_idx_q == (E - 1)) begin
            row_idx_q <= 0;
            state_q <= S_ROW_PREP;
          end else begin
            init_idx_q <= init_idx_q + 1;
          end
        end

        S_ROW_PREP: begin
          if (row_idx_q >= M) begin
            if ((iter_q + 1'b1) >= target_iter_q) begin
              iter_q <= target_iter_q;
              final_idx_q <= 0;
              state_q <= S_FINAL;
            end else begin
              iter_q <= iter_q + 1'b1;
              row_idx_q <= 0;
            end
          end else begin
            calc_edge_idx = row_ptr_mem[row_idx_q];
            calc_stop_idx = row_ptr_mem[row_idx_q + 1];
            calc_deg = calc_stop_idx - calc_edge_idx;
            if (calc_deg > ROW_DEG_MAX_LIMIT) begin
              error_q <= 1'b1;
              state_q <= S_IDLE;
            end else begin
              row_start_q <= calc_edge_idx;
              row_deg_q <= calc_deg[ROW_DEG_W-1:0];
              row_slot_q <= 0;
              state_q <= S_ROW_GATHER;
            end
          end
        end

        S_ROW_GATHER: begin
          if (row_slot_q >= row_deg_q) begin
            row_slot_q <= 0;
            state_q <= S_ROW_EMIT;
          end else begin
            calc_edge_idx = row_start_q + {{(ROW_PTR_W-ROW_DEG_W){1'b0}}, row_slot_q};
            calc_var_idx = edge_var_mem[calc_edge_idx];
            row_edge_buf[row_slot_q] <= calc_edge_idx[EDGE_IDX_W-1:0];
            row_var_buf[row_slot_q] <= calc_var_idx[VAR_IDX_W-1:0];
            row_old_buf[row_slot_q] <= c2v_mem[calc_edge_idx];
            row_q_buf[row_slot_q] <= sat_llr(extend_llr(app_mem[calc_var_idx]) - extend_llr(c2v_mem[calc_edge_idx]));
            if (row_slot_q == (row_deg_q - 1)) begin
              row_slot_q <= 0;
              state_q <= S_ROW_EMIT;
            end else begin
              row_slot_q <= row_slot_q + 1;
            end
          end
        end

        S_ROW_EMIT: begin
          if (row_slot_q >= row_deg_q) begin
            row_idx_q <= row_idx_q + 1;
            state_q <= S_ROW_PREP;
          end else begin
            calc_edge_idx = row_edge_buf[row_slot_q];
            calc_var_idx = row_var_buf[row_slot_q];
            c2v_mem[calc_edge_idx] <= row_msg_at(row_slot_q);
            app_mem[calc_var_idx] <= sat_llr(extend_llr(app_mem[calc_var_idx]) - extend_llr(row_old_buf[row_slot_q]) + extend_llr(row_msg_at(row_slot_q)));
            if (row_slot_q == (row_deg_q - 1)) begin
              row_idx_q <= row_idx_q + 1;
              row_slot_q <= 0;
              state_q <= S_ROW_PREP;
            end else begin
              row_slot_q <= row_slot_q + 1;
            end
          end
        end

        S_FINAL: begin
          posterior_q[final_idx_q] <= app_mem[final_idx_q];
          hard_q[final_idx_q] <= hard_decide_from_llr(app_mem[final_idx_q]);
          if (final_idx_q == (N - 1)) begin
            done_o <= 1'b1;
            state_q <= S_IDLE;
          end else begin
            final_idx_q <= final_idx_q + 1;
          end
        end

        default: state_q <= S_IDLE;
      endcase
    end
  end

endmodule
