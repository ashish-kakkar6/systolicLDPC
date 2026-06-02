`timescale 1ns / 1ps

/*
 * Module: control
 *
 * Hardware pipeline controller for:
 *   problem_store -> sorter -> ranked basis selection -> row compaction
 *   -> systolic solver -> solution column
 *
 *
 *   - full H, sigma, quantized cutoff, and quantized scores are already resident in RAM
 *   - the sorter keeps only the exact stable top-P ranked candidates
 *   - the sorter and score lookup path use narrow address/data reads
 *   - selected columns are gathered into a square reduced system
 *   - if compaction does not preserve a square system, error_o is asserted
 *   - the final solution column tail is captured, aligned in S_FLIP, then scattered
 *   - important: TOP_P_MAX must be large enough, because some ranked columns
 *     can fail the independence test before M_MAX columns are accepted
 */
module control #(
  parameter int M_MAX = 24,
  parameter int N_MAX = 221,
  parameter int N_PAD_MAX = 256,
  parameter int TOP_P_MAX = ((3 * M_MAX) < N_PAD_MAX) ? (3 * M_MAX) : N_PAD_MAX,
  parameter int COUNT_W = 16,
  parameter int SORT_IDX_W = (N_PAD_MAX <= 1) ? 1 : $clog2(N_PAD_MAX),
  parameter int SELECT_W = (M_MAX <= 1) ? 1 : $clog2(M_MAX + 1),
  parameter int SOLVER_SRC_DEPTH = (M_MAX < 64) ? 64 : M_MAX,
  parameter int SOLVER_ADDR_W = $clog2((M_MAX < 64) ? 64 : M_MAX)
) (
  input  logic                          clk,
  input  logic                          rst,
  input  logic                          start_i,
  input  logic [(M_MAX * N_MAX)-1:0]    h_rows_flat_i,
  input  logic [M_MAX-1:0]              sigma_flat_i,
  output logic [SORT_IDX_W-1:0]         estimate_sort_raddr_o,
  input  logic [3:0]                    estimate_sort_rdata_i,
  output logic [SORT_IDX_W-1:0]         estimate_lookup_raddr_o,
  input  logic [3:0]                    estimate_lookup_rdata_i,
  input  logic [3:0]                    cutoff_i,
  output logic                          busy_o,
  output logic                          done_o,
  output logic                          error_o,
  output logic [SELECT_W-1:0]           selected_count_o,
  output logic [SELECT_W-1:0]           compacted_rows_o,
  output logic [(M_MAX * SORT_IDX_W)-1:0] selected_indices_flat_o,
  output logic                          reduced_write_valid_o,
  output logic [SOLVER_ADDR_W-1:0]      reduced_write_addr_o,
  output logic [M_MAX-1:0]              reduced_write_row_o,
  output logic                          reduced_write_sigma_o,
  output logic [M_MAX-1:0]              x_hardware_o,
  output logic [N_MAX-1:0]              f_hardware_o,
  output logic                          solver_start_o,
  output logic [COUNT_W-1:0]            solver_run_cycles_o,
  output logic                          solver_trace_valid_o,
  output logic                          solver_trace_bit_o
);

  localparam logic [COUNT_W-1:0] SOLVER_RUN_BASE_CYCLES = COUNT_W'(3 * M_MAX);
  localparam int EFFECTIVE_TOP_P = (TOP_P_MAX < 1) ? 1 : ((TOP_P_MAX > N_PAD_MAX) ? N_PAD_MAX : TOP_P_MAX);
  localparam int ROW_IDX_W = (M_MAX <= 1) ? 1 : $clog2(M_MAX);
  localparam int SCAN_COUNT_W = $clog2(N_PAD_MAX + 1);

  typedef enum logic [3:0] {
    S_IDLE,
    S_START_SORT,
    S_WAIT_SORT,
    S_SELECT_COLS,
    S_CLEAR_SOLVER_MEM,
    S_COMPACT_ROWS,
    S_START_SOLVER,
    S_WAIT_SOLVER,
    S_FLIP,
    S_DONE,
    S_ERROR
  } state_t;

  state_t state_q;

  logic                        sorter_start;
  logic                        sorter_busy;
  logic                        sorter_done;
  logic [SORT_IDX_W-1:0]       sorter_score_raddr;
  logic [SORT_IDX_W-1:0]       sorter_ranked_raddr;
  logic [SORT_IDX_W-1:0]       sorter_ranked_rdata;

  logic                        solver_start;
  logic                        solver_busy;
  logic                        solver_done;
  logic                        solver_error;
  logic                        solver_a_we;
  logic [SOLVER_ADDR_W-1:0]    solver_a_waddr;
  logic [M_MAX-1:0]            solver_a_wdata;
  logic                        solver_b_we;
  logic [SOLVER_ADDR_W-1:0]    solver_b_waddr;
  logic                        solver_b_wdata;
  logic [SELECT_W-1:0]         selected_count_q;
  logic [SELECT_W-1:0]         compacted_rows_q;
  logic [$clog2(N_PAD_MAX+1)-1:0] scan_idx_q;
  logic [$clog2(M_MAX+1)-1:0]  row_scan_q;
  logic [(M_MAX * SORT_IDX_W)-1:0] selected_indices_q;
  logic [(M_MAX * M_MAX)-1:0]  basis_flat_q;
  logic [COUNT_W-1:0]          solver_rows_q;
  logic [SOLVER_ADDR_W-1:0]    solver_clear_addr_q;
  logic                        trace_capture_delay_q;
  logic [COUNT_W-1:0]          trace_capture_remaining_q;
  logic [M_MAX-1:0]            trace_tail_q;
  logic [M_MAX-1:0]            x_hardware_q;
  logic [N_MAX-1:0]            f_hardware_q;
  logic                        error_q;

  logic [3:0]                  current_score;
  logic [SORT_IDX_W-1:0]       current_index;
  logic [M_MAX-1:0]            current_candidate_col;
  logic [M_MAX-1:0]            reduced_candidate_col;
  logic                        candidate_below_cutoff;
  logic                        candidate_in_range;
  logic [N_MAX-1:0]            current_h_row;
  logic [M_MAX-1:0]            current_reduced_row;
  logic                        current_sigma_bit;
  logic                        current_row_nonzero;

  function automatic logic [N_MAX-1:0] h_row_at(
    input logic [(M_MAX * N_MAX)-1:0] flat,
    input logic [ROW_IDX_W-1:0] row
  );
    h_row_at = flat[(row * N_MAX) +: N_MAX];
  endfunction

  function automatic logic [M_MAX-1:0] h_column_at(
    input logic [(M_MAX * N_MAX)-1:0] flat,
    input logic [SORT_IDX_W-1:0] col
  );
    logic [M_MAX-1:0] column_bits;
    begin
      column_bits = '0;
      for (int row = 0; row < M_MAX; row++) begin
        column_bits[row] = flat[(row * N_MAX) + int'(col)];
      end
      h_column_at = column_bits;
    end
  endfunction

  function automatic integer first_one_idx(input logic [M_MAX-1:0] vec);
    integer pivot;
    begin
      pivot = -1;
      for (int bit_idx = 0; bit_idx < M_MAX; bit_idx++) begin
        if ((pivot < 0) && vec[bit_idx])
          pivot = bit_idx;
      end
      first_one_idx = pivot;
    end
  endfunction

  function automatic logic [M_MAX-1:0] basis_col_at(
    input logic [(M_MAX * M_MAX)-1:0] flat,
    input logic [ROW_IDX_W-1:0] idx
  );
    basis_col_at = flat[(idx * M_MAX) +: M_MAX];
  endfunction

  function automatic logic [M_MAX-1:0] reduce_candidate(
    input logic [M_MAX-1:0] candidate,
    input logic [(M_MAX * M_MAX)-1:0] basis_flat,
    input logic [SELECT_W-1:0] basis_count
  );
    logic [M_MAX-1:0] temp;
    logic [M_MAX-1:0] basis_col;
    integer pivot;
    begin
      temp = candidate;
      for (int idx = 0; idx < basis_count; idx++) begin
        basis_col = basis_col_at(basis_flat, ROW_IDX_W'(idx));
        pivot = first_one_idx(basis_col);
        if ((pivot >= 0) && temp[pivot])
          temp = temp ^ basis_col;
      end
      reduce_candidate = temp;
    end
  endfunction

  function automatic logic [M_MAX-1:0] gather_selected_row(
    input logic [N_MAX-1:0] row_bits,
    input logic [(M_MAX * SORT_IDX_W)-1:0] selected_flat,
    input logic [SELECT_W-1:0] count
  );
    logic [M_MAX-1:0] gathered;
    logic [SORT_IDX_W-1:0] idx_bits;
    begin
      gathered = '0;
      for (int idx = 0; idx < count; idx++) begin
        idx_bits = selected_flat[(idx * SORT_IDX_W) +: SORT_IDX_W];
        gathered[idx] = row_bits[idx_bits];
      end
      gather_selected_row = gathered;
    end
  endfunction

  function automatic logic [N_MAX-1:0] scatter_solution(
    input logic [M_MAX-1:0] reduced_bits,
    input logic [(M_MAX * SORT_IDX_W)-1:0] selected_flat,
    input logic [SELECT_W-1:0] count
  );
    logic [N_MAX-1:0] full_bits;
    logic [SORT_IDX_W-1:0] idx_bits;
    begin
      full_bits = '0;
      for (int idx = 0; idx < count; idx++) begin
        idx_bits = selected_flat[(idx * SORT_IDX_W) +: SORT_IDX_W];
        if (int'(idx_bits) < N_MAX)
          full_bits[idx_bits] = reduced_bits[idx];
      end
      scatter_solution = full_bits;
    end
  endfunction

  ranker_u4_wrapper #(
    .N_PAD_MAX(N_PAD_MAX),
    .IDX_W(SORT_IDX_W),
    .TOP_P_MAX(EFFECTIVE_TOP_P)
  ) u_sorter (
    .clk(clk),
    .rst(rst),
    .start_i(sorter_start),
    .score_raddr_o(sorter_score_raddr),
    .score_rdata_i(estimate_sort_rdata_i),
    .ranked_raddr_i(sorter_ranked_raddr),
    .busy_o(sorter_busy),
    .done_o(sorter_done),
    .ranked_rdata_o(sorter_ranked_rdata)
  );

  solver_gj_wrapper #(
    .ROWS_MAX(M_MAX),
    .COLS_MAX(M_MAX),
    .COUNT_W(COUNT_W),
    .SRC_DEPTH(SOLVER_SRC_DEPTH)
  ) u_solver (
    .clk(clk),
    .rst(rst),
    .start_i(solver_start),
    .rows_i(solver_rows_q),
    .a_we_i(solver_a_we),
    .a_waddr_i(solver_a_waddr),
    .a_wdata_i(solver_a_wdata),
    .b_we_i(solver_b_we),
    .b_waddr_i(solver_b_waddr),
    .b_wdata_i(solver_b_wdata),
    .busy_o(solver_busy),
    .done_o(solver_done),
    .error_o(solver_error),
    .trace_valid_o(solver_trace_valid_o),
    .trace_bit_o(solver_trace_bit_o)
  );

  always_comb begin
    if (int'(scan_idx_q) < N_PAD_MAX) begin
      current_index = sorter_ranked_rdata;
      current_score = estimate_lookup_rdata_i;
    end else begin
      current_index = '0;
      current_score = 4'h0;
    end

    candidate_in_range = (int'(current_index) < N_MAX);
    if (candidate_in_range)
      current_candidate_col = h_column_at(h_rows_flat_i, current_index);
    else
      current_candidate_col = '0;

    reduced_candidate_col = reduce_candidate(current_candidate_col, basis_flat_q, selected_count_q);
    candidate_below_cutoff = (current_score < cutoff_i);

    if (int'(row_scan_q) < M_MAX) begin
      current_h_row = h_row_at(h_rows_flat_i, ROW_IDX_W'(row_scan_q));
      current_sigma_bit = sigma_flat_i[ROW_IDX_W'(row_scan_q)];
    end else begin
      current_h_row = '0;
      current_sigma_bit = 1'b0;
    end

    current_reduced_row = gather_selected_row(current_h_row, selected_indices_q, selected_count_q);
    current_row_nonzero = |current_reduced_row;
  end

  assign sorter_start = (state_q == S_START_SORT);
  assign sorter_ranked_raddr = SORT_IDX_W'(scan_idx_q);
  assign estimate_sort_raddr_o = sorter_score_raddr;
  assign estimate_lookup_raddr_o = current_index;
  assign solver_start = (state_q == S_START_SOLVER);

  assign solver_a_we =
    (state_q == S_CLEAR_SOLVER_MEM) ||
    ((state_q == S_COMPACT_ROWS) && (row_scan_q < SELECT_W'(M_MAX)) && current_row_nonzero);
  assign solver_a_waddr =
    (state_q == S_CLEAR_SOLVER_MEM) ? solver_clear_addr_q : SOLVER_ADDR_W'(compacted_rows_q);
  assign solver_a_wdata =
    (state_q == S_CLEAR_SOLVER_MEM) ? '0 : current_reduced_row;
  assign solver_b_we = solver_a_we;
  assign solver_b_waddr = solver_a_waddr;
  assign solver_b_wdata =
    (state_q == S_CLEAR_SOLVER_MEM) ? 1'b0 : current_sigma_bit;

  assign reduced_write_valid_o = (state_q == S_COMPACT_ROWS) && (row_scan_q < SELECT_W'(M_MAX)) && current_row_nonzero;
  assign reduced_write_addr_o = solver_a_waddr;
  assign reduced_write_row_o = current_reduced_row;
  assign reduced_write_sigma_o = current_sigma_bit;

  assign selected_indices_flat_o = selected_indices_q;
  assign selected_count_o = selected_count_q;
  assign compacted_rows_o = compacted_rows_q;
  assign x_hardware_o = x_hardware_q;
  assign f_hardware_o = f_hardware_q;
  assign solver_start_o = solver_start;
  assign solver_run_cycles_o = solver_rows_q + SOLVER_RUN_BASE_CYCLES;

  assign busy_o = !((state_q == S_IDLE) || (state_q == S_DONE) || (state_q == S_ERROR));
  assign error_o = error_q || solver_error || (state_q == S_ERROR);

  always_ff @(posedge clk) begin
    if (rst) begin
      state_q <= S_IDLE;
      selected_count_q <= '0;
      compacted_rows_q <= '0;
      scan_idx_q <= '0;
      row_scan_q <= '0;
      selected_indices_q <= '0;
      for (int idx = 0; idx < M_MAX; idx++) begin
        basis_flat_q[(idx * M_MAX) +: M_MAX] <= '0;
      end
      solver_rows_q <= '0;
      solver_clear_addr_q <= '0;
      trace_capture_delay_q <= 1'b0;
      trace_capture_remaining_q <= '0;
      trace_tail_q <= '0;
      x_hardware_q <= '0;
      f_hardware_q <= '0;
      error_q <= 1'b0;
      done_o <= 1'b0;
    end else begin
      done_o <= 1'b0;

      case (state_q)
        S_IDLE: begin
          if (start_i) begin
            selected_count_q <= '0;
            compacted_rows_q <= '0;
            scan_idx_q <= '0;
            row_scan_q <= '0;
            selected_indices_q <= '0;
            for (int idx = 0; idx < M_MAX; idx++) begin
              basis_flat_q[(idx * M_MAX) +: M_MAX] <= '0;
            end
            solver_rows_q <= '0;
            solver_clear_addr_q <= '0;
            trace_capture_delay_q <= 1'b0;
            trace_capture_remaining_q <= '0;
            trace_tail_q <= '0;
            x_hardware_q <= '0;
            f_hardware_q <= '0;
            error_q <= 1'b0;
            state_q <= S_START_SORT;
          end
        end

        S_START_SORT: begin
          state_q <= S_WAIT_SORT;
        end

        S_WAIT_SORT: begin
          if (sorter_done) begin
            scan_idx_q <= '0;
            state_q <= S_SELECT_COLS;
          end
        end

        S_SELECT_COLS: begin
          if (scan_idx_q >= SCAN_COUNT_W'(EFFECTIVE_TOP_P)) begin
            if (selected_count_q < SELECT_W'(M_MAX)) begin
              error_q <= 1'b1;
              state_q <= S_ERROR;
            end else begin
              row_scan_q <= '0;
              compacted_rows_q <= '0;
              solver_clear_addr_q <= '0;
              state_q <= S_CLEAR_SOLVER_MEM;
            end
          end else begin
            if (candidate_in_range && candidate_below_cutoff && (|reduced_candidate_col)) begin
              selected_indices_q[(selected_count_q * SORT_IDX_W) +: SORT_IDX_W] <= current_index;
              basis_flat_q[(selected_count_q * M_MAX) +: M_MAX] <= reduced_candidate_col;
              selected_count_q <= selected_count_q + 1'b1;
              if ((selected_count_q + SELECT_W'(1)) >= SELECT_W'(M_MAX)) begin
                row_scan_q <= '0;
                compacted_rows_q <= '0;
                solver_clear_addr_q <= '0;
                state_q <= S_CLEAR_SOLVER_MEM;
              end
            end
            scan_idx_q <= scan_idx_q + 1'b1;
          end
        end

        S_CLEAR_SOLVER_MEM: begin
          if (solver_clear_addr_q == SOLVER_ADDR_W'(SOLVER_SRC_DEPTH - 1)) begin
            row_scan_q <= '0;
            compacted_rows_q <= '0;
            state_q <= S_COMPACT_ROWS;
          end else begin
            solver_clear_addr_q <= solver_clear_addr_q + 1'b1;
          end
        end

        S_COMPACT_ROWS: begin
          if (row_scan_q >= SELECT_W'(M_MAX)) begin
            if (selected_count_q == '0) begin
              error_q <= 1'b1;
              state_q <= S_ERROR;
            end else if (compacted_rows_q != selected_count_q) begin
              error_q <= 1'b1;
              state_q <= S_ERROR;
            end else begin
              solver_rows_q <= COUNT_W'(compacted_rows_q);
              state_q <= S_START_SOLVER;
            end
          end else begin
            if (current_row_nonzero) begin
              compacted_rows_q <= compacted_rows_q + 1'b1;
            end else if (current_sigma_bit) begin
              error_q <= 1'b1;
              state_q <= S_ERROR;
            end
            row_scan_q <= row_scan_q + 1'b1;
          end
        end

        S_START_SOLVER: begin
          trace_capture_delay_q <= 1'b1;
          trace_capture_remaining_q <= solver_rows_q + SOLVER_RUN_BASE_CYCLES + 1'b1;
          trace_tail_q <= '0;
          state_q <= S_WAIT_SOLVER;
        end

        S_WAIT_SOLVER: begin
          if (trace_capture_delay_q) begin
            trace_capture_delay_q <= 1'b0;
          end else if (trace_capture_remaining_q != '0) begin
            trace_tail_q <= {solver_trace_bit_o, trace_tail_q[M_MAX-1:1]};
            trace_capture_remaining_q <= trace_capture_remaining_q - 1'b1;
          end

          if (solver_error) begin
            error_q <= 1'b1;
            state_q <= S_ERROR;
          end else if (solver_done) begin
            state_q <= S_FLIP;
          end
        end

        S_FLIP: begin
          // trace_tail_q already holds the last reduced-solution bits in the
          // same order as np.flip(solver_trace[:, 0]) from the software flow.
          x_hardware_q <= trace_tail_q;
          f_hardware_q <= scatter_solution(
            trace_tail_q,
            selected_indices_q,
            selected_count_q
          );
          done_o <= 1'b1;
          state_q <= S_DONE;
        end

        S_DONE: begin
          done_o <= 1'b1;
          if (!start_i)
            state_q <= S_IDLE;
        end

        S_ERROR: begin
          if (!start_i)
            state_q <= S_IDLE;
        end

        default: begin
          error_q <= 1'b1;
          state_q <= S_ERROR;
        end
      endcase
    end
  end

endmodule
