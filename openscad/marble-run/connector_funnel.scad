// connector-funnel (purple) — thin landing connector: dish on top, bore through to a stud.
use <lib.scad>

module mr_connector() {
  difference() {
    block_base(MINI_H);
    translate([0, 0, LOWEXIT]) cylinder(h = MINI_H - LOWEXIT + EPS, d = BORE_D);
  }
}

mr_connector();
