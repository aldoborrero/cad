// block-control (White) — green channels + an orange control knob on a side face
// (quadri-plot ControlBlock = ExitGreen + knobs).
use <../lib.scad>

module mr_control() {
  difference() {
    block_base();
    union() {
      ch_top();
      ex_side(60, 0);
      ex_bottom();
      ex_across();
    }
  }
  // orange control knob on the +Y face (port of quadri-plot's knob)
  rotate([0, 0, 90]) translate([SIDE / 2, 0, HEIGHT * 2 / 3]) rotate([0, 90, 0]) {
    translate([0, 0, 3]) cylinder(h = 4, r = 13);
    cylinder(h = 3, r = 4);
  }
}

mr_control();
