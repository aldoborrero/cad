// marble-run — shared library: parameters + geometry helpers (OpenSCAD / BOSL2).
//
// Pieces `use <lib.scad>` and compose these helper modules; the main
// `include`s it once. Same numbers as ../../freecad/marble-run/part/lib.py.

include <BOSL2/std.scad>

$fn = 64;
EPS = 0.05;

/* ---------------- parameters ---------------- */
SIDE         = 44;   // cube footprint (quadri-plot side=44)
HEIGHT       = 44;   // block height -- MEASURE (quadri-plot uses 60)
CHAMFER      = 2;    // vertical-edge bevel
BORE_D       = 19;   // marble channel Ø
STUD_D       = 29;   // bottom registration boss
STUD_H       = 8;
STACK_CLEAR  = 1;    // radial stud<->socket gap
SOCKET_D     = STUD_D + 2 * STACK_CLEAR;   // 31
SOCKET_DEPTH = STUD_H + 0.5;               // 8.5
MINI_H       = 12;   // thin landing connector height
FUNNEL_TOP_D = 34;   // connector catch-bowl mouth
FUNNEL_DEPTH = 8;

/* ---------------- solids ---------------- */
// chamfered cube (base at z=0) + bottom stud + top socket/dish
module block_base(h = HEIGHT) {
  difference() {
    union() {
      cuboid([SIDE, SIDE, h], chamfer = CHAMFER, edges = "Z", anchor = BOTTOM);
      down(STUD_H) cyl(h = STUD_H, d = STUD_D, anchor = BOTTOM);
    }
    up(h - SOCKET_DEPTH) cyl(h = SOCKET_DEPTH + EPS, d = SOCKET_D, anchor = BOTTOM);
  }
}

// thin connector body (chamfered) + bottom stud
module connector_solid() {
  union() {
    cuboid([SIDE, SIDE, MINI_H], chamfer = CHAMFER, edges = "Z", anchor = BOTTOM);
    down(STUD_H) cyl(h = STUD_H, d = STUD_D, anchor = BOTTOM);
  }
}

/* ---------------- cutters (subtract from a solid) ---------------- */
// vertical through bore: under the stud, up to the socket floor
module cut_through(h = HEIGHT) {
  down(STUD_H) cyl(h = STUD_H + h - SOCKET_DEPTH + EPS, d = BORE_D, anchor = BOTTOM);
}

// vertical drop from the dish down to the side-exit centre-line
module cut_vertical(h = HEIGHT) {
  zmid = h * 0.45;
  up(zmid) cyl(h = h - SOCKET_DEPTH - zmid + EPS, d = BORE_D, anchor = BOTTOM);
}

// horizontal exit out the +X face at the centre-line
module cut_side(h = HEIGHT) {
  zmid = h * 0.45;
  up(zmid) right(SIDE / 4) xcyl(h = SIDE / 2 + CHAMFER + 2, d = BORE_D);
}

// connector catch bowl (mouth -> bore) and its through bore
module cut_bowl() {
  up(MINI_H - FUNNEL_DEPTH) cyl(h = FUNNEL_DEPTH + EPS, d1 = BORE_D, d2 = FUNNEL_TOP_D, anchor = BOTTOM);
}

module cut_through_mini() {
  down(STUD_H) cyl(h = STUD_H + MINI_H - FUNNEL_DEPTH + EPS, d = BORE_D, anchor = BOTTOM);
}
