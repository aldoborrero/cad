// common.scad — shared helpers for this repo's OpenSCAD projects.
// Use with:  use <common.scad>   (lib/openscad is on OPENSCADPATH, set by the devshell,
//                                 so this resolves from any depth under projects/)
// For richer primitives prefer BOSL2 (on OPENSCADPATH): include <BOSL2/std.scad>

// 2D rounded rectangle, centered.
module rrect(w, h, r) {
  offset(r = r) square([w - 2 * r, h - 2 * r], center = true);
}

// Angular sector polygon (centered on the origin), z0..z1 extruded.
// Handy for cutting a "mouth" or windows out of a ring.
module ring_sector(radius, center_angle, half_angle, z0, z1, step = 2) {
  translate([0, 0, z0])
    linear_extrude(z1 - z0)
      polygon(concat(
        [[0, 0]],
        [for (t = [center_angle - half_angle : step : center_angle + half_angle])
          [radius * cos(t), radius * sin(t)]]
      ));
}

// Snap-in C clip that stands off the current top face (+Z); mouth opens toward +X.
module cable_clip(cable_dia = 4, wall = 2) {
  cr = cable_dia / 2;
  difference() {
    cylinder(h = cable_dia + wall, r = cr + wall);
    translate([0, 0, -1]) cylinder(h = cable_dia + wall + 2, r = cr);
    translate([0, -cr * 0.8, -1]) cube([cr + wall + 2, cr * 1.6, cable_dia + wall + 2]);
  }
}

// Round "puck" with a flat base, straight cylindrical wall, and a shallow domed top
// (e.g. the Athom / IoTorero device). Height is measured at the centre of the dome.
module dome_puck(dia, straight_h, total_h) {
  a = dia / 2;
  dome_h = total_h - straight_h;
  Rcap = (a * a + dome_h * dome_h) / (2 * dome_h);
  union() {
    cylinder(h = straight_h, r = a);
    translate([0, 0, straight_h]) intersection() {
      translate([0, 0, dome_h - Rcap]) sphere(r = Rcap);
      cylinder(h = dome_h, r = a + 1);
    }
  }
}
