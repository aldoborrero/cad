// block-red (Built-in toggle) — top entry + two 60 deg side exits at 90 deg
// (the toggle picks which side the marble takes).
use <../lib.scad>

module mr_red() {
  difference() {
    block_base();
    union() {
      ch_top();
      ex_side(60, 0);
      ex_side(60, 90);
    }
  }
}

mr_red();
