// connector-white (Wheat) — thin chamfered cube with a straight Ø30 hole, no stud
// (quadri-plot MiniWhiteBlock). A spacer/ring the marble drops straight through.
use <lib.scad>

module mr_connector_white() {
  difference() {
    cuboid([SIDE, SIDE, MINI_H], chamfer = CHAMFER, edges = "Z", anchor = BOTTOM);
    translate([0, 0, -1]) cylinder(h = MINI_H + 2, d = SOCKET_D);
  }
}

mr_connector_white();
