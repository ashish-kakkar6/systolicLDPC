`timescale 1ns / 1ps

module bp_osd_score_bridge #(
    parameter int N = 1,
    parameter int N_PAD = 1,
    parameter int LLR_W = 8,
    parameter int SCORE_SHIFT = 5
) (
    input  logic                     clk,
    input  logic                     rst,
    input  logic                     start_i,
    input  logic signed [N*LLR_W-1:0] posterior_llr_flat_i,
    output logic                     busy_o,
    output logic                     done_o,
    output logic                     estimate_we_o,
    output logic [$clog2((N_PAD > 1) ? N_PAD : 2)-1:0] estimate_waddr_o,
    output logic [31:0]              estimate_wdata_o,
    output logic                     cutoff_we_o,
    output logic [31:0]              cutoff_wdata_o
);
    localparam int ADDR_W = $clog2((N_PAD > 1) ? N_PAD : 2);

    typedef enum logic [1:0] {
        S_IDLE,
        S_WRITE_EST,
        S_WRITE_CUTOFF,
        S_DONE
    } state_t;

    state_t state_q;
    localparam logic [LLR_W-1:0] MAX_SCORE_VALUE = 14;

    int unsigned idx_q;

    function automatic logic signed [LLR_W-1:0] llr_at(input int unsigned index);
        llr_at = posterior_llr_flat_i[index*LLR_W +: LLR_W];
    endfunction

    function automatic logic [3:0] score_from_llr(input logic signed [LLR_W-1:0] value);
        logic [LLR_W-1:0] abs_value;
        logic [LLR_W-1:0] scaled_value;
        begin
            abs_value = value[LLR_W-1] ? $unsigned(-$signed(value)) : $unsigned(value);
            scaled_value = $unsigned(abs_value) >> SCORE_SHIFT;
            if (scaled_value > MAX_SCORE_VALUE) begin
                score_from_llr = 4'd14;
            end else begin
                score_from_llr = scaled_value[3:0];
            end
        end
    endfunction

    always_ff @(posedge clk or posedge rst) begin
        if (rst) begin
            state_q <= S_IDLE;
            idx_q <= '0;
        end else begin
            case (state_q)
                S_IDLE: begin
                    idx_q <= '0;
                    if (start_i) begin
                        state_q <= S_WRITE_EST;
                    end
                end
                S_WRITE_EST: begin
                    if (idx_q == (N_PAD - 1)) begin
                        idx_q <= '0;
                        state_q <= S_WRITE_CUTOFF;
                    end else begin
                        idx_q <= idx_q + 1'b1;
                    end
                end
                S_WRITE_CUTOFF: begin
                    state_q <= S_DONE;
                end
                S_DONE: begin
                    state_q <= S_IDLE;
                end
                default: begin
                    state_q <= S_IDLE;
                    idx_q <= '0;
                end
            endcase
        end
    end

    always @(*) begin
        logic [3:0] score_value;

        busy_o = (state_q != S_IDLE) && (state_q != S_DONE);
        done_o = (state_q == S_DONE);

        estimate_we_o = 1'b0;
        estimate_waddr_o = idx_q[ADDR_W-1:0];
        estimate_wdata_o = 32'd0;
        cutoff_we_o = 1'b0;
        cutoff_wdata_o = 32'd15;

        score_value = 4'd15;
        if (idx_q < N) begin
            score_value = score_from_llr(llr_at(idx_q));
        end

        case (state_q)
            S_WRITE_EST: begin
                estimate_we_o = 1'b1;
                estimate_wdata_o = {28'd0, score_value};
            end
            S_WRITE_CUTOFF: begin
                cutoff_we_o = 1'b1;
            end
            default: begin
            end
        endcase
    end
endmodule
