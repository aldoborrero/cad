// marble-run — main: place every piece (OpenSCAD / BOSL2).
//
// Library:  lib.scad          (parameters + geometry helpers)
// Pieces:   block_*.scad, connector_funnel.scad  (each `use`s lib, defines mr_*)
// This main: `include`s lib once, `use`s each piece, lays them all out.
//
// Render one piece with -D, e.g.:
//   openscad -D 'part="yellow"' -o yellow.stl marble-run.scad
// Default part="all" builds every piece on a plate (what `cad export` produces).

include <lib.scad>
use <block_blank.scad>
use <block_orange.scad>
use <block_yellow.scad>
use <block_green.scad>
use <block_teal.scad>
use <block_blue.scad>
use <block_wood.scad>
use <block_red.scad>
use <block_control.scad>
use <connector_funnel.scad>
use <connector_white.scad>
use <rail_curve60.scad>
use <rail_curve120.scad>
use <rail_s.scad>
use <rail_straight.scad>
use <spiral_tower.scad>

// blocks: all | blank | orange | yellow | green | teal | blue | wood | red | connector
// rails:  rail_curve60 | rail_curve120 | rail_s | rail_straight
part = "all";

module layout() {
  pitch = SIDE + 16;
  for (i = [0:8]) {
    translate([(i % 5) * pitch, floor(i / 5) * pitch, 0]) {
      if      (i == 0) mr_blank();
      else if (i == 1) mr_orange();
      else if (i == 2) mr_yellow();
      else if (i == 3) mr_green();
      else if (i == 4) mr_teal();
      else if (i == 5) mr_blue();
      else if (i == 6) mr_wood();
      else if (i == 7) mr_red();
      else if (i == 8) mr_connector();
    }
  }
}

if      (part == "all")       layout();
else if (part == "blank")     mr_blank();
else if (part == "orange")    mr_orange();
else if (part == "yellow")    mr_yellow();
else if (part == "green")     mr_green();
else if (part == "teal")      mr_teal();
else if (part == "blue")      mr_blue();
else if (part == "wood")      mr_wood();
else if (part == "red")           mr_red();
else if (part == "control")       mr_control();
else if (part == "connector")     mr_connector();
else if (part == "connector_white") mr_connector_white();
else if (part == "rail_curve60")  mr_rail_curve60();
else if (part == "rail_curve120") mr_rail_curve120();
else if (part == "rail_s")        mr_rail_s();
else if (part == "rail_straight") mr_rail_straight();
else if (part == "spiral_tower")  mr_spiral_tower();
