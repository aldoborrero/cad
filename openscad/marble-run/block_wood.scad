// block-wood (bottom crossing) — vertical through + a low horizontal crossing.
use <lib.scad>

module mr_wood() {
  difference() {
    block_base();
    union() {
      ch_top();
      ex_vertical();
      ex_across();
    }
  }
}

mr_wood();
