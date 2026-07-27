// marble-run — Hape Quadrilla-compatible marble run (OpenSCAD / BOSL2)
//
// The OpenSCAD sibling of freecad/marble-run (Part/CSG) and
// freecad/marble-run-partdesign (Part Design). Same numbers, same pieces.
//
// Render one piece with -D, e.g.:  openscad -D 'part="turn"' -o turn.stl marble-run.scad
// Default `part="all"` lays every piece out on a plate (what `cad export` builds).

include <BOSL2/std.scad>

/* ---------------- parameters (mirror freecad/marble-run/params.py) ------------- */
SIDE          = 44;   // cube footprint  (quadri-plot side=44)
HEIGHT        = 44;   // block height    -- MEASURE (quadri-plot uses 60)
CHAMFER       = 2;    // vertical-edge bevel
BORE_D        = 19;   // marble channel diameter (marble + clearance)
STUD_D        = 29;   // bottom registration boss
STUD_H        = 8;
STACK_CLEAR   = 1;    // radial stud<->socket gap (29 -> 31)
SOCKET_D      = STUD_D + 2 * STACK_CLEAR;   // 31
SOCKET_DEPTH  = STUD_H + 0.5;               // 8.5
MINI_H        = 12;   // thin landing connector height
FUNNEL_TOP_D  = 34;   // connector catch-bowl mouth
FUNNEL_DEPTH  = 8;
MARBLE_D      = 16;

$fn = 64;
EPS = 0.05;

/* ---------------- shared geometry ---------------- */
// chamfered cube (base at z=0) + bottom stud + top socket/dish
module block_base(h) {
  difference() {
    union() {
      cuboid([SIDE, SIDE, h], chamfer = CHAMFER, edges = "Z", anchor = BOTTOM);
      down(STUD_H) cyl(h = STUD_H, d = STUD_D, anchor = BOTTOM);
    }
    up(h - SOCKET_DEPTH) cyl(h = SOCKET_DEPTH + EPS, d = SOCKET_D, anchor = BOTTOM);
  }
}

/* ---------------- pieces ---------------- */
module mr_blank() { block_base(HEIGHT); }

module mr_straight() {
  difference() {
    block_base(HEIGHT);
    // through bore: from under the stud up to the socket floor
    down(STUD_H) cyl(h = STUD_H + HEIGHT - SOCKET_DEPTH + EPS, d = BORE_D, anchor = BOTTOM);
  }
}

module mr_turn() {
  zmid = HEIGHT * 0.45;   // side-exit centre-line
  difference() {
    block_base(HEIGHT);
    union() {
      up(zmid) cyl(h = HEIGHT - SOCKET_DEPTH - zmid + EPS, d = BORE_D, anchor = BOTTOM);
      up(zmid) right(SIDE / 4) xcyl(h = SIDE / 2 + CHAMFER + 2, d = BORE_D);
    }
  }
}

module mr_connector() {
  difference() {
    union() {
      cuboid([SIDE, SIDE, MINI_H], chamfer = CHAMFER, edges = "Z", anchor = BOTTOM);
      down(STUD_H) cyl(h = STUD_H, d = STUD_D, anchor = BOTTOM);
    }
    // conical catch bowl (mouth -> bore) + through bore
    up(MINI_H - FUNNEL_DEPTH) cyl(h = FUNNEL_DEPTH + EPS, d1 = BORE_D, d2 = FUNNEL_TOP_D, anchor = BOTTOM);
    down(STUD_H) cyl(h = STUD_H + MINI_H - FUNNEL_DEPTH + EPS, d = BORE_D, anchor = BOTTOM);
  }
}

module mr_marble() { sphere(d = MARBLE_D); }

/* ---------------- selector ---------------- */
part = "all";   // all | blank | straight | turn | connector | marble

module layout() {
  pitch = SIDE + 16;
  translate([0 * pitch, 0, 0])       mr_blank();
  translate([1 * pitch, 0, 0])       mr_straight();
  translate([2 * pitch, 0, 0])       mr_turn();
  translate([3 * pitch, 0, 0])       mr_connector();
  translate([4 * pitch, 0, STUD_H])  mr_marble();
}

if      (part == "all")       layout();
else if (part == "blank")     mr_blank();
else if (part == "straight")  mr_straight();
else if (part == "turn")      mr_turn();
else if (part == "connector") mr_connector();
else if (part == "marble")    mr_marble();
