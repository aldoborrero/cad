// marble-run — main: place every piece (OpenSCAD / BOSL2).
//
// Library:  lib.scad                       (parameters + geometry helpers)
// Pieces:   blocks/  connectors/  rails/  mechanisms/  towers/
//           (each `use`s ../lib.scad and defines an mr_* module)
// This main: `include`s lib once, `use`s each piece, lays them all out.
//
// Render one piece with -D, e.g.:
//   openscad -D 'part="yellow"' -o yellow.stl marble-run.scad
// Default part="all" builds every block on a plate (what `cad export` produces).

include <lib.scad>

// blocks
use <blocks/blank.scad>
use <blocks/orange.scad>
use <blocks/yellow.scad>
use <blocks/green.scad>
use <blocks/teal.scad>
use <blocks/blue.scad>
use <blocks/wood.scad>
use <blocks/red.scad>
use <blocks/control.scad>
// connectors
use <connectors/funnel.scad>
use <connectors/white.scad>
// rails
use <rails/straight.scad>
use <rails/curve60.scad>
use <rails/curve120.scad>
use <rails/s.scad>
use <rails/curve120_split.scad>
use <rails/s_split.scad>
// mechanisms
use <mechanisms/spiral.scad>
use <catchers/catcher.scad>
use <catchers/catcher_hape.scad>
use <mechanisms/flag_spinner.scad>
use <mechanisms/spiral_ramp.scad>
use <mechanisms/seesaw.scad>
// towers
use <towers/drop.scad>
// tools
use <tools/fitcheck.scad>
// ramps
use <ramps/accelerator.scad>
use <ramps/skate.scad>

// blocks:     all | blank | orange | yellow | green | teal | blue | wood | red | control
// connectors: funnel | white
// rails:      rail_straight | rail_curve60 | rail_curve120 | rail_s
//             split halves (optional, for a 256 mm bed):
//               rail_curve120_a | rail_curve120_b | rail_s_a | rail_s_b
// mechanisms: spiral | flag | spiral_ramp
//             seesaw (both parts) | seesaw_arm | seesaw_mount
// catchers:   catcher (wedge) | catcher_hape
//             the round bowl is a shape, not a part: -D CATCH_SHAPE="round"
// towers:     drop_tower3 | drop_tower2
// ramps:      accelerator | skate
// tools:      fitcheck (the tolerance comb — print this first)
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
      else if (i == 8) mr_funnel();
    }
  }
}

if      (part == "all")           layout();
else if (part == "blank")         mr_blank();
else if (part == "orange")        mr_orange();
else if (part == "yellow")        mr_yellow();
else if (part == "green")         mr_green();
else if (part == "teal")          mr_teal();
else if (part == "blue")          mr_blue();
else if (part == "wood")          mr_wood();
else if (part == "red")           mr_red();
else if (part == "control")       mr_control();
else if (part == "funnel")        mr_funnel();
else if (part == "white")         mr_white();
else if (part == "rail_straight") mr_rail_straight();
else if (part == "rail_curve60")  mr_rail_curve60();
else if (part == "rail_curve120") mr_rail_curve120();
else if (part == "rail_s")        mr_rail_s();
else if (part == "rail_curve120_a") mr_rail_curve120_a();
else if (part == "rail_curve120_b") mr_rail_curve120_b();
else if (part == "rail_s_a")      mr_rail_s_a();
else if (part == "rail_s_b")      mr_rail_s_b();
else if (part == "spiral")        mr_spiral();
else if (part == "catcher")       mr_catcher();
else if (part == "catcher_hape")  mr_catcher_hape();
else if (part == "flag")          mr_flag_spinner();
else if (part == "spiral_ramp")   mr_spiral_ramp();
else if (part == "seesaw")        mr_seesaw();
else if (part == "seesaw_arm")    mr_seesaw_arm();
else if (part == "seesaw_mount")  mr_seesaw_mount();
else if (part == "drop_tower3")   mr_drop_tower_3();
else if (part == "drop_tower2")   mr_drop_tower_2();
else if (part == "accelerator")   mr_accelerator();
else if (part == "skate")         mr_skate();
else if (part == "fitcheck")      mr_fitcheck();
