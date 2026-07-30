// block-green (Sideways, bottom) — 60 deg side exit + bottom exit + low crossing.
use <../lib.scad>

module mr_green() {
  difference() {
    block_base();
    union() {
      ch_top();
      ex_side(60, 0);
      ex_bottom();
      ex_across_clear() ex_side(60, 0, divider());
    }
  }
}

mr_green();
