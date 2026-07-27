// block-yellow (One side lateral) — top entry + a 60 deg sloped side exit.
use <lib.scad>

module mr_yellow() {
  difference() {
    block_base();
    union() {
      ch_top();
      ex_side(60, 0);
    }
  }
}

mr_yellow();
