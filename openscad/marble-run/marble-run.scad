// marble-run — main: place every piece (OpenSCAD / BOSL2).
//
// Library:  lib.scad          (parameters + geometry helpers)
// Pieces:   block_*.scad, connector_funnel.scad  (each `use`s lib, defines mr_*)
// This main: `include`s lib once, `use`s each piece, lays them all out.
//
// Render one piece with -D, e.g.:
//   openscad -D 'part="turn"' -o turn.stl marble-run.scad
// Default part="all" builds every piece on a plate (what `cad export` produces).

include <lib.scad>
use <block_blank.scad>
use <block_straight.scad>
use <block_turn.scad>
use <connector_funnel.scad>

part = "all";   // all | blank | straight | turn | connector

module layout() {
  pitch = SIDE + 16;
  translate([0 * pitch, 0, 0]) mr_blank();
  translate([1 * pitch, 0, 0]) mr_straight();
  translate([2 * pitch, 0, 0]) mr_turn();
  translate([3 * pitch, 0, 0]) mr_connector();
}

if      (part == "all")       layout();
else if (part == "blank")     mr_blank();
else if (part == "straight")  mr_straight();
else if (part == "turn")      mr_turn();
else if (part == "connector") mr_connector();
