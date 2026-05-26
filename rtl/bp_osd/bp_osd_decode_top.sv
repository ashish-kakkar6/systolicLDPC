module bp_osd_decode_top #(
    parameter int M = 1,
    parameter int N = 1,
    parameter int E = 1,
    parameter int ROW_DEG_MAX = 1,
    parameter int LLR_W = 12,
    parameter int LLR_FRAC = 6,
    parameter int MAX_ITER_W = 8,
    parameter int N_PAD_MAX = 1,
    parameter int M_MAX = M,
    parameter int N_MAX = N,
    parameter int TOP_P_MAX = ((3 * M_MAX) < N_PAD_MAX) ? (3 * M_MAX) : N_PAD_MAX,
    parameter int COUNT_W = 16,
    parameter int SCORE_SHIFT = 5
) (
    input  logic                     clk,
    input  logic                     rst,
    input  logic                     start_i,
    input  logic [MAX_ITER_W-1:0]    max_iter_i,

    input  logic                     bp_prior_we_i,
    input  logic [$clog2((N > 1) ? N : 2)-1:0] bp_prior_waddr_i,
    input  logic signed [LLR_W-1:0]  bp_prior_wdata_i,
    input  logic                     bp_syndrome_we_i,
    input  logic [$clog2((M > 1) ? M : 2)-1:0] bp_syndrome_waddr_i,
    input  logic                     bp_syndrome_wdata_i,
    input  logic                     bp_row_ptr_we_i,
    input  logic [$clog2(((M + 1) > 1) ? (M + 1) : 2)-1:0] bp_row_ptr_waddr_i,
    input  logic [$clog2((E + 1) > 1 ? (E + 1) : 2)-1:0] bp_row_ptr_wdata_i,
    input  logic                     bp_edge_var_we_i,
    input  logic [$clog2((E > 1) ? E : 2)-1:0] bp_edge_var_waddr_i,
    input  logic [$clog2((N > 1) ? N : 2)-1:0] bp_edge_var_wdata_i,

    input  logic                     osd_h_we_i,
    input  logic [$clog2((M_MAX > 1) ? M_MAX : 2)-1:0] osd_h_waddr_i,
    input  logic [N-1:0]             osd_h_wdata_i,
    input  logic                     osd_sigma_we_i,
    input  logic [$clog2((M_MAX > 1) ? M_MAX : 2)-1:0] osd_sigma_waddr_i,
    input  logic                     osd_sigma_wdata_i,

    output logic                     busy_o,
    output logic                     done_o,
    output logic                     error_o,
    output logic [MAX_ITER_W-1:0]    bp_iter_count_o,
    output logic [N-1:0]             bp_hard_decision_o,
    output logic signed [N*LLR_W-1:0] bp_posterior_llr_flat_o,

    output logic [$clog2((M_MAX + 1) > 1 ? (M_MAX + 1) : 2)-1:0] selected_count_o,
    output logic [$clog2((M_MAX + 1) > 1 ? (M_MAX + 1) : 2)-1:0] compacted_rows_o,
    output logic [M_MAX*$clog2((N_PAD_MAX > 1) ? N_PAD_MAX : 2)-1:0] selected_indices_flat_o,
    output logic                     reduced_write_valid_o,
    output logic [$clog2((M_MAX < 64) ? 64 : M_MAX)-1:0] reduced_write_addr_o,
    output logic [M_MAX-1:0]         reduced_write_row_o,
    output logic                     reduced_write_sigma_o,
    output logic [M_MAX-1:0]         x_hardware_o,
    output logic [N_MAX-1:0]         f_hardware_o,
    output logic                     solver_start_o,
    output logic [COUNT_W-1:0]       solver_run_cycles_o,
    output logic                     solver_trace_valid_o,
    output logic                     solver_trace_bit_o
);
    localparam int BP_ROW_PTR_W = $clog2((E + 1) > 1 ? (E + 1) : 2);
    localparam int BP_EDGE_VAR_ADDR_W = $clog2((E > 1) ? E : 2);
    localparam int OSD_EST_ADDR_W = $clog2((N_PAD_MAX > 1) ? N_PAD_MAX : 2);

    typedef enum logic [3:0] {
        S_IDLE,
        S_BP_START,
        S_BP_WAIT,
        S_BRIDGE_START,
        S_BRIDGE_WAIT,
        S_OSD_START,
        S_OSD_WAIT,
        S_DONE,
        S_ERROR
    } state_t;

    state_t state_q;
    logic error_q;

    logic bp_start_q;
    logic bp_busy;
    logic bp_done;
    logic bp_error;
    logic [MAX_ITER_W-1:0] bp_iter_count;
    logic [N-1:0] bp_hard_decision;
    logic signed [N*LLR_W-1:0] bp_posterior_llr_flat;

    logic bridge_start_q;
    logic bridge_busy;
    logic bridge_done;
    logic bridge_estimate_we;
    logic [OSD_EST_ADDR_W-1:0] bridge_estimate_waddr;
    logic [31:0] bridge_estimate_wdata;
    logic bridge_cutoff_we;
    logic [31:0] bridge_cutoff_wdata;

    logic osd_start_q;
    logic osd_busy;
    logic osd_done;
    logic osd_error;

    minsum_decode_top #(
        .M(M),
        .N(N),
        .E(E),
        .ROW_DEG_MAX(ROW_DEG_MAX),
        .LLR_W(LLR_W),
        .LLR_FRAC(LLR_FRAC),
        .MAX_ITER_W(MAX_ITER_W)
    ) u_bp (
        .clk(clk),
        .rst(rst),
        .start_i(bp_start_q),
        .max_iter_i(max_iter_i),
        .prior_we_i(bp_prior_we_i),
        .prior_waddr_i(bp_prior_waddr_i),
        .prior_wdata_i(bp_prior_wdata_i),
        .syndrome_we_i(bp_syndrome_we_i),
        .syndrome_waddr_i(bp_syndrome_waddr_i),
        .syndrome_wdata_i(bp_syndrome_wdata_i),
        .row_ptr_we_i(bp_row_ptr_we_i),
        .row_ptr_waddr_i(bp_row_ptr_waddr_i),
        .row_ptr_wdata_i(bp_row_ptr_wdata_i),
        .edge_var_we_i(bp_edge_var_we_i),
        .edge_var_waddr_i(bp_edge_var_waddr_i),
        .edge_var_wdata_i(bp_edge_var_wdata_i),
        .busy_o(bp_busy),
        .done_o(bp_done),
        .error_o(bp_error),
        .iter_count_o(bp_iter_count),
        .result_mode_i(1'b0),
        .hard_decision_o(bp_hard_decision),
        .posterior_llr_flat_o(bp_posterior_llr_flat)
    );

    bp_osd_score_bridge #(
        .N(N),
        .N_PAD(N_PAD_MAX),
        .LLR_W(LLR_W),
        .SCORE_SHIFT(SCORE_SHIFT)
    ) u_bridge (
        .clk(clk),
        .rst(rst),
        .start_i(bridge_start_q),
        .posterior_llr_flat_i(bp_posterior_llr_flat),
        .busy_o(bridge_busy),
        .done_o(bridge_done),
        .estimate_we_o(bridge_estimate_we),
        .estimate_waddr_o(bridge_estimate_waddr),
        .estimate_wdata_o(bridge_estimate_wdata),
        .cutoff_we_o(bridge_cutoff_we),
        .cutoff_wdata_o(bridge_cutoff_wdata)
    );

    osd_control_top #(
        .M_MAX(M_MAX),
        .N_MAX(N_MAX),
        .N_PAD_MAX(N_PAD_MAX),
        .TOP_P_MAX(TOP_P_MAX),
        .COUNT_W(COUNT_W)
    ) u_osd (
        .clk(clk),
        .rst(rst),
        .start_i(osd_start_q),
        .h_we_i(osd_h_we_i),
        .h_waddr_i(osd_h_waddr_i),
        .h_wdata_i(osd_h_wdata_i),
        .sigma_we_i(osd_sigma_we_i),
        .sigma_waddr_i(osd_sigma_waddr_i),
        .sigma_wdata_i(osd_sigma_wdata_i),
        .estimate_we_i(bridge_estimate_we),
        .estimate_waddr_i(bridge_estimate_waddr),
        .estimate_wdata_i(bridge_estimate_wdata),
        .cutoff_we_i(bridge_cutoff_we),
        .cutoff_wdata_i(bridge_cutoff_wdata),
        .busy_o(osd_busy),
        .done_o(osd_done),
        .error_o(osd_error),
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

    always_ff @(posedge clk or posedge rst) begin
        if (rst) begin
            state_q <= S_IDLE;
            error_q <= 1'b0;
        end else begin
            case (state_q)
                S_IDLE: begin
                    error_q <= 1'b0;
                    if (start_i) begin
                        state_q <= S_BP_START;
                    end
                end
                S_BP_START: begin
                    state_q <= S_BP_WAIT;
                end
                S_BP_WAIT: begin
                    if (bp_error) begin
                        error_q <= 1'b1;
                        state_q <= S_ERROR;
                    end else if (bp_done) begin
                        state_q <= S_BRIDGE_START;
                    end
                end
                S_BRIDGE_START: begin
                    state_q <= S_BRIDGE_WAIT;
                end
                S_BRIDGE_WAIT: begin
                    if (bridge_done) begin
                        state_q <= S_OSD_START;
                    end
                end
                S_OSD_START: begin
                    state_q <= S_OSD_WAIT;
                end
                S_OSD_WAIT: begin
                    if (osd_error) begin
                        error_q <= 1'b1;
                        state_q <= S_ERROR;
                    end else if (osd_done) begin
                        state_q <= S_DONE;
                    end
                end
                S_DONE: begin
                    state_q <= S_IDLE;
                end
                S_ERROR: begin
                    state_q <= S_IDLE;
                end
                default: begin
                    state_q <= S_IDLE;
                    error_q <= 1'b0;
                end
            endcase
        end
    end

    always_comb begin
        bp_start_q = 1'b0;
        bridge_start_q = 1'b0;
        osd_start_q = 1'b0;

        case (state_q)
            S_BP_START: begin
                bp_start_q = 1'b1;
            end
            S_BRIDGE_START: begin
                bridge_start_q = 1'b1;
            end
            S_OSD_START: begin
                osd_start_q = 1'b1;
            end
            default: begin
            end
        endcase
    end

    assign busy_o = (state_q != S_IDLE) && (state_q != S_DONE) && (state_q != S_ERROR);
    assign done_o = (state_q == S_DONE);
    assign error_o = error_q;
    assign bp_iter_count_o = bp_iter_count;
    assign bp_hard_decision_o = bp_hard_decision;
    assign bp_posterior_llr_flat_o = bp_posterior_llr_flat;
endmodule
