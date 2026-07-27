// block-straight (orange) — marble drops straight through.
use <lib.scad>

module mr_straight() {
  difference() {
    block_base();
    cut_through();
  }
}

mr_straight();
