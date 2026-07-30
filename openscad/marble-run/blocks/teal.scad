// block-teal (Sideways, bottom) — 60 deg side exit + a low horizontal crossing.
use <../lib.scad>

module mr_teal() {
  difference() {
    block_base();
    union() {
      ch_top();
      ex_side(60, 0);
      ex_across_clear() ex_side(60, 0, divider());
    }
  }
}

mr_teal();
