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

/* ---------------- pieces that need the parameters directly ---------------- */
// A piece file `use`s this library, and `use` imports modules but NOT variables, so
// anything that reads SIDE/MINI_H/... has to live here rather than in the piece file.

// thin landing connector (purple): top dish, bore through, stud underneath
module connector_funnel() {
  difference() {
    block_base(MINI_H);
    translate([0, 0, LOWEXIT]) cylinder(h = MINI_H - LOWEXIT + EPS, d = BORE_D);
  }
}

// quadri-plot MiniWhiteBlock: thin chamfered cube, straight Ø30 hole, no stud
module mini_white() {
  difference() {
    cuboid([SIDE, SIDE, MINI_H], chamfer = CHAMFER, edges = "Z", anchor = BOTTOM);
    translate([0, 0, -EPS]) cylinder(h = MINI_H + 2 * EPS, d = SOCKET_D);
  }
}

// the orange control knob on a side face (quadri-plot ControlBlock)
module control_knob() {
  rotate([0, 0, 90]) translate([SIDE / 2, 0, HEIGHT * 2 / 3]) rotate([0, 90, 0]) {
    translate([0, 0, 3]) cylinder(h = 4, r = 13);
    cylinder(h = 3, r = 4);
  }
}

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
MARBLE_D = 16;     // Quadrilla marble

// Edge breaks. The outer profile already carries CHAMFER (2 mm) on its four long arrises,
// but quadri-plot leaves the groove and the end faces square, which on a printed part is a
// genuinely sharp arris — this is a toy, so break them:
//   RAIL_C_IN   the groove's four long arrises, top and bottom
//   RAIL_C_END  the perimeter of the end faces, where the sweep is cut off
// The top pair of RAIL_C_IN is the surface the marble actually rides, so widening the seat
// changes where it sits: `rail_seat()` is the real contact half-width, and everything that
// depends on it (seat height, lip placement) is derived, not hard-coded.
RAIL_C_IN  = 0.8;
RAIL_C_END = 1.0;
RAIL_C_STEPS = 4;  // the end chamfer is a stepped approximation; 4 leaves 0.25 mm steps

/* ---- guard lips (the original's "Korrekturschiene") ---------------------------------
   The 8 mm groove on its own only holds the marble against ~0.44 g of side load, which
   in the R = 230 curve is 0.99 m/s — a free drop of barely 74 mm (1.2 blocks) before it
   climbs the outer edge and leaves the rail. The original has a raised lip either side
   for exactly that reason; this reproduces it.

   The lip is part of `rail_xsec()`, so it is swept by whatever path each piece uses —
   linear for the straight, `rotate_extrude` for the curves, both arcs of the S, and the
   split halves inherit it too. Nothing is per-piece.

   Section copied from the reference part: a 5 x 5 bar crowned with a shallow arc
   (0.94 mm rise -> R 3.79). Its inner face stands clear of the marble by LIP_GAP at
   the lip's own height, so it guards without ever touching a rolling marble.

   LIP = false gives the plain quadri-plot rail back. */
LIP      = true;
LIP_H    = 5;      // height above the rail top face
LIP_W    = 5;      // wall thickness
LIP_GAP  = 0.7;    // clearance to the marble, at z = RAIL_H + LIP_H
LIP_CROWN = 0.94;  // rise of the rounded top across LIP_W
LIP_CLR  = 26;     // lip is absent within this radius of a node (a 44 mm block seats there)
LIP_RAMP = 10;     // ...and ramps to full height over this much more
// How far the lip reaches from a node before it stops again. On the original the lip is
// not continuous: each bar carries two short runs, one near each node, with the middle of
// the span bare — on a 60 deg curve, ~37 mm blank, ~42 mm of lip, ~76 mm bare, then the
// mirror of that. 80 reproduces it (26..80 from the node, full height 36..70).
// 0, or anything past half the node spacing, gives one continuous lip — which is what the
// 180 mm straight gets, its nodes being only 136 apart. Continuous holds better; the
// default follows the original.
LIP_RUN  = 80;

// half-width of the two arrises the marble actually rides on: the groove wall is at
// GROOVE_W/2, but its top edge is chamfered away, so contact sits at the chamfer's outer lip
function rail_seat() = GROOVE_W / 2 + RAIL_C_IN;
// marble centre height above the rail top face, sitting in the groove
function marble_z() = sqrt(pow(MARBLE_D / 2, 2) - pow(rail_seat(), 2));
// half-width of the marble at the top of the lip -> where the lip's inner face may start
function lip_y0() = sqrt(pow(MARBLE_D / 2, 2) - pow(marble_z() - LIP_H, 2)) + LIP_GAP;
// crown radius from chord LIP_W and rise LIP_CROWN
function lip_cr() = (pow(LIP_W, 2) / 4 + pow(LIP_CROWN, 2)) / (2 * LIP_CROWN);

// one lip, spanning x = 0..LIP_W and y = 0..LIP_H
module lip_xsec() {
  intersection() {
    square([LIP_W, LIP_H]);
    translate([LIP_W / 2, LIP_H - lip_cr()]) circle(r = lip_cr(), $fa = 2);
  }
}

module chamfer_square(w, h, c = CHAMFER) {
  polygon([[c, 0], [w - c, 0], [w, c], [w, h - c], [w - c, h], [c, h], [0, h - c], [0, c]]);
}

// The groove cutter, centred on x = 0: GROOVE_W across the middle of the wall, opening out
// by RAIL_C_IN at both the top and the bottom face so neither arris comes out square.
module groove_cut(c = RAIL_C_IN) {
  hw = GROOVE_W / 2;
  polygon([[-hw - c, -1], [hw + c, -1],
           [hw + c, 0], [hw, c], [hw, RAIL_H - c], [hw + c, RAIL_H],
           [hw + c, RAIL_H + 1], [-hw - c, RAIL_H + 1],
           [-hw - c, RAIL_H], [-hw, RAIL_H - c], [-hw, c], [-hw - c, 0]]);
}

// 2D rail cross-section, centred on x = 0 (radius/height plane)
module rail_xsec(lip = LIP) {
  translate([-SIDE / 2, 0])
    difference() {
      chamfer_square(SIDE, RAIL_H);
      translate([SIDE / 2, 0]) groove_cut();
    }
  // the lip shares the plane z = RAIL_H with the rail top exactly — do not sink it by EPS,
  // or the node's clearance cone (which starts on that same plane) leaves a paper-thin
  // skirt and the union stops being one shell.
  if (lip)
    for (s = [-1, 1])
      translate([s > 0 ? lip_y0() : -(lip_y0() + LIP_W), RAIL_H])
        lip_xsec();
}

module rail_stud() { translate([0, 0, -STUD_H]) cylinder(h = STUD_H + 2, d = STUD_D); }

// node cut: top dish + through bore (marble drops through / a block stacks on top).
// With lips, also the cone that clears them off the node: a block resting on the node
// covers 44 x 44, so nothing may stand proud within LIP_CLR of it, and the cone widening
// upwards makes the lip rise back to full height over LIP_RAMP instead of as a step.
module rail_node_cut(lip = LIP) {
  translate([0, 0, RAIL_H - SOCKET_DEPTH]) cylinder(h = SOCKET_DEPTH + EPS, d = SOCKET_D);
  translate([0, 0, LOWEXIT]) cylinder(h = RAIL_H - LOWEXIT + 2 * EPS, d = BORE_D);
  if (lip)
    translate([0, 0, RAIL_H])
      cylinder(h = LIP_H + EPS, r1 = LIP_CLR, r2 = LIP_CLR + LIP_RAMP, $fa = 2);
}

// Clears the lip off the middle of a span, leaving the two runs near the nodes that the
// original has. `half` is the distance from here to either neighbouring node; the cone is
// the same trick as the node's, so the lip ramps down into the gap instead of stepping.
// Nothing happens when the span is too short for a gap — the lip just stays continuous.
module lip_mid_cut(half, lip = LIP) {
  r = half - LIP_RUN;
  if (lip && LIP_RUN > 0 && r > 0)
    translate([0, 0, RAIL_H])
      cylinder(h = LIP_H + EPS, r1 = r, r2 = r + LIP_RAMP, $fa = 2);
}

// straight-line distance from a 60 deg node to the middle of its span
function node_half_chord() = 2 * RAIL_R * sin(15);

// Breaks the perimeter of an end face, where the sweep is simply cut off. Intersect the
// finished rail with one of these per end. Local frame: the end plane is y = 0 and the body
// runs towards +y, which is the frame `project_arc` already puts you in on a curve.
//
// It is a stack of slabs, each the cross-section eroded by a shrinking amount, so the end
// face is inset by RAIL_C_END and grows to full over the same distance — a stepped 45°
// chamfer. A hull() would be simpler but the section is not convex (it has the groove), and
// a hull would fill it in. Past the chamfer the cutter is an open half-space, so it never
// clips the far end of an arc.
//
// The section is taken without the lip: eroding the union of rail + lip leaves the rail top
// at full height under the lip's footprint (that face is interior to the union), which would
// stand two proud tabs on the end face. No lip reaches an end anyway — the node's clearance
// cone keeps it 26 mm away and every end sits well inside that.
module rail_end_chamfer(c = RAIL_C_END, steps = RAIL_C_STEPS) {
  s = c / steps;
  for (i = [0:steps - 1])
    translate([0, i * s, 0])
      rotate([90, 0, 180])
        linear_extrude(height = s + EPS)
          offset(r = -(c - i * s))
            rail_xsec(lip = false);
  translate([-BIG, c, -BIG]) cube([2 * BIG, BIG, 2 * BIG]);
}

// quadri-plot ProjectAlongArc: place children at `a` degrees along the arc
module project_arc(a, d = 1) {
  translate([-RAIL_R * d, 0, 0]) rotate([0, 0, d * a]) translate([RAIL_R * d, 0, 0]) children();
}

// curved rail (angle = 60 or 120); studs + node cuts at each 60 deg node
module rail_curve(angle = 60, before = 5, after = 5, d = 1) {
  rad = d * RAIL_R;
  // Only a *free* end gets the chamfer. An arc asked for with no overhang (before or after
  // = 0) ends exactly on a node because it is meant to butt against its neighbour — that is
  // how the S-curve is built from two arcs, and how its halves meet. Chamfering there would
  // cut a V-groove right around the seam.
  intersection() {
    rail_curve_raw(angle, before, after, d);
    if (before > 0) project_arc(-before, d) rotate([0, 0, d > 0 ? 0 : 180]) rail_end_chamfer();
    if (after > 0) project_arc(angle + after, d) rotate([0, 0, d > 0 ? 180 : 0]) rail_end_chamfer();
  }
}

module rail_curve_raw(angle, before, after, d) {
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
    project_arc(30, d) lip_mid_cut(node_half_chord());
    if (angle > 60) project_arc(90, d) lip_mid_cut(node_half_chord());
  }
}

// S-curve: two 60 deg arcs (quadri-plot SCurve)
module rail_scurve() {
  rail_curve(60, before = 0);
  rotate([0, 0, 180]) rail_curve(60, before = 0);
}

// straight rail in the same style: nodes only at the two ends, straight groove between
module rail_straight(length = 180) {
  intersection() {
    rail_straight_raw(length);
    rotate([0, 0, -90]) rail_end_chamfer();
    translate([length, 0, 0]) rotate([0, 0, 90]) rail_end_chamfer();
  }
}

module rail_straight_raw(length) {
  inset = SIDE / 2;
  difference() {
    union() {
      rotate([90, 0, 90]) linear_extrude(height = length) rail_xsec();
      translate([inset, 0, 0]) rail_stud();
      translate([length - inset, 0, 0]) rail_stud();
    }
    translate([inset, 0, 0]) rail_node_cut();
    translate([length - inset, 0, 0]) rail_node_cut();
    translate([length / 2, 0, 0]) lip_mid_cut(length / 2 - inset);
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
JOINT_W0    = 3.5;   // width at the cut face  (with JOINT_CLEAR the pocket spans 15.8..21.2
JOINT_W1    = 5.0;   // width behind the face   from the centreline: clear of the node's Ø30
                     //                         socket inboard and of the rail edge outboard.
                     //                         Reaching the edge left a loose chamfer sliver.)
JOINT_D     = 9;     // how far the tenon reaches past the cut face
BIG         = 600;   // half-space cutter size

// the pair of dovetails at a cut face. `dir` is +1 to reach forward along the arc,
// -1 to reach back; `grow` inflates it into the female pocket; `over` extends it back
// behind the cut face so the male tenon overlaps its own half instead of merely touching
// it (touching at a plane leaves two separate shells).
module rail_tenon(dir = 1, grow = 0, over = 0) {
  for (s = [-1, 1])
    translate([s * JOINT_X, 0, -grow])
      linear_extrude(height = RAIL_H + 2 * grow)
        offset(delta = grow)
          polygon([[-JOINT_W0 / 2, -dir * over], [JOINT_W0 / 2, -dir * over],
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
          project_arc(at, d) rail_tenon(1, over = 0.05);
          rail_curve(angle, before, after, d);
        }
    }
    if (joint && !keep_near) project_arc(at, d) rail_tenon(1, JOINT_CLEAR);
  }
}

// The S-curve is already two 60 deg arcs meeting at the origin node, so each half is just
// one of them; the joint sits at that shared node.
//
// The arc itself stops dead on that node, but its stud does not: `rail_stud` is a whole
// Ø28 cylinder centred on the node, so half of it hangs 14 mm past the arc's end face. In
// the one-piece S the two arcs union and that is invisible; as two prints it means both
// halves carry the same stud and they cannot be put together. Trim each half on the node
// plane so it takes half the stud, and the two halves rebuild it between them.
module rail_s_half(keep_near = true, joint = JOINT) {
  rot = keep_near ? 0 : 180;
  rotate([0, 0, rot]) difference() {
    union() {
      difference() {
        rail_curve(60, before = 0);
        translate([0, -BIG / 2, 0]) cube(BIG, center = true);
      }
      if (joint && keep_near)
        intersection() {
          rail_tenon(-1, over = 0.05);
          translate([0, 0, RAIL_H / 2]) cube([SIDE, 2 * JOINT_D, RAIL_H], center = true);
        }
    }
    // The pocket reaches the other way from the tenon: this half is placed by a 180 deg
    // rotation, so the tenon that comes at it from the far half arrives on this half's +y
    // side. Mirroring the tenon's own direction here would cut the pocket into thin air.
    if (joint && !keep_near) rail_tenon(1, JOINT_CLEAR);
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

// Hub: a mini block that joins the tower like any other piece — stud underneath, socket
// on top, and a bore right through so a marble can also drop straight down the middle.
// The real part is built the same way (Ø30.5 socket above, hollow Ø29.5 stud below); an
// earlier version here was a plain ring with a through hole, which left the whole ramp
// with nothing to plug into and simply resting on the tower.
module turm_hub() {
  difference() {
    block_base(MINI_H);
    translate([0, 0, LOWEXIT]) cylinder(h = MINI_H - LOWEXIT + EPS, d = BORE_D);
  }
}

// Columns tying the ramp's inner edge back to the hub. The real part carries eight of
// them at staggered heights, following the ramp down; four left the long spans between
// unsupported.
module turm_webs() {
  inner = TURM_MID - TURM_W / 2;                       // ramp inner edge (25)
  for (a = [90, 45, 0, -45, -90, -135, -180, 22.5]) {
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

/* ---------------- skate ramp (the orange "Mega Skatepark" ramp) ---------------- */
// A long ramp that sags in the VERTICAL plane — a valley the marble runs down and up
// again, unlike the rails, which curve in plan. The marble sits down inside a channel
// with raised side walls rather than riding two bars, so the section is a cradle like
// the accelerator's. It hangs off a square mount on a snap-in hinge, so the same ramp
// serves towers of different heights, and seats on the grid at its low point.
//
// NOTE: unlike every other piece here, this one was not measured — the part was not to
// hand. Rather than scale guesses off a photo, the ramp is pinned to the system's own
// grid (below) and the arc falls out of that. Sanity check: the retail box is 300 mm
// long, and a 264 mm chord fits inside it.
// The run is a modular system, so the ramp is specified in whole blocks and the arc is
// derived from that, rather than the other way round: six block widths end to end, with
// the ends sitting exactly one block height above the middle. That way the tower at each
// end and the support under the middle all land on the grid.
SKATE_SPAN  = 6 * SIDE;    // 264 — end to end
SKATE_RISE  = HEIGHT;      // 60  — how far the ends sit above the low point
function skate_half()  = 2 * atan(2 * SKATE_RISE / SKATE_SPAN);   // half the swept angle
function skate_radius() = (SKATE_SPAN / 2) / sin(skate_half());
SKATE_R     = skate_radius();
SKATE_ANG   = 2 * skate_half();
SKATE_W     = 26;    // outside width
SKATE_H     = 14;    // section height
SKATE_CR    = 10.4;  // cradle radius (as the accelerator: the marble sits in it)
SKATE_DEPTH = 7;     // how deep the cradle is cut into the top face
// The top end is not rigid: the ramp hangs off a square mount by a hinge, so the same
// ramp works from towers of different heights. The mount is the same 44 x 44 ring as the
// set's stabiliser pieces, and the ramp carries a knuckle with two stub axles that snap
// into ears on the mount — two prints, no separate pin.
SKATE_PIN_D = 5;     // stub axle
SKATE_PIN_L = 3;     // how far each stub stands out
SKATE_EAR_T = 4;     // ear thickness
SKATE_CLR   = 0.35;  // hinge running clearance (tune on a test print)

// Section in (u, v): u runs down from the top face, v across the width. Swept about a
// horizontal axis, so -u is "up" and the cradle is cut into the u = 0 face.
module skate_xsec() {
  difference() {
    translate([0, -SKATE_W / 2]) square([SKATE_H, SKATE_W]);
    translate([SKATE_DEPTH - SKATE_CR, 0]) circle(r = SKATE_CR);
  }
}

// the sagging arc, low point at the origin
module skate_arc() {
  translate([0, 0, SKATE_R]) rotate([90, 0, 0]) rotate([0, 0, -90 - SKATE_ANG / 2])
    rotate_extrude(angle = SKATE_ANG, $fa = 1) translate([SKATE_R, 0]) skate_xsec();
}

// The flat landing at the top end: the arc arrives there at SKATE_ANG/2 from horizontal,
// so the tab is a separate horizontal flange rather than a continuation of the curve —
// it has to be level for a block's stud to drop through the bore.
// where the arc's top end sits, and the hinge axis on it
function skate_ex() = SKATE_R * sin(SKATE_ANG / 2);
function skate_ez() = SKATE_R * (1 - cos(SKATE_ANG / 2)) - SKATE_H / 2;

// The ramp's half of the hinge: a round knuckle closing off the top end, with a stub
// axle each side. Rounding it to SKATE_H/2 is what lets the ramp swing.
module skate_knuckle() {
  translate([skate_ex(), 0, skate_ez()]) rotate([90, 0, 0]) {
    cylinder(h = SKATE_W, r = SKATE_H / 2, center = true);
    for (s = [-1, 1])
      translate([0, 0, s * SKATE_W / 2]) cylinder(h = SKATE_PIN_L, d = SKATE_PIN_D);
  }
}

// The mount: the same 44 x 44 ring as the set's stabiliser pieces, so it stacks in a
// tower like any other block, with two ears standing proud of one face to take the
// hinge. A slot runs from the top of each ear down to its hole and is a little narrower
// than the axle, so the ramp snaps in by springing the ears apart and then stays put.
SKATE_EAR_L  = 18;   // how far the ears project past the ring
SKATE_EAR_X  = 10;   // hinge axis, measured out from the ring's face
SKATE_SNAP_W = 3.6;  // throat of the snap slot (< SKATE_PIN_D, so it grips)

module skate_mount() {
  gap = SKATE_W + 2 * SKATE_CLR;
  ax  = SIDE / 2 + SKATE_EAR_X;
  difference() {
    union() {
      cuboid([SIDE, SIDE, SKATE_H], chamfer = CHAMFER, edges = "Z", anchor = BOTTOM);
      for (s = [-1, 1])
        translate([SIDE / 2 - 6, s * (gap + SKATE_EAR_T) / 2, 0])
          cube([SKATE_EAR_L, SKATE_EAR_T, SKATE_H]);
    }
    translate([0, 0, -EPS]) cylinder(h = SKATE_H + 2 * EPS, d = SOCKET_D);   // the ring bore
    for (s = [-1, 1]) {
      translate([ax, s * (gap + SKATE_EAR_T) / 2, SKATE_H / 2]) rotate([-90, 0, 0])
        translate([0, 0, -1]) cylinder(h = SKATE_EAR_T + 2, d = SKATE_PIN_D + 2 * SKATE_CLR);
      // snap slot: straight up out of the hole, narrower than the axle
      translate([ax, s * (gap + SKATE_EAR_T) / 2 - EPS, SKATE_H / 2])
        cube([SKATE_SNAP_W, SKATE_EAR_T + 2 * EPS, SKATE_H], center = false);
    }
  }
}

// Underneath the low point of the curve the ramp needs a seat: the original rests its
// middle on a stack of the set's rings, and without something to locate on, a 268 mm
// span would just slide off. A flat pad with the standard Ø28 stud drops into the Ø30
// hole of a ring or the socket on a block's top, exactly as the rails' nodes do.
SKATE_PAD_D = 36;   // flat seat around the stud
SKATE_PAD_T = 3;

module skate_seat() {
  // start 1.5 mm inside the arc: its underside is a polygonal approximation and does not
  // quite reach -SKATE_H, so butting the pad against that height leaves them unfused
  z = -SKATE_H + 1.5;
  translate([0, 0, z]) {
    translate([0, 0, -SKATE_PAD_T]) cylinder(h = SKATE_PAD_T + EPS, d = SKATE_PAD_D);
    translate([0, 0, -SKATE_PAD_T - STUD_H]) cylinder(h = STUD_H + EPS, d = STUD_D);
  }
}

// The two parts laid out for printing: the ramp, and the mount beside it. They clip
// together by springing the ears over the stub axles.
module skate_ramp() {
  union() { skate_arc(); skate_knuckle(); skate_seat(); }
  // the mount printed alongside, positioned so its ears line up with the knuckle
  translate([skate_ex() - SIDE / 2 - SKATE_EAR_X, 0, skate_ez() - SKATE_H / 2 + 60])
    skate_mount();
}

/* ---------------- accelerator ramp (the red slope; not in quadri-plot) ---------------- */
// The little red slope that clips onto a rail and turns a marble's drop into speed
// along the level rail. The marble lands at the tall wide end (x=0) and runs down a
// Ø20.8 cradle to the low narrow tip. Underneath it is hollow, standing on two side
// walls plus a central foot that drops into the rail's 8 mm groove; the foot is split
// into two prongs so it can flex over the rail.
//
// Every number below was measured on the real part (41.25 x 22.83 x 20.69).
ACC_L     = 41.25;  // length, tall/wide entry at x=0 -> low/narrow tip at x=L
ACC_W0    = 22.83;  // width at the entry
ACC_W1    = 10.80;  // width at the tip
ACC_ZTOP  = 20.70;  // top of the side walls at the entry
ACC_ZC    = 24.85;  // cradle axis height at the entry (= floor 14.45 + ACC_R)
ACC_R     = 10.40;  // cradle radius (the marble rides in this groove)
ACC_TILT  = 12.5;   // slope of both the top and the cradle, degrees
ACC_BASE  = 4.50;   // the side walls stop here; below is open
ACC_SHELL = 2.00;   // material left under the cradle
ACC_WALL  = 1.90;   // side-wall thickness
ACC_FOOT_W = 7.70;  // central foot: matches the rail's 8 mm groove
ACC_FOOT_S = 2.60;  // slot splitting the foot into two prongs
ACC_FOOT_X0 = 2;    // the foot runs between these stations
ACC_FOOT_X1 = 38;

ACC_LIP   = 0.90;   // bullnose rounding on the top edge of the walls (the "labio")
ACC_STEPS = 200;   // sweep resolution (see README: needs a Manifold backend to be quick)

// half-width of the plan: a straight taper ending in a round nose
function acc_w(x) =
  let (r1 = ACC_W1 / 2, cx = ACC_L - r1, y0 = ACC_W0 / 2)
    (x <= cx) ? y0 + (r1 - y0) * x / cx
              : sqrt(max(0, r1 * r1 - (x - cx) * (x - cx)));
function acc_ztop(x) = ACC_ZTOP - tan(ACC_TILT) * x;   // top of the walls
function acc_zc(x)   = ACC_ZC   - tan(ACC_TILT) * x;   // cradle axis

// Height of the wall at its outer edge — near the tip the cradle, not the cap, decides it.
function acc_wallh(x) =
  let (w = acc_w(x), zc = acc_zc(x))
    ((w < ACC_R) ? zc - sqrt(ACC_R * ACC_R - w * w) : acc_ztop(x)) - ACC_BASE;

// Material left between the base and the bottom of the cradle: the floor that ties the
// two walls together. It thins towards the tip faster than the walls do.
function acc_floort(x) = acc_zc(x) - ACC_R - ACC_BASE;

// The bullnose has to shrink as the section thins out. Rounding a feature by more than
// half its thickness erodes it away completely, which would cut the tip off the ramp
// (wall) and, worse, dissolve the floor and leave the two walls as separate solids.
function acc_lip(x) =
  max(0, min(ACC_LIP, (acc_wallh(x) - 0.4) / 2, (acc_floort(x) - 0.4) / 2));

// The cross-section at station x. Rounding the finished outline is what gives the wall
// its bullnose top edge: on the real part the wall does not end in a sharp arris, it
// rolls over from the outer face into the cradle.
module acc_xsec(x) {
  w = acc_w(x); zt = acc_ztop(x); zc = acc_zc(x); lip = acc_lip(x);
  foot = (x >= ACC_FOOT_X0 && x <= ACC_FOOT_X1);
  offset(r = lip) offset(r = -lip)
    difference() {
      union() {
        difference() {
          translate([-w, ACC_BASE]) square([2 * w, zt - ACC_BASE]);
          difference() {                                   // hollow, leaving the shell
            translate([-(w - ACC_WALL), -20]) square([2 * (w - ACC_WALL), zc + 20]);
            translate([0, zc]) circle(r = ACC_R + ACC_SHELL);
          }
        }
        // Central foot, hanging to z=0. It stops at the cradle, not at the shell: near
        // the tip the shell circle drops below ACC_BASE, and cutting the foot there
        // would leave it floating clear of the body.
        if (foot) difference() {
          translate([-ACC_FOOT_W / 2, 0]) square([ACC_FOOT_W, zc]);
          translate([0, zc]) circle(r = ACC_R);
        }
      }
      translate([0, zc]) circle(r = ACC_R);                // the cradle
      if (foot) translate([-ACC_FOOT_S / 2, -1]) square([ACC_FOOT_S, ACC_BASE + 1]);
    }
}

// sweep the section along the length (section u -> y, v -> z, extrusion -> x)
module accelerator() {
  dx = ACC_L / ACC_STEPS;
  for (i = [0:ACC_STEPS - 1])
    translate([i * dx, 0, 0]) rotate([0, 0, 90]) rotate([90, 0, 0])
      linear_extrude(height = dx + 0.01) acc_xsec(i * dx + dx / 2);
}
