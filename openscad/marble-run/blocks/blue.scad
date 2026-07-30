// block-blue (Sideways, bottom) — 60 deg side exit + bottom exit + a back exit.
use <../lib.scad>

module mr_blue() {
  difference() {
    block_base();
    union() {
      ch_top();
      ex_side(60, 0);
      ex_bottom();
      ex_back_clear() ex_side(60, 0, divider());
    }
  }
}

mr_blue();
