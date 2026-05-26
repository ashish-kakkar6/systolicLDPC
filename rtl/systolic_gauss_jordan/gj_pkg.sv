`timescale 1ns / 1ps

/*
 * Package: gj_pkg
 *
 * Shared types for the systolic Gauss-Jordan modules.
 *
 * Enums:
 *    opcode_t - Two-bit operation code used by <pe_diag>, <pe_col>, and
 *               higher-level mesh modules.
 */
package gj_pkg;

  /*
   * Enum: opcode_t
   *
   * OP_PASS - Forward the incoming bit unchanged.
   * OP_SWAP - Emit the stored bit and load the incoming bit.
   * OP_ADD - Emit the XOR of the incoming bit and the stored bit.
   * OP_DONT_CARE - Start-cycle placeholder produced by unlock-mode diagonal
   *                processing.
   */
  typedef enum logic [1:0] {
    OP_PASS      = 2'b00,
    OP_SWAP      = 2'b01,
    OP_ADD       = 2'b10,
    OP_LOCK      = 2'b11
  } opcode_t;

endpackage
