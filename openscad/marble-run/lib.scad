// marble-run — shared library: parameters + geometry helpers (OpenSCAD / BOSL2).
//
// Channel geometry is a faithful port of shuckc/quadri-plot (blocks.scad):
// a TopEntry bore drops the marble from the dish to the CENTRE pivot, then an
// ExitPart (sphere pivot + bore) carries it out — straight, or tilted `theta`.
// Pieces `use <../lib.scad>` and compose these; the main `include`s it once.

include <BOSL2/std.scad>

$fn = 64;
EPS = 0.05;

/* ---------------- parameters (measured on a real set) ---------------- */
SIDE         = 44;   // cube footprint width
HEIGHT       = 60;   // block height
CHAMFER      = 2;    // edge bevel
BORE_D       = 20;   // marble tunnel Ø
STUD_D       = 28;   // bottom registration boss (fits a 30 socket)
STUD_H       = 8;
STACK_CLEAR  = 1;
SOCKET_D     = STUD_D + 2 * STACK_CLEAR;   // 30 (top dish Ø)
SOCKET_DEPTH = STUD_H + 0.5;               // 8.5
MINI_H       = 12;   // thin landing connector height

/* ---------------- reference heights ---------------- */
CENTER  = HEIGHT / 2;   // channel pivot (quadri-plot: 30)
LOWEXIT = -STUD_H - 2;  // a bore starts just below the stud
LOW     = 6;            // height of the low across/back crossings

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

/* ---------------- channel primitives (subtract from a block) ---------------- */
// TopEntry bore: from the centre pivot up to the top (meets the socket dish)
module ch_top() {
  translate([0, 0, CENTER]) cylinder(h = HEIGHT - CENTER + EPS, d = BORE_D);
}

// ExitPart: sphere pivot at the centre + bore from below the stud up to the centre
module ch_exit() {
  translate([0, 0, CENTER]) sphere(d = BORE_D);
  translate([0, 0, LOWEXIT]) cylinder(h = CENTER - LOWEXIT + EPS, d = BORE_D);
}

// straight vertical exit (orange)
module ex_vertical() { ch_exit(); }

// side exit tilted `theta` from vertical, azimuth `ang` (pivot at the centre)
module ex_side(theta = 60, ang = 0) {
  rotate([0, 0, ang])
    translate([0, 0, CENTER]) rotate([theta, 0, -90]) translate([0, 0, -CENTER]) ch_exit();
}

// low horizontal through-bore across both faces
module ex_across() {
  translate([0, 0, LOW]) rotate([90, 90, 0]) translate([0, 0, -(SIDE + 8) / 2])
    cylinder(h = SIDE + 8, d = BORE_D);
}

// low horizontal bore out one side (back)
module ex_back() {
  translate([0, 0, LOW]) rotate([0, 90, 0]) translate([0, 0, -(SIDE / 2 + 4)])
    cylinder(h = SIDE / 2 + 4, d = BORE_D);
}

// bottom exit: ExitPart lowered so its pivot sits near the bottom
module ex_bottom() { translate([0, 0, LOW - CENTER]) ch_exit(); }

/* ---------------- straight-drop tower (N tiers, one continuous piece) ---------------- */
// A single smooth column `tiers * HEIGHT` tall with a straight vertical bore from the
// top dish out through the bottom stud: the marble drops straight through and exits the
// bottom (which plugs into the next piece). Printed as one manifold part (no seams).
module tower(tiers = 3) {
  h = tiers * HEIGHT;
  difference() {
    block_base(h);
    translate([0, 0, LOWEXIT]) cylinder(h = h - LOWEXIT + EPS, d = BORE_D);
  }
}

/* ---------------- rails (faithful port of quadri-plot bridges.scad) ---------------- */
// quadri-plot cross-section: a chamfered 44 x 11.5 bar with an 8 mm groove cut full
// height -> two parallel rails; the marble rides on the two inner edges. The node
// studs (centred in the groove) bridge the two rails, so it prints as one piece.
RAIL_R   = 230;    // arc radius (quadri-plot)
RAIL_H   = 11.5;   // rail height (quadri-plot)
GROOVE_W = 8;      // groove width (quadri-plot)

module chamfer_square(w, h, c = CHAMFER) {
  polygon([[c, 0], [w - c, 0], [w, c], [w, h - c], [w - c, h], [c, h], [0, h - c], [0, c]]);
}

// 2D rail cross-section, centred on x = 0 (radius/height plane)
module rail_xsec() {
  translate([-SIDE / 2, 0])
    difference() {
      chamfer_square(SIDE, RAIL_H);
      translate([SIDE / 2 - GROOVE_W / 2, 0]) square([GROOVE_W, RAIL_H + 1]);
    }
}

module rail_stud() { translate([0, 0, -STUD_H]) cylinder(h = STUD_H + 2, d = STUD_D); }

// node cut: top dish + through bore (marble drops through / a block stacks on top)
module rail_node_cut() {
  translate([0, 0, RAIL_H - SOCKET_DEPTH]) cylinder(h = SOCKET_DEPTH + EPS, d = SOCKET_D);
  translate([0, 0, LOWEXIT]) cylinder(h = RAIL_H - LOWEXIT + 2 * EPS, d = BORE_D);
}

// quadri-plot ProjectAlongArc: place children at `a` degrees along the arc
module project_arc(a, d = 1) {
  translate([-RAIL_R * d, 0, 0]) rotate([0, 0, d * a]) translate([RAIL_R * d, 0, 0]) children();
}

// curved rail (angle = 60 or 120); studs + node cuts at each 60 deg node
module rail_curve(angle = 60, before = 5, after = 5, d = 1) {
  rad = d * RAIL_R;
  difference() {
    union() {
      translate([-rad, 0, 0])
        rotate([0, 0, -d * before])
          rotate_extrude(angle = d * (angle + before + after), convexity = 10, $fa = 3)
            translate([rad, 0]) rail_xsec();
      rail_stud();
      project_arc(60, d) rail_stud();
      if (angle > 60) project_arc(120, d) rail_stud();
    }
    project_arc(0, d) rail_node_cut();
    project_arc(60, d) rail_node_cut();
    if (angle > 60) project_arc(120, d) rail_node_cut();
  }
}

// S-curve: two 60 deg arcs (quadri-plot SCurve)
module rail_scurve() {
  rail_curve(60, before = 0);
  rotate([0, 0, 180]) rail_curve(60, before = 0);
}

// straight rail in the same style: nodes only at the two ends, straight groove between
module rail_straight(length = 180) {
  inset = SIDE / 2;
  difference() {
    union() {
      rotate([90, 0, 90]) linear_extrude(height = length) rail_xsec();
      translate([inset, 0, 0]) rail_stud();
      translate([length - inset, 0, 0]) rail_stud();
    }
    translate([inset, 0, 0]) rail_node_cut();
    translate([length - inset, 0, 0]) rail_node_cut();
  }
}

/* ---------------- optional split joint for the oversized curved rails ---------------- */
// rail_curve120 (338 x 338) and rail_s (374 x 375) are the only pieces that exceed a
// 256 mm bed. Both can be cut at one of their 60 deg nodes into two ~201 x 201 halves.
// The cut goes through the node, so the node's bore is reassembled from two halves and
// the stud of the block underneath passes through it and pins the joint shut. Two
// sliding dovetails (one per rail bar) keep the halves aligned and stop them lifting:
// each is narrow at the cut face and wider behind it, so the halves are joined by
// lowering one onto the other and cannot be pulled apart along the rail.
//
// This is entirely opt-in — the whole pieces are unchanged. Render a half with e.g.
//   openscad -D 'part="rail_curve120_a"' -o a.stl marble-run.scad
JOINT       = true;  // false -> plain butt cut, no dovetail (glue it yourself)
JOINT_CLEAR = 0.18;  // clearance added all round the female pocket (tune on a test print)
JOINT_X     = 18.5;  // dovetail centre, offset from the rail centreline
JOINT_W0    = 4.5;   // width at the cut face  (kept inside the solid 15..22 band, so it
JOINT_W1    = 6.5;   // width behind the face   clears the node's Ø30 socket)
JOINT_D     = 9;     // how far the tenon reaches past the cut face
BIG         = 600;   // half-space cutter size

// the pair of dovetails at a cut face. `dir` is +1 to reach forward along the arc,
// -1 to reach back; `grow` inflates it into the female pocket.
module rail_tenon(dir = 1, grow = 0) {
  for (s = [-1, 1])
    translate([s * JOINT_X, 0, -grow])
      linear_extrude(height = RAIL_H + 2 * grow)
        offset(delta = grow)
          polygon([[-JOINT_W0 / 2, 0], [JOINT_W0 / 2, 0],
                   [JOINT_W1 / 2, dir * JOINT_D], [-JOINT_W1 / 2, dir * JOINT_D]]);
}

// everything on one side of the radial plane at `at` degrees (to be subtracted)
module rail_halfspace(at, d = 1, keep_near = true) {
  project_arc(at, d) translate([0, (keep_near ? 1 : -1) * BIG / 2, 0]) cube(BIG, center = true);
}

// One half of a curved rail cut at `at` degrees. keep_near = the a < at side, which
// carries the male tenons; the far half gets the matching pockets.
module rail_curve_half(angle, at, keep_near = true, before = 5, after = 5, d = 1, joint = JOINT) {
  difference() {
    union() {
      difference() {
        rail_curve(angle, before, after, d);
        rail_halfspace(at, d, keep_near);
      }
      if (joint && keep_near)
        intersection() {
          project_arc(at, d) rail_tenon(1);
          rail_curve(angle, before, after, d);
        }
    }
    if (joint && !keep_near) project_arc(at, d) rail_tenon(1, JOINT_CLEAR);
  }
}

// The S-curve is already two 60 deg arcs meeting at the origin node, so each half is
// just one of them; the joint sits at that shared node.
module rail_s_half(keep_near = true, joint = JOINT) {
  rot = keep_near ? 0 : 180;
  rotate([0, 0, rot]) difference() {
    union() {
      rail_curve(60, before = 0);
      if (joint && keep_near)
        intersection() {
          rail_tenon(-1);
          translate([0, 0, RAIL_H / 2]) cube([SIDE, 2 * JOINT_D, RAIL_H], center = true);
        }
    }
    if (joint && !keep_near) rail_tenon(-1, JOINT_CLEAR);
  }
}

/* ---------------- spiral tower (quadri-plot CylinderLadder, PLA open cage) ---------------- */
// The transparent tube is replaced by an open rib cage (gaps < marble Ø, so the marble
// stays in but you can see it), and the cascade shelves are fused to the ribs.
TOWER_R      = 24;   // cage / shelf radius
TOWER_H      = 100;  // cage height
TOWER_RIBS   = 8;
TOWER_RIB_D  = 4;
TOWER_SHELVES = 5;
TOWER_SP     = 18;   // shelf spacing
SHELF_T      = 3;
SHELF_TILT   = 8;    // deg, so the marble rolls off
TOWER_BASE_H = 6;

module spiral_ring(z) {
  translate([0, 0, z]) difference() {
    cylinder(r = TOWER_R + TOWER_RIB_D / 2, h = 4);
    translate([0, 0, -1]) cylinder(r = TOWER_R - TOWER_RIB_D / 2, h = 6);
  }
}

// one tilted semicircular cascade shelf, fused to the ribs
module spiral_shelf() {
  difference() {
    rotate([0, SHELF_TILT, 0]) cylinder(r = TOWER_R, h = SHELF_T, center = true);
    translate([TOWER_R, 0, 0]) cube([2 * TOWER_R, 4 * TOWER_R, 4 * TOWER_R], center = true);
  }
}

module spiral_tower() {
  difference() {
    union() {
      cylinder(r = TOWER_R + TOWER_RIB_D / 2, h = TOWER_BASE_H);      // base plate
      translate([0, 0, -STUD_H]) cylinder(h = STUD_H + 2, d = STUD_D);  // stud
      for (k = [0:TOWER_RIBS - 1])                                    // rib cage
        rotate([0, 0, 360 / TOWER_RIBS * k])
          translate([TOWER_R, 0, TOWER_BASE_H]) cylinder(d = TOWER_RIB_D, h = TOWER_H);
      spiral_ring(TOWER_BASE_H);
      spiral_ring(TOWER_BASE_H + TOWER_H - 4);
      for (i = [0:TOWER_SHELVES - 1])                                 // cascade shelves
        translate([0, 0, TOWER_BASE_H + 8 + i * TOWER_SP])
          rotate([0, 0, 180 * (i % 2)]) spiral_shelf();
    }
    translate([0, 0, -STUD_H - 1]) cylinder(h = TOWER_BASE_H + STUD_H + 2, d = BORE_D);  // exit bore
  }
}

/* ---------------- marble catcher (quadri-plot MarbleCatcher) ---------------- */
// A round collection bowl: a chamfered wall ring + a floor. Marbles drop in and
// collect (no exit, as in quadri-plot). Flat bottom sits on the table.
CATCH_R    = 50;   // inner bowl radius
CATCH_WALL = 4;
CATCH_H    = 20;   // wall height
CATCH_FLOOR = 4;

module marble_catcher() {
  rotate_extrude($fa = 4) translate([CATCH_R, 0]) chamfer_square(CATCH_WALL, CATCH_H, 1);
  cylinder(h = CATCH_FLOOR, r = CATCH_R + 1);
}

/* ---------------- flag tower (quadri-plot FlagTower, PLA 2-part spinner) ---------------- */
// Two parts: a fixed body (tapered base + axle post + open rib cage + a drop bore) and a
// rotating spinner (disc with 3 holes + hub over the post + flag). The marble lands on the
// disc; when a hole aligns with the body's drop bore it falls through and exits the bottom.
FLAG_R_BOT   = 22;
FLAG_R_TOP   = 34;
FLAG_BASE_H  = 40;
FLAG_HOLE_R  = BORE_D / 2 + 1;   // 3 disc/exit holes
FLAG_HOLE_RAD = 17;
FLAG_AXLE_R  = 4;
FLAG_AXLE_TOP = 72;
FLAG_CAGE_R  = 32;
FLAG_CZ0     = 44;
FLAG_CZ1     = 70;
FLAG_RIBS    = 8;

module flag(w = 40, h = 24, d = 3) {
  translate([0, 0.5 * d, 0]) rotate([90, 0, 0]) linear_extrude(height = d)
    polygon([[0, 0], [w, 0], [w * 0.8, h * 0.5], [w, h], [0, h]]);
}

module flag_tower_body() {
  difference() {
    union() {
      cylinder(h = FLAG_BASE_H, r1 = FLAG_R_BOT, r2 = FLAG_R_TOP);   // tapered base
      translate([0, 0, -STUD_H]) cylinder(h = STUD_H + 2, d = STUD_D);  // stud
      translate([0, 0, FLAG_BASE_H]) cylinder(h = FLAG_AXLE_TOP - FLAG_BASE_H, r = FLAG_AXLE_R);
      for (k = [0:FLAG_RIBS - 1])                                    // open cage
        rotate([0, 0, 360 / FLAG_RIBS * k])
          translate([FLAG_CAGE_R, 0, FLAG_CZ0]) cylinder(r = 1.6, h = FLAG_CZ1 - FLAG_CZ0);
      translate([0, 0, FLAG_CZ1 - 3]) difference() {                 // top ring
        cylinder(r = FLAG_CAGE_R + 2, h = 3);
        translate([0, 0, -1]) cylinder(r = FLAG_CAGE_R - 2, h = 5);
      }
    }
    translate([FLAG_HOLE_RAD, 0, -STUD_H - 1])                       // drop bore at one hole
      cylinder(h = FLAG_BASE_H + STUD_H + 2, r = FLAG_HOLE_R);
  }
}

module flag_spinner() {
  difference() {
    union() {
      translate([0, 0, FLAG_BASE_H + 0.5]) cylinder(h = 3, r = 30);            // disc
      translate([0, 0, FLAG_BASE_H + 0.5]) cylinder(h = FLAG_AXLE_TOP - 2 - FLAG_BASE_H - 0.5, r = 7);  // hub
      translate([6, 0, FLAG_AXLE_TOP - 26]) flag();                            // flag
    }
    for (k = [0:2])                                                            // 3 holes
      rotate([0, 0, 120 * k]) translate([FLAG_HOLE_RAD, 0, FLAG_BASE_H]) cylinder(h = 5, r = FLAG_HOLE_R);
    translate([0, 0, FLAG_BASE_H - 1]) cylinder(h = FLAG_AXLE_TOP, r = FLAG_AXLE_R + 1);  // bore over post
  }
}

/* ---------------- spiral ramp / tower twister ("Turmdreher") ---------------- */
// A helical ramp that wraps around a tower: the marble enters at the top and spirals
// down a full 270 deg before exiting at the bottom. The path is a rounded square (it
// hugs the 44 mm tower), the cross-section is a flat bar with a Ø20 half-pipe groove,
// and a central 44x44x12 hub with a Ø30 through hole slides over the tower.
// Dimensions measured on a real part: 96 x 96 footprint, floor z 28 -> 10.5.
TURM_A     = 48;    // outer half-width (96 footprint)
TURM_RC    = 25;    // outer corner radius
TURM_MID   = 36.5;  // channel centreline half-width
TURM_MIDRC = 13.5;  // centreline corner radius (TURM_RC - half the bar width)
TURM_W     = 23;    // bar width (cross-section)
TURM_T     = 3;     // floor thickness under the groove
TURM_A0    = 90;    // entry angle (highest point)
TURM_SWEEP = 270;   // degrees swept while descending
TURM_ZTOP  = 28;    // channel floor at the entry
TURM_ZBOT  = 10.5;  // channel floor at the exit
TURM_STEPS = 120;   // sweep resolution
TURM_WEB   = 10;    // width of the webs that tie the ramp to the hub

// radius of a rounded square (half-width a, corner radius rc) at angle th
function turm_fold(th) = let (m = ((th % 90) + 90) % 90) (m > 45 ? 90 - m : m);
function turm_r(a, rc, th) =
  let (f = turm_fold(th), d = a - rc, cd = d * (cos(f) + sin(f)))
    (a * tan(f) <= d) ? a / cos(f) : cd + sqrt(max(0, cd * cd - 2 * d * d + rc * rc));

function turm_ang(i) = TURM_A0 - TURM_SWEEP * i / TURM_STEPS;
function turm_z(i)   = TURM_ZTOP + (TURM_ZBOT - TURM_ZTOP) * i / TURM_STEPS;
function turm_pt(th) = let (r = turm_r(TURM_MID, TURM_MIDRC, th)) [r * cos(th), r * sin(th)];

// the ramp bar in cross-section: top face level with the groove's centre
module turm_bar_xsec() { translate([-TURM_W / 2, -TURM_T]) square([TURM_W, TURM_T + BORE_D / 2]); }

// the groove cutter: a Ø20 half-pipe, open upwards (hull keeps it convex for sweeping)
module turm_groove_xsec() {
  hull() {
    translate([0, BORE_D / 2]) circle(d = BORE_D);
    translate([-BORE_D / 2, BORE_D / 2]) square([BORE_D, 20]);
  }
}

// place a cross-section on the path at step i, square to the direction of travel
module turm_at(i) {
  th = turm_ang(i);
  p  = turm_pt(th);
  q  = turm_pt(turm_ang(i + 1));
  translate([p[0], p[1], turm_z(i)])
    rotate([0, 0, atan2(q[1] - p[1], q[0] - p[0]) + 90]) rotate([90, 0, 0])
      linear_extrude(height = 0.02, center = true) children();
}

// sweep a (convex) cross-section along the whole helix
module turm_sweep() {
  for (i = [0:TURM_STEPS - 1]) hull() {
    turm_at(i) children();
    turm_at(i + 1) children();
  }
}

// hub: a mini block that slides over the tower (chamfered 44 cube, Ø30 through hole)
module turm_hub() {
  difference() {
    cuboid([SIDE, SIDE, MINI_H], chamfer = CHAMFER, edges = "Z", anchor = BOTTOM);
    translate([0, 0, -EPS]) cylinder(h = MINI_H + 2 * EPS, d = SOCKET_D);
  }
}

// webs tying the ramp's inner edge back to the hub (also the print supports)
module turm_webs() {
  inner = TURM_MID - TURM_W / 2;                       // ramp inner edge (25)
  for (a = [90, 0, -90, -180]) {
    i = (TURM_A0 - a) / TURM_SWEEP * TURM_STEPS;
    h = turm_z(i) - TURM_T + EPS;
    rotate([0, 0, a])
      translate([(SIDE / 2 + inner) / 2 - 1, 0, h / 2])
        cube([inner - SIDE / 2 + 2, TURM_WEB, h], center = true);
  }
}

module spiral_ramp() {
  turm_hub();
  turm_webs();
  difference() {
    turm_sweep() turm_bar_xsec();
    turm_sweep() turm_groove_xsec();
  }
}

/* ---------------- accelerator ramp (red scoop wedge; not in quadri-plot) ---------------- */
// A slender scoop that sits on a rail and launches a falling marble horizontally: a
// tall rounded back tapering to a thin front lip, with a 14mm concave half-pipe channel
// running the sloped top (deep cradle at the back, opening over the lip). Modelled from
// the real Hape "little red ramp". One piece: closed base + a central hendidura that
// grips the rail. Proportions measured from the real part: 44 x 24 x 20.
ACCEL_L    = 44;   // length (thin lip at x=0 -> tall back at x=L)
ACCEL_HB   = 20;   // back height
ACCEL_WB   = 24;   // plan width at the back
ACCEL_WT   = 16;   // plan width at the front tip
ACCEL_GW   = 14;   // concave channel width
ACCEL_BASE = 3.5;  // solid base-plate thickness (closes the underside)

// solid wedge shell = side silhouette (extruded across the width) trimmed by the teardrop plan
module accel_shell() {
  intersection() {
    translate([0, SIDE / 2, 0]) rotate([90, 0, 0])
      linear_extrude(height = SIDE)
        polygon([[-2, 0], [ACCEL_L, 0], [ACCEL_L, ACCEL_HB - 4], [ACCEL_L - 4, ACCEL_HB],
                 [18, 17], [8, 6], [1, 4], [-2, 3]]);
    translate([0, 0, -5]) linear_extrude(height = 80)
      offset(r = 6) offset(r = -6)   // round the teardrop corners/ends
        polygon([[0, -ACCEL_WT / 2], [ACCEL_L, -ACCEL_WB / 2], [ACCEL_L, ACCEL_WB / 2], [0, ACCEL_WT / 2]]);
  }
}

module accelerator() {
  difference() {
    union() {
      difference() {
        accel_shell();
        // 14mm half-pipe channel, axis on the sloped top ridge -> open full length
        translate([21, 0, 12]) rotate([0, 90 - atan2(16, 38), 0])
          cylinder(h = 90, d = ACCEL_GW, center = true);
      }
      // solid base plate so the channel can't punch through the thin front lip
      intersection() {
        accel_shell();
        translate([0, 0, ACCEL_BASE / 2]) cube([200, 200, ACCEL_BASE], center = true);
      }
    }
    // rail hendidura: a blind groove in the underside at the back that grips the rail
    translate([ACCEL_L - 9, 0, ACCEL_BASE / 2]) cube([18, 8, ACCEL_BASE + EPS], center = true);
  }
}
