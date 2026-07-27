// block-turn (yellow) — enters top, turns 90 deg, exits the +X side face.
use <lib.scad>

module mr_turn() {
  difference() {
    block_base();
    union() {
      cut_vertical();
      cut_side();
    }
  }
}

mr_turn();
