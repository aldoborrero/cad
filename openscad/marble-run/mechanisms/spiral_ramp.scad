// spiral-ramp ("Turmdreher") — a helical ramp that wraps around a tower. The marble
// enters at the top and spirals down 270° before exiting at the bottom; the central
// hub slides over the tower's stud. Modelled from the real Hape part (96 x 96 x 38).
use <../lib.scad>

module mr_spiral_ramp() { spiral_ramp(); }

mr_spiral_ramp();
