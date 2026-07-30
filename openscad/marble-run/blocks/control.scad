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
  control_knob();
}

mr_control();
