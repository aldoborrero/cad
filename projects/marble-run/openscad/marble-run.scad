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
//             catalogue (every distinct piece laid out side by side, to look at)
part = "all";

// One dispatch, used by everything. Selecting a piece by name is the only thing OpenSCAD
// offers in place of passing a module around, and there were three copies of this chain.
module piece(name) {
  if      (name == "blank")         mr_blank();
  else if (name == "orange")        mr_orange();
  else if (name == "yellow")        mr_yellow();
  else if (name == "green")         mr_green();
  else if (name == "teal")          mr_teal();
  else if (name == "blue")          mr_blue();
  else if (name == "wood")          mr_wood();
  else if (name == "red")           mr_red();
  else if (name == "control")       mr_control();
  else if (name == "funnel")        mr_funnel();
  else if (name == "white")         mr_white();
  else if (name == "rail_straight") mr_rail_straight();
  else if (name == "rail_curve60")  mr_rail_curve60();
  else if (name == "rail_curve120") mr_rail_curve120();
  else if (name == "rail_s")        mr_rail_s();
  else if (name == "rail_curve120_a") mr_rail_curve120_a();
  else if (name == "rail_curve120_b") mr_rail_curve120_b();
  else if (name == "rail_s_a")      mr_rail_s_a();
  else if (name == "rail_s_b")      mr_rail_s_b();
  else if (name == "spiral")        mr_spiral();
  else if (name == "catcher")       mr_catcher();
  else if (name == "catcher_hape")  mr_catcher_hape();
  else if (name == "flag")          mr_flag_spinner();
  else if (name == "spiral_ramp")   mr_spiral_ramp();
  else if (name == "seesaw")        mr_seesaw();
  else if (name == "seesaw_arm")    mr_seesaw_arm();
  else if (name == "seesaw_mount")  mr_seesaw_mount();
  else if (name == "drop_tower3")   mr_drop_tower_3();
  else if (name == "drop_tower2")   mr_drop_tower_2();
  else if (name == "accelerator")   mr_accelerator();
  else if (name == "skate")         mr_skate();
  else if (name == "fitcheck")      mr_fitcheck();
}

// The printable plate: the eight channelled blocks and the funnel, on the 44 grid.
PLATE = ["blank", "orange", "yellow", "green", "teal", "blue", "wood", "red", "funnel"];
module layout() {
  pitch = SIDE + 16;
  for (i = [0:len(PLATE) - 1])
    translate([(i % 5) * pitch, floor(i / 5) * pitch, 0]) piece(PLATE[i]);
}

// Every distinct piece side by side, for looking at -- NOT for printing: rail_s alone is
// 374 mm. Halves and sub-parts are left out (rail_*_a/_b, seesaw_arm, seesaw_mount), since
// they add nothing to see.
//
// The offsets are not a grid. Each piece carries its own origin -- blocks are centred on
// theirs, the straight rail runs off in +x, the curves swing about a centre 230 mm away --
// so a uniform pitch would pile them on top of each other. These bring each piece's own
// bounding box to its slot, shelf-packed within 800 mm, and were read off the built meshes.
CATALOGUE = [
  [ 22.0,  22.0, "blank"],       [ 86.0,  22.0, "orange"],
  [150.0,  22.0, "yellow"],      [214.0,  22.0, "green"],
  [278.0,  22.0, "teal"],        [342.0,  22.0, "blue"],
  [406.0,  22.0, "wood"],        [470.0,  22.0, "red"],
  [534.0,  22.0, "control"],     [598.0,  22.0, "funnel"],
  [662.0,  22.0, "white"],       [704.0,  11.4, "accelerator"],
  [ 26.0,  97.0, "spiral"],      [ 94.0,  93.0, "drop_tower2"],
  [158.0,  93.0, "drop_tower3"], [222.0, 137.2, "spiral_ramp"],
  [362.7,  93.0, "seesaw"],      [466.7, 105.0, "flag"],
  [ 92.0, 218.0, "catcher"],     [422.0, 239.0, "catcher_hape"],
  [539.5, 205.0, "rail_straight"],
  [ 97.5, 393.4, "fitcheck"],    [373.2, 336.9, "rail_curve60"],
  [557.7, 337.0, "skate"],       [374.0, 606.7, "rail_curve120"],
  [557.6, 812.7, "rail_s"],
];
//
// render() on each piece, which is what makes F5 work at all: the preview normalizes the
// whole CSG tree, 27 pieces take it past the 200000-element ceiling, and it aborts with
// "CSG normalization resulted in an empty tree" -- a blank viewport. render() resolves each
// piece to a mesh first, so the tree is 27 leaves. It costs the same as F6 on the first
// pass and changes no geometry.
module catalogue() {
  for (e = CATALOGUE) translate([e[0], e[1], 0]) render() piece(e[2]);
}

if      (part == "all")       layout();
else if (part == "catalogue") catalogue();
else                          piece(part);
