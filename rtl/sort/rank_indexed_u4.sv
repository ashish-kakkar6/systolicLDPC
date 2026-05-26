`timescale 1ns / 1ps

/*
 * Module: rank_indexed_u4
 *
 * Exact stable smallest-first top-P ranker for quantized 4-bit scores.
 *
 * The ranker reads one score per cycle and inserts the incoming (score, index)
 * pair into a sorted chain of length TOP_P. Only the best TOP_P entries are
 * retained. Ties are broken by original index, matching the software
 * reference's stable (score, index) ordering exactly.
 */
module rank_indexed_u4 #(
  parameter int N = 8,
  parameter int IDX_W = (N <= 1) ? 1 : $clog2(N),
  parameter int TOP_P = N
) (
  input  logic                    clk,
  input  logic                    rst,
  input  logic                    start_i,
  output logic [IDX_W-1:0]        score_raddr_o,
  input  logic [3:0]              score_rdata_i,
  input  logic [IDX_W-1:0]        ranked_raddr_i,
  output logic                    busy_o,
  output logic                    done_o,
  output logic [IDX_W-1:0]        ranked_rdata_o
);

  localparam int KEEP_P = (TOP_P < 1) ? 1 : ((TOP_P > N) ? N : TOP_P);

  typedef enum logic [0:0] {
    S_IDLE,
    S_LOAD
  } state_t;

  state_t state_q;
  logic [IDX_W-1:0] scan_idx_q;
  logic             valid_q [0:KEEP_P-1];
  logic [3:0]       score_q [0:KEEP_P-1];
  logic [IDX_W-1:0] index_q [0:KEEP_P-1];

  logic             valid_d [0:KEEP_P-1];
  logic [3:0]       score_d [0:KEEP_P-1];
  logic [IDX_W-1:0] index_d [0:KEEP_P-1];
  logic             carry_valid [0:KEEP_P];
  logic [3:0]       carry_score [0:KEEP_P];
  logic [IDX_W-1:0] carry_index [0:KEEP_P];

  integer ii;

  assign score_raddr_o = scan_idx_q;
  assign busy_o = (state_q != S_IDLE);

  always_comb begin
    ranked_rdata_o = '0;
    if (int'(ranked_raddr_i) < KEEP_P)
      ranked_rdata_o = index_q[int'(ranked_raddr_i)];
  end

  always_comb begin
    for (int idx = 0; idx < KEEP_P; idx++) begin
      valid_d[idx] = valid_q[idx];
      score_d[idx] = score_q[idx];
      index_d[idx] = index_q[idx];
    end

    carry_valid[0] = 1'b1;
    carry_score[0] = score_rdata_i;
    carry_index[0] = scan_idx_q;

    for (int idx = 0; idx < KEEP_P; idx++) begin
      carry_valid[idx + 1] = 1'b0;
      carry_score[idx + 1] = '0;
      carry_index[idx + 1] = '0;

      if (carry_valid[idx]) begin
        if (!valid_q[idx]) begin
          valid_d[idx] = 1'b1;
          score_d[idx] = carry_score[idx];
          index_d[idx] = carry_index[idx];
        end else if ((carry_score[idx] < score_q[idx]) ||
                     ((carry_score[idx] == score_q[idx]) &&
                      (carry_index[idx] < index_q[idx]))) begin
          valid_d[idx] = 1'b1;
          score_d[idx] = carry_score[idx];
          index_d[idx] = carry_index[idx];
          carry_valid[idx + 1] = 1'b1;
          carry_score[idx + 1] = score_q[idx];
          carry_index[idx + 1] = index_q[idx];
        end else begin
          carry_valid[idx + 1] = 1'b1;
          carry_score[idx + 1] = carry_score[idx];
          carry_index[idx + 1] = carry_index[idx];
        end
      end
    end
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      state_q <= S_IDLE;
      scan_idx_q <= '0;
      done_o <= 1'b0;
      for (ii = 0; ii < KEEP_P; ii++) begin
        valid_q[ii] <= 1'b0;
        score_q[ii] <= '0;
        index_q[ii] <= '0;
      end
    end else begin
      done_o <= 1'b0;

      case (state_q)
        S_IDLE: begin
          if (start_i) begin
            scan_idx_q <= '0;
            for (ii = 0; ii < KEEP_P; ii++) begin
              valid_q[ii] <= 1'b0;
              score_q[ii] <= '0;
              index_q[ii] <= '0;
            end
            state_q <= S_LOAD;
          end
        end

        S_LOAD: begin
          for (ii = 0; ii < KEEP_P; ii++) begin
            valid_q[ii] <= valid_d[ii];
            score_q[ii] <= score_d[ii];
            index_q[ii] <= index_d[ii];
          end

          if (scan_idx_q == IDX_W'(N - 1)) begin
            done_o <= 1'b1;
            state_q <= S_IDLE;
          end else begin
            scan_idx_q <= scan_idx_q + 1'b1;
          end
        end

        default: begin
          state_q <= S_IDLE;
        end
      endcase
    end
  end

endmodule
