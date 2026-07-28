// flag-tower (FlagTower) — 2-part spinner (PLA adaptation of quadri-plot's
// transparent-tube flag tower). Body (fixed: base + axle + open cage + drop bore)
// and spinner (disc with 3 holes + hub over the axle + flag) laid out side by side
// for printing. Assemble by dropping the spinner over the axle post.
use <lib.scad>

module mr_flag_tower() {
  flag_tower_body();
  translate([100, 0, 0]) flag_spinner();
}

mr_flag_tower();
