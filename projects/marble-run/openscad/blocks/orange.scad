// block-orange (Vertical) — marble drops straight through.
use <../lib.scad>

module mr_orange() {
  difference() {
    block_base();
    union() {
      ch_top();
      ex_vertical();
    }
  }
}

mr_orange();
