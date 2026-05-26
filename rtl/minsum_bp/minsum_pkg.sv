`timescale 1ns / 1ps

package minsum_pkg;

  function automatic integer alpha_scale_mag(input integer magnitude, input integer shift);
    integer scaled;
    scaled = magnitude - (magnitude >>> shift);
    if (scaled < 0)
      alpha_scale_mag = 0;
    else
      alpha_scale_mag = scaled;
  endfunction

endpackage
