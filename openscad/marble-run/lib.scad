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

/* ---------------- marble catcher ---------------- */
// Sized by simulation, not by the photograph. sim/ scores a bowl by the only thing it is
// for — the fraction of marbles it keeps — and the numbers here are the best of a sweep
// over topology, diameter, rim height and depression depth. Retention over 1.2 to 2.4 m/s:
//
//   photo proportions, round, block on a boss beside it   Ø112 x 26   71 %   124 cm3
//   round, port, thin wall, shallow depression           Ø96  x 44   98 %    75 cm3
//   this: wedge                                          70->30 x 44 100 %    69 cm3
//
// Most of that 124 was the floor: a solid 11 mm disc under a depression that only needed to
// be 4 deep, and a 4 mm wall 41 tall. Halving the depression and thinning the wall took 29 %
// out with no retention cost at all. Going further does cost: a flat floor is 62 cm3 but
// only 88 %, so the depression is earning its 13 cm3.
//
// -D CATCH_D=112 -D CATCH_H=26 -D CATCH_DISH=5 -D CATCH_DISH_R=46 -D CATCH_SLOT_R=34
// -D CATCH_DOCK_H=26 puts the shallow photo-shaped bowl back.
// The moulded original rather than quadri-plot's plain ring-and-disc. Three things make it
// what it is:
//   - the floor is not flat. It falls away to a shallow central depression, so the marbles
//     roll to the middle and stay in a heap instead of scattering against the wall.
//   - a ring of radial slots around that depression.
//   - the rim is broken on one side by a saddle with two flared ears, where the run meets
//     the bowl. That gap is SIDE wide plus clearance, so it takes a 44 mm rail or block end.
//
// Proportions are read off a photograph of the real part, not measured, so they are all
// expressed against CATCH_D — change the diameter and the rest follows. The dock is the one
// thing pinned to the system grid, since it has to mate. The moulded-in branding on the
// original is deliberately not reproduced.
//
// The floor is left solid: a shell would want either a 15 deg unsupported ceiling or a
// pocket far too shallow to self-support, so the sensible place to hollow this out is the
// slicer's infill, not the model.
CATCH_D      = 96;    // outer diameter
CATCH_WALL   = 2.5;   // rim wall
CATCH_H      = 46;    // rim height above the table (the port sits 2 mm higher now)
CATCH_FLOOR  = 3;     // floor left under the deepest point of the depression
CATCH_DISH   = 4;     // how far the depression falls below the ledge round the wall
CATCH_DISH_R = 42;    // and where it starts
CATCH_EDGE   = 1.4;   // break on the rim edges
CATCH_FN     = 160;   // the file's $fn = 64 is far too coarse for a Ø112 revolve
CATCH_SLOTS  = 10;
CATCH_SLOT_R = 29;    // slot centres
CATCH_SLOT_L = 11;    // slot length, radial
CATCH_SLOT_W = 4.4;
CATCH_SLOT_A = 18;    // ...offset half a pitch so no slot lands on the dock

/* ---- the dock: the bowl is the base of the tower -------------------------------------
   The block does not stand beside the bowl, it plugs into it. On one side the rim grows
   into a 44 x 44 boss with the system's Ø30 socket in its top, exactly like the funnel
   connector, so a block seats on it with its stud and the run stacks up from there.

   That is what sets the boss height: a block's 60 deg side exit crosses its face at z 17.3
   above its own base, so the marble has to leave from above the rim to fall in. At
   CATCH_DOCK_H = CATCH_H the exit sits 17 mm clear of the rim and the marble lands in the
   middle of the depression, which is where you want it anyway.

   It also means the wall stays whole. The previous version cut a 46 mm mouth through the
   rim for the block to fire through, and sim/ showed that was where the retention went. */
// CATCH_DOCK_H picks the whole topology, and it is the one number that matters:
//   >= CATCH_H  the boss stands as tall as the rim, its inner face on the bowl's inner
//               wall, and the block seated on it overhangs the bowl and drops the marble
//               straight in. Simple, but the marble falls the full height of the boss.
//   <  CATCH_H  the boss is a low pad outside the wall and the marble comes in through a
//               port pierced through the wall at exit height. The wall stays whole above
//               and below it, the drop is only a few mm, and the pad costs a fraction of
//               the material. 0 -> the minimum a Ø30 socket can sit in.
CATCH_DOCK_H  = 0;
CATCH_PORT_W  = 26;    // the port, when there is one
// The port is sized by the trajectory, not by the marble. It arrives descending 30 deg, so
// crossing 4 mm of wall it drops another 2.3 — size it for the marble alone and it clips
// the bottom lip on the way in, which cost 17 points of retention when it was tried at 20.
CATCH_PORT_H  = 26;
CATCH_PORT_R  = 5;     // corner radius
CATCH_PAD_WELD = 8;    // how far the pad reaches back inside the wall to weld to it
CATCH_BLEND    = 10;   // fillet where the boss runs into the bowl; 0 leaves the bare crease
// The top of the wall can lean inwards. Both surfaces lean together so the wall keeps its
// thickness, which means it costs nothing — it removes a little — and a marble coming up
// the wall meets a face pointing back into the bowl instead of an open rim. At 45 deg it
// is self-supporting, so it prints without help.
CATCH_LIP     = 8;
// How much narrower the bowl is at the floor than at the rim. The idea was that a tapered
// wall does the gathering the depression is carved out of a solid floor to do, so the floor
// could go thin and the two features stop being paid for twice — 55 cm3 against 75.
//
// It does not work, and the simulator is clear about why: a wall that flares outwards as it
// rises leans *away* from a marble coming up it, so it launches rather than returns. 24 % to
// 60 % retention against 98 %. Retention wants the opposite — the wall leaning back over the
// bowl, which is what CATCH_LIP does. Left in, at 0, so the dead end stays reproducible.
CATCH_TAPER   = 0;

/* ---- an alternative plan: the wedge ------------------------------------------------
   A round bowl is an arena. The marble comes in on one line and crosses the whole
   diameter, so most of the floor is never used and the far wall has to be tall enough to
   survive being hit head-on at full speed.

   The wedge puts the marble into a V instead. It enters at the wide end and runs into two
   converging walls, which take it much better than one flat wall does — a corner cannot be
   ricocheted off cleanly. If that works, the footprint can shrink, and the floor is half
   the material in this part.

   A circle is perimeter-optimal, so this cannot win on wall for the same floor area (a
   square costs 13 % more, a hexagon 5 %). It can only win by needing less floor. */
CATCH_SHAPE   = "wedge";   // "wedge" | "round"
CATCH_W_MOUTH = 70;        // width at the entry
CATCH_W_TIP   = 30;        // and at the V
CATCH_W_LEN   = 90;        // between their centres
CATCH_VANE_R  = 14;    // deflector: radius the marble's centre is turned on
CATCH_VANE_A  = 60;    //            and through how much
CATCH_VANE_T  = 3;     //            wall thickness
CATCH_VANE_H  = 0;     //            0 -> none. With the marble now dropping into the middle
                       //            rather than fired across, it has nothing to deflect
CATCH_VANE_X  = 44;    //            where its face meets the incoming line
CATCH_VANE_S  = -1;    //            which way round the bowl it sends the marble

function catch_ri() = CATCH_D / 2 - CATCH_WALL;
// A whole MINI_H, which is exactly a white spacer. The boss is what decides where the
// tower standing on it starts, so it has to be a system height or the run cannot be
// levelled against anything else: heights in this set are sums of 60 and 12, and the
// 10 mm this used to be (socket depth plus a bit) is neither.
function catch_dock_h() = CATCH_DOCK_H > 0 ? CATCH_DOCK_H : MINI_H;
function catch_ported() = catch_dock_h() < CATCH_H;
// where the block's stud goes. A boss as tall as the rim puts the block's face on the
// bowl's inner wall, so it overhangs and drops the marble straight in; a low pad has to
// stand the block clear of the rim, and the marble comes in through the port instead.
function catch_dock_x() = (catch_ported() ? CATCH_D / 2 + 1 : catch_ri()) + SIDE / 2;
// a block's 60 deg side exit crosses its face this far above its own base
function catch_exit_z() = catch_dock_h() + 17.3;
// outer radius at height z, once the wall is allowed to taper
function catch_r_at(z) = CATCH_D / 2 - CATCH_TAPER
                       + CATCH_TAPER * min(z, CATCH_H - max(CATCH_LIP, EPS))
                         / (CATCH_H - max(CATCH_LIP, EPS));
// the deflector's face is the outer wall of the marble's turn, so it stands off the
// incoming centreline by the marble's radius
function catch_vane_rf() = CATCH_VANE_R + MARBLE_D / 2;
// the floor. A wedge has no depression carved into it — the V does that job — so its floor
// is just the minimum printable slab
function catch_ledge(shape = CATCH_SHAPE) = CATCH_FLOOR + (shape == "wedge" ? 0 : CATCH_DISH);
// sphere whose cap is CATCH_DISH deep across CATCH_DISH_R: it meets the ledge tangentially,
// so the depression blends into the floor with no step to trip a marble
function catch_dish_r() = (pow(CATCH_DISH_R, 2) + pow(CATCH_DISH, 2)) / (2 * CATCH_DISH);

// The bowl's outside. The dock is unioned to this and the cavity subtracted afterwards, so
// wherever the two meet the dock simply inherits the bowl's wall — no chord bitten out of
// the inside, and nothing to weld by hand.
module catch_envelope() {
  ro = CATCH_D / 2;
  e = CATCH_EDGE;
  rotate_extrude($fn = CATCH_FN)
    let(rb = ro - CATCH_TAPER, t = max(CATCH_LIP, e))
      polygon([[0, 0], [rb - e, 0], [rb, e], [ro, CATCH_H - t],
               [ro - t, CATCH_H], [0, CATCH_H]]);
}

// The inside: everything above the floor ledge, with the rim's inner edge broken.
module catch_cavity(shape = CATCH_SHAPE) {
  ri = catch_ri();
  e = CATCH_EDGE;
  h = max(CATCH_H, catch_dock_h()) + 10;
  led = catch_ledge(shape);
  rotate_extrude($fn = CATCH_FN)
    let(rib = ri - CATCH_TAPER, t = max(CATCH_LIP, e))
      polygon([[0, led], [rib, led], [ri, CATCH_H - t],
               [ri - t, CATCH_H], [ri - t, h], [0, h]]);
}

// The depression: the arc revolved, rather than a sphere clipped to a cylinder. A sphere of
// this radius needs a huge $fn before its polar facet stops being a visible flat spot, and
// all of it outside CATCH_DISH_R would be thrown away anyway. The profile stops at
// CATCH_DISH_R, where it is tangent to the ledge, so there is no step to trip a marble.
module catch_dish(steps = 32) {
  R = catch_dish_r();
  rotate_extrude($fn = CATCH_FN)
    polygon(concat([for (i = [0:steps])
                     let(r = CATCH_DISH_R * i / steps)
                       [r, CATCH_FLOOR + R - sqrt(R * R - r * r)]],
                   [[0, CATCH_FLOOR + CATCH_DISH]]));   // capped at the ledge: above it
                                                       // the cavity has already gone, and
                                                       // running it to the rim ate the lip
}

module catch_slots() {
  for (i = [0:CATCH_SLOTS - 1])
    rotate([0, 0, i * 360 / CATCH_SLOTS + CATCH_SLOT_A])
      translate([CATCH_SLOT_R, 0, -EPS])
        linear_extrude(height = CATCH_H)
          hull() for (s = [-1, 1])
            translate([s * (CATCH_SLOT_L - CATCH_SLOT_W) / 2, 0]) circle(d = CATCH_SLOT_W);
}

// The boss, chamfered on its vertical edges like every block in the set. A low pad is run
// back to the bowl's inner radius: standing it where the block needs to be leaves it
// touching a cylinder along one line, which is no join at all — it came out as a second
// loose body.
function catch_dock_x1() = catch_dock_x() + SIDE / 2;
function catch_dock_x0() = catch_ported() ? catch_r_at(catch_dock_h()) - CATCH_PAD_WELD
                                          : catch_dock_x() - SIDE / 2;

// the boss in plan, chamfered on its corners like every block in the set
module catch_dock_plan() {
  x0 = catch_dock_x0();
  x1 = catch_dock_x1();
  c = CHAMFER;
  polygon([[x0 + c, -SIDE / 2], [x1 - c, -SIDE / 2], [x1, -SIDE / 2 + c],
           [x1, SIDE / 2 - c], [x1 - c, SIDE / 2], [x0 + c, SIDE / 2],
           [x0, SIDE / 2 - c], [x0, -SIDE / 2 + c]]);
}

module catch_dock() { linear_extrude(height = catch_dock_h()) catch_dock_plan(); }

// The outside of the bowl in plan at height z — the same profile the body is built from,
// so a slice taken here lands exactly on its surface.
module catch_shell_plan(z, shape = CATCH_SHAPE) {
  e = CATCH_EDGE;
  t = max(CATCH_LIP, e);
  s = z < e ? e - z : (z > CATCH_H - t ? z - (CATCH_H - t) : 0);
  if (shape == "wedge") catch_plan(s);
  else circle(r = catch_r_at(z) - s, $fn = CATCH_FN);
}

// The fillet where the boss meets the bowl. A cylinder run into a box leaves two live
// re-entrant creases; a morphological closing in plan — dilate by the radius, erode back —
// fills exactly those and leaves every convex corner untouched, which is what a fillet is.
// Trimmed to a collar around the boss. Untrimmed, the closing's outline runs along the
// wall's outside for the whole perimeter, coincident with the wall's own face, and the
// union of two solids sharing a face that long comes back with a 0.01 mm shard down it.
// The fillet itself never reaches further than CATCH_BLEND from the boss.
// $fn on the offsets, not the file's: offset() rounds with the resolution in scope, and at
// the file's 64 a 10 mm fillet arc came out with 0.12 mm sagitta against the wall's 0.011.
// Geometrically tangent, visibly ten times coarser than the surface it runs into.
module catch_blend_plan(z, shape) {
  intersection() {
    offset(r = -CATCH_BLEND, $fn = CATCH_FN) offset(r = CATCH_BLEND, $fn = CATCH_FN) {
      catch_shell_plan(z, shape);
      catch_dock_plan();
    }
    offset(r = CATCH_BLEND + 1, $fn = CATCH_FN) catch_dock_plan();
  }
}

// Most of the wall is prismatic and gets one solid; only where it leans inwards at the top
// does the fillet have to follow it, and only then if the boss reaches that high.
//
// Sweeping the whole height in slabs instead looks the same and is not: in the prismatic
// band every slab has the same section, and each joint between two of them came out as a
// two- or three-triangle shard. 121 of them on the wedge, and the part stopped being closed.
module catch_blend(shape = CATCH_SHAPE, step = 0.25) {
  h = catch_dock_h();
  zlean = CATCH_H - max(CATCH_LIP, CATCH_EDGE);
  // only worth following if there is a real lip up there; when all that is above zlean is
  // the top edge break, running the prism through it beats paying for slabs and their joints
  zs = (h - zlean > CATCH_EDGE) ? zlean : h;
  if (CATCH_BLEND > 0) {
    linear_extrude(height = zs) catch_blend_plan(zs / 2, shape);
    if (h > zlean) {
      n = max(1, ceil((h - zlean) / step));
      dz = (h - zlean) / n;
      for (i = [0:n - 1])
        translate([0, 0, zlean + i * dz])
          linear_extrude(height = dz + EPS)
            catch_blend_plan(zlean + i * dz + dz / 2, shape);
    }
  }
}

module catch_dock_socket() {
  translate([catch_dock_x(), 0, catch_dock_h() - SOCKET_DEPTH])
    cylinder(h = SOCKET_DEPTH + EPS, d = SOCKET_D);
}

// The port: a rounded window through the wall on the marble's line, only where the marble
// actually passes. Everything above and below it is still wall, which is the whole point.
module catch_port() {
  if (catch_ported())
    translate([catch_r_at(catch_exit_z()) - CATCH_WALL - 2, 0, catch_exit_z()])
      rotate([0, 90, 0])
        linear_extrude(height = CATCH_WALL + 6)
          offset(r = CATCH_PORT_R)
            square([CATCH_PORT_H - 2 * CATCH_PORT_R, CATCH_PORT_W - 2 * CATCH_PORT_R],
                   center = true);
}

// Optional deflector, kept parametric but off: see sim/. The band has to be built closed —
// out along the face and back along the outside. Handing offset() the bare arc gives it a
// polyline of zero area and what comes back is rubbish.
module catch_vane_band(steps = 32) {
  rf = catch_vane_rf();
  a0 = -90 * CATCH_VANE_S;
  function a(i) = a0 - CATCH_VANE_S * CATCH_VANE_A * i / steps;
  translate([CATCH_VANE_X, CATCH_VANE_S * CATCH_VANE_R]) {
    polygon(concat([for (i = [0:steps]) rf * [cos(a(i)), sin(a(i))]],
                   [for (i = [steps:-1:0]) (rf + CATCH_VANE_T) * [cos(a(i)), sin(a(i))]]));
    for (i = [0, steps])
      translate((rf + CATCH_VANE_T / 2) * [cos(a(i)), sin(a(i))]) circle(d = CATCH_VANE_T, $fn = 32);
  }
}

module catch_vane_plan(grow = 0) { offset(r = grow) catch_vane_band(); }

module catch_vane() {
  c = 0.8;
  intersection() {
    union() {
      linear_extrude(height = CATCH_VANE_H - c) catch_vane_plan();
      linear_extrude(height = CATCH_VANE_H) catch_vane_plan(-c);
    }
    cylinder(h = CATCH_VANE_H, r = catch_ri(), $fn = CATCH_FN);
  }
}

// the wedge in plan: convex, so every edge break below can be a hull of two prisms
module catch_plan(shrink = 0) {
  offset(r = -shrink)
    hull() {
      translate([CATCH_D / 2 - CATCH_W_MOUTH / 2, 0]) circle(d = CATCH_W_MOUTH, $fn = 64);
      translate([CATCH_D / 2 - CATCH_W_MOUTH / 2 - CATCH_W_LEN, 0])
        circle(d = CATCH_W_TIP, $fn = 64);
    }
}

module catch_wedge_lean(shrink, lip) {
  translate([0, 0, CATCH_H - lip]) hull() {
    linear_extrude(height = EPS) catch_plan(shrink);
    translate([0, 0, lip]) linear_extrude(height = EPS) catch_plan(shrink + lip);
  }
}

module catch_wedge_body() {
  e = CATCH_EDGE;
  lip = max(CATCH_LIP, e);
  hull() {
    linear_extrude(height = EPS) catch_plan(e);
    translate([0, 0, e]) linear_extrude(height = CATCH_H - lip - e) catch_plan();
  }
  catch_wedge_lean(0, lip);
}

module catch_wedge_cavity(shape = "wedge") {
  lip = max(CATCH_LIP, CATCH_EDGE);
  w = CATCH_WALL;
  led = catch_ledge(shape);
  translate([0, 0, led]) linear_extrude(height = CATCH_H - lip - led + EPS) catch_plan(w);
  catch_wedge_lean(w, lip);
  translate([0, 0, CATCH_H]) linear_extrude(height = 20) catch_plan(w + lip);
}

// The round bowl on demand, whatever CATCH_SHAPE says — the shape the Quadrilla original
// has, carrying the same work the wedge got: port entry, socket dock, thin wall, the
// depression and the ring of slots.
module marble_catcher_round() { marble_catcher("round"); }

module marble_catcher(shape = CATCH_SHAPE) {
  union() {
    difference() {
      union() {
        if (shape == "wedge") catch_wedge_body(); else catch_envelope();
        catch_dock();
        catch_blend(shape);
      }
      if (shape == "wedge") catch_wedge_cavity(shape); else catch_cavity(shape);
      if (shape != "wedge") { catch_dish(); catch_slots(); }
      catch_dock_socket();
      catch_port();
    }
    if (CATCH_VANE_H > 2) catch_vane();
  }
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
// NEARLY THERE -- still do not print. sim/spiralramp.py seats a block on the hub, drops a
// marble in, and the marble now leaves the block, runs the whole 270 deg, and arrives over
// the neighbouring column: 8 of 8 runs, across two tower heights, two restitutions and two
// frictions. It was 0 of 24 an hour ago and the old ramp could not get the marble out of
// the block at all.
//
// What is left: it comes to rest about 10 deg short of the channel's end, at radius 42
// against a target of 44, instead of running off and dropping into the column below. The
// stop is at the same millimetre in every run and does not move when the slope is changed,
// so it is geometry, not lost energy -- almost certainly a third instance of the lamina
// described below, at the point where the tail's curvature peaks.
//
// The lamina is the lesson of this piece. Sweeping by hulling pairs of sections means the
// hulled GROOVE can sit inside the hulled BAR wherever the path turns, leaving a paper-thin
// wall of uncut material on the inside of the turn. It is invisible in a render and it
// stops a marble dead. It appeared at the entry (0.3 mm at x=22, right across the block's
// exit) and again at the helix-to-spur junction, and both went away once the turn was made
// smooth instead of sharp. A sweep that interpolates the section properly, rather than
// hulling, would end the whole class.
//
// A helical ramp wrapping a tower: the marble leaves the side exit of the block above,
// spirals down 270 deg around it, and is put down on the axis of the NEXT COLUMN one grid
// pitch away. What it does is shift the run sideways while it descends.
//
// The previous version connected at neither end and is described in full in the README.
// Three numbers here come straight out of fixing that:
//
//   HUB 24, not 12.  The hub sets how high the feeding block sits, and that sets the whole
//   height budget. At 12 the channel has 8.5 mm to descend over 202 mm of path -- 2.45 deg,
//   and a ball in a groove stalls near 3. At 24 it gets 5.3 deg.
//
//   ENTRY AZIMUTH is a parameter, and it is 0.  The old entry sat at 90, which of the nine
//   blocks only `red` can feed. That was never a real constraint: the stud is round, the
//   socket is round and all four faces are at 22, so a block drops in at any of four
//   rotations and the builder aims its exit. Any block with a 60 deg side exit works.
//
//   THE EXIT REACHES 44.  The helix radius is 36.5, which is nowhere -- it is past the
//   neighbouring block's face and short of its axis. A short radial spur takes it out to a
//   full grid pitch so the marble drops into that column's top bore.
TURM_HUB_H = 2 * MINI_H;   // 24
TURM_A0    = 0;            // entry azimuth; any face, the builder rotates the block to suit
TURM_SWEEP = 270;          // degrees swept while descending
TURM_A     = 48;           // outer half-width (96 footprint, as the real part)
TURM_RC    = 25;           // outer corner radius
TURM_MID   = 36.5;         // channel centreline half-width
TURM_MIDRC = 13.5;         // centreline corner radius
TURM_W     = 23;           // bar width
TURM_T     = 3;            // floor under the groove
TURM_LEAD  = 75;           // degrees over which the channel spirals out to meet the helix
TURM_WALL  = 15;           // channel wall above the floor. The half-pipe alone leaves only
                           // 2 mm standing above the marble's centre and it climbs straight
                           // out: simulated, it flew off the ramp in 13 of 16 runs.
TURM_ZBOT  = 4;            // floor at the end of the helix
TURM_TAIL  = 60;           // degrees over which the channel spirals back OUT to the next
                           // column's axis. A straight radial spur butted onto the helix
                           // meets it at a right angle, and sweeping by hulls leaves an
                           // uncut lamina in the inside of any sharp turn -- the marble
                           // stopped dead on it, at the same millimetre whatever the spur's
                           // slope. The entry had the identical fault. No kinks anywhere.
TURM_OUT   = SIDE;         // the exit spur reaches the next column's axis
TURM_STEPS = 120;
TURM_WEB   = 8;

// a marble sits this far above the channel floor: the half-pipe's radius is BORE_D/2 and
// the ball's centre orbits at (BORE_D - MARBLE_D)/2 about its axis, so it lands on MARBLE_D/2
function turm_seat()   = MARBLE_D / 2;
// where the block above puts the marble's centre as it crosses its own face
function turm_feed_z() = TURM_HUB_H + 15;
// so the channel starts right there, at the face -- not out at the helix radius. Left to
// meet the marble only after it had crossed the 14.5 mm gap, the entry has to sit low
// enough to catch a 13 mm fall, and then there is no height left to descend in.
// The channel starts ON the block's face. Standing it half a channel width further out
// looks safer and is wrong: a swept section is a plate square to the DIRECTION OF TRAVEL,
// and at the entry that direction is radial, so the 23 mm of width lies tangentially and
// none of it reaches into the block. Setting the start at 33.5 for clearance it did not
// need simply left a 10 mm hole between the block's face and the channel, and the marble
// dropped through it -- measured: no material at all between radius 23 and 30.5.
function turm_r0()     = SIDE / 2;
function turm_ztop()   = turm_feed_z() - turm_seat();

// radius of a rounded square (half-width a, corner radius rc) at angle th
function turm_fold(th) = let (m = ((th % 90) + 90) % 90) (m > 45 ? 90 - m : m);
function turm_r(a, rc, th) =
  let (f = turm_fold(th), d = a - rc, cd = d * (cos(f) + sin(f)))
    (a * tan(f) <= d) ? a / cos(f) : cd + sqrt(max(0, cd * cd - 2 * d * d + rc * rc));

function turm_ang(i) = TURM_A0 - TURM_SWEEP * i / TURM_STEPS;
function turm_z(i)   = turm_ztop() + (TURM_ZBOT - turm_ztop()) * i / TURM_STEPS;
// The lead: the radius grows from the block's face to the helix over TURM_LEAD degrees, as
// a square root so that dr/dth is steep at the very start. That makes the channel leave the
// face almost radially -- along the marble's own line -- and turn tangential by itself. A
// straight radial spur butted onto the helix would meet it at a right angle instead.
function turm_leadf(th) = let (d = (TURM_A0 - th) / TURM_LEAD)
  (d >= 1) ? 1 : (d <= 0 ? 0 : sqrt(d));
function turm_tailf(th) = let (e = TURM_A0 - TURM_SWEEP, d = (e + TURM_TAIL - th) / TURM_TAIL)
  (d <= 0) ? 0 : ((d >= 1) ? 1 : d * d);
function turm_rad(th) =
  let (base = turm_r0() + (turm_r(TURM_MID, TURM_MIDRC, th) - turm_r0()) * turm_leadf(th))
    base + (TURM_OUT - base) * turm_tailf(th);
function turm_pt(th) = let (r = turm_rad(th)) [r * cos(th), r * sin(th)];

// the ramp bar in cross-section: top face level with the groove's centre
module turm_bar_xsec() { translate([-TURM_W / 2, -TURM_T]) square([TURM_W, TURM_T + TURM_WALL]); }

// the groove cutter: a Ø20 half-pipe, open upwards (hull keeps it convex for sweeping)
module turm_groove_xsec() {
  hull() {
    translate([0, BORE_D / 2]) circle(d = BORE_D);
    translate([-BORE_D / 2, BORE_D / 2]) square([BORE_D, 20]);
  }
}

// place a cross-section at a point, square to a direction of travel
module turm_place(pt, dir, z) {
  translate([pt[0], pt[1], z]) rotate([0, 0, dir + 90]) rotate([90, 0, 0])
    linear_extrude(height = 0.02, center = true) children();
}

module turm_at(i) {
  p = turm_pt(turm_ang(i));
  q = turm_pt(turm_ang(i + 1));
  turm_place(p, atan2(q[1] - p[1], q[0] - p[0]), turm_z(i)) children();
}

// sweep a (convex) cross-section along the helix, then out along the exit spur
module turm_sweep() {
  for (i = [0:TURM_STEPS - 1]) hull() {
    turm_at(i) children();
    turm_at(i + 1) children();
  }
}

// Hub: a mini block that joins the tower like any other piece -- stud underneath, socket on
// top, bore right through. Two mini heights tall, which is what buys the channel its slope.
module turm_hub() {
  difference() {
    block_base(TURM_HUB_H);
    translate([0, 0, LOWEXIT]) cylinder(h = TURM_HUB_H - LOWEXIT + EPS, d = BORE_D);
  }
}

// Columns tying the ramp's inner edge back to the hub. Each runs from the HUB's radius at
// its own angle to the RAMP's inner radius at that same angle. Fixed x limits were the old
// bug: the hub is a square reaching 31.1 at a corner while the ramp retreats to 34.5, so
// every corner web was buried inside the hub and held nothing.
module turm_webs() {
  for (k = [0:7]) {
    a  = TURM_A0 - TURM_SWEEP * (k + 0.5) / 8;
    r0 = turm_r(SIDE / 2, CHAMFER, a) - 1;              // out of the hub
    r1 = turm_rad(a) - TURM_W / 2 + 1;                       // into the ramp's inner edge
    i  = (k + 0.5) / 8 * TURM_STEPS;
    h  = turm_z(i) - TURM_T + EPS;
    if (r1 > r0)
      rotate([0, 0, a]) translate([(r0 + r1) / 2, 0, h / 2])
        cube([r1 - r0, TURM_WEB, h], center = true);
  }
}

// The mouth. The channel is a closed trough with a wall on BOTH sides, and at the entry
// its inner wall stands at the block's own face, straight across the exit hole -- a plate
// in front of the door. Simulated with that wall in place the marble jammed inside the
// block in all 24 runs. This cuts a radial channel through it, on the marble's own line and
// descending at the 30 deg it is already falling at, so it rolls out of the block and into
// the groove instead of hitting a wall.
// It runs at CONSTANT height, from inside the block's face out to where the lead has
// turned tangential. Sloping it down instead carves the bar's floor away with it, and the
// marble drops through the hole that leaves.
TURM_MOUTH = 30;   // how far out the mouth reaches
module turm_mouth() {
  a = TURM_A0;
  hull() for (r = [SIDE / 2 - 2, TURM_MOUTH])
    turm_place([r * cos(a), r * sin(a)], a, turm_ztop()) turm_groove_xsec();
}

module spiral_ramp() {
  turm_hub();
  turm_webs();
  difference() {
    turm_sweep() turm_bar_xsec();
    turm_sweep() turm_groove_xsec();
    turm_mouth();
    // Trim everything above the hub back to the block's own footprint. A swept section is
    // placed at a station and hulled to the next, and that hull reaches slightly inward of
    // where the station sits -- measured, the channel's floor poked to x=20.7 against a
    // face at 22, a 1.3 mm ledge sitting exactly in the mouth of the block's exit bore. The
    // marble rolled down the bore, met it, and stopped, in all 16 runs. Nothing of the ramp
    // belongs inside the block.
    translate([0, 0, TURM_HUB_H])
      linear_extrude(height = HEIGHT) offset(delta = 0.1) square([SIDE, SIDE], center = true);
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
SKATE_EAR_T = 4;     // ear thickness
SKATE_PIN_L = SKATE_EAR_T;   // stub reaches flush with the ear's outer face
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
    // cylinder() always grows in +z, so the -z stub has to be dropped by its own length
    // first — without that it grew back into the knuckle and only one stub existed.
    for (s = [-1, 1])
      translate([0, 0, s * SKATE_W / 2 - (s < 0 ? SKATE_PIN_L : 0)])
        cylinder(h = SKATE_PIN_L, d = SKATE_PIN_D);
  }
}

// The mount: the same 44 x 44 ring as the set's stabiliser pieces, so it stacks in a
// tower like any other block, with two ears standing proud of one face to take the
// hinge. A slot runs from the top of each ear down to its hole and is a little narrower
// than the axle, so the ramp snaps in by springing the ears apart and then stays put.
SKATE_EAR_X   = 10;  // hinge axis, measured out from the ring's face
SKATE_EAR_WELD = 6;  // how far the ear reaches back into the ring, to weld to it
SKATE_EAR_END = 8;   // and how much material stands outboard of the axis: this is the arm
                     // that springs, so it is what sets the snap force
SKATE_EAR_L  = SKATE_EAR_WELD + SKATE_EAR_X + SKATE_EAR_END;   // 24
SKATE_SNAP_W = 3.6;  // throat of the snap slot (< SKATE_PIN_D, so it grips)

module skate_mount() {
  gap = SKATE_W + 2 * SKATE_CLR;
  ax  = SIDE / 2 + SKATE_EAR_X;
  ey  = (gap + SKATE_EAR_T) / 2;    // each ear's mid-plane
  difference() {
    union() {
      cuboid([SIDE, SIDE, SKATE_H], chamfer = CHAMFER, edges = "Z", anchor = BOTTOM);
      // ears placed about their mid-plane. Growing them in +y from s*ey instead put the
      // pair 2 mm off centre and the ramp fouled the -y ear.
      for (s = [-1, 1])
        translate([SIDE / 2 - SKATE_EAR_WELD, s * ey - SKATE_EAR_T / 2, 0])
          cube([SKATE_EAR_L, SKATE_EAR_T, SKATE_H]);
    }
    translate([0, 0, -EPS]) cylinder(h = SKATE_H + 2 * EPS, d = SOCKET_D);   // the ring bore
    for (s = [-1, 1]) {
      translate([ax, s * ey, SKATE_H / 2]) rotate([90, 0, 0])
        cylinder(h = SKATE_EAR_T + 2, d = SKATE_PIN_D + 2 * SKATE_CLR, center = true);
      // snap slot: straight up out of the hole, narrower than the axle. Centred on the
      // bore — grown from it in +x, the throat sat beside the axle instead of over it.
      translate([ax, s * ey, SKATE_H])
        cube([SKATE_SNAP_W, SKATE_EAR_T + 2, SKATE_H], center = true);
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

/* ---------------- seesaw (Wippe): a tipping cup on a balance arm ---------------- */
// A plain seesaw — a trough pivoted at its middle that a marble runs along — cannot work,
// and it is worth writing down why, because it is the obvious thing to build. Whichever
// end is up at rest, the marble has to travel *outward along that end* to tip it, and that
// is uphill. Whichever end is down, the marble reaches it without changing any moment. So
// the marble can never move from a non-tipping position to a tipping one under gravity.
//
// The mechanism that does work drops the marble into a cup at the end of the raised arm.
// A counterweight holds that end up; the loaded arm swings down; and once the arm passes
// level the cup's floor tips the other way and the marble rolls out of its open end. The
// empty arm then rides back up. Everything below follows from that.
//
// The marble is glass, 5.36 g, and the arm is PLA and much heavier, so the design rule is
// that the arm must be *balanced about its pivot except for the counterweight*: then the
// arm's own mass only adds inertia, and the marble has to beat the counterweight alone.
SEE_BASE_H   = 2 * MINI_H;   // 24 — the mount stacks on the system's grid
SEE_PIVOT_Z  = 22;           // pivot, above the mount's top face
SEE_UP       = 12;           // rest tilt, cup end up
SEE_DOWN     = 10;           // and at the bottom stop
SEE_ARM_W    = 9;
SEE_ARM_H    = 11;           // section enough to carry the Ø5 axle
SEE_CUP_C    = 40;           // The feed is fixed by the grid — the column next door, one
                             // 44 mm pitch out — so it is the tray that gets positioned to
                             // catch it, not the other way round. Simulation puts the
                             // reliable landing band in the tray's outer half, so the tray
                             // sits 4 mm inboard of the feed and 44 lands mid-band.
SEE_CUP_L    = 20;
SEE_CUP_W    = 22;
SEE_CUP_T    = 2;
SEE_CUP_Z    = -8;           // floor: a marble on it has its centre at the pivot height,
                             // so the load's line of action does not wander as it tips
SEE_CUP_BACK = 13;           // inner wall, above the floor
SEE_CW_X     = -SIDE;        // counterweight, one grid pitch the other side of the pivot.
SEE_CW       = [20, 22, 7]; // Measured, not guessed: the tray alone is ~2.6 cm3 sitting a
                             // full 44 mm out, and balancing that against a counterweight
                             // tucked in at 16 mm needed 13 g of PLA there — a brick. Out
                             // at 44 the same job takes 6.3 g, and the piece reads as the
                             // balance it is.
SEE_STOP_X   = -20;          // the gate straddles the beam, inside the base: flush with
                             // the base's side face, the two shared a plane and slivered
SEE_STOP_L   = 8;
SEE_PED_W    = 24;           // pedestal carrying the ears
SEE_CLR      = 0.3;          // swing clearance at the stops
SEE_STOP_STEPS = 24;         // resolution of the swept stop faces

function see_pivot() = SEE_BASE_H + SEE_PIVOT_Z;
function see_ey()    = SEE_ARM_W / 2 + SKATE_CLR + SKATE_EAR_T / 2;   // ear mid-plane

// The tray: floor, inner wall, two side walls, and deliberately open at the outer end —
// an outer lip is what a first sketch wants and it is wrong. Rolling the 20 mm of floor at
// the 10 deg bottom tilt only buys the marble 3.5 mm of height, so any lip tall enough to
// hold it at rest is also tall enough to trap it for good.
module seesaw_tray() {
  x0 = SEE_CUP_C - SEE_CUP_L / 2;
  difference() {
    translate([x0 - SEE_CUP_T, -SEE_CUP_W / 2, SEE_CUP_Z - SEE_CUP_T])
      cube([SEE_CUP_L + SEE_CUP_T, SEE_CUP_W, SEE_CUP_T + SEE_CUP_BACK]);
    translate([x0, -(SEE_CUP_W / 2 - SEE_CUP_T), SEE_CUP_Z])
      cube([SEE_CUP_L + 1, SEE_CUP_W - 2 * SEE_CUP_T, SEE_CUP_BACK + 1]);
  }
}

// The arm in its own frame: pivot at the origin, level, cup towards +x.
module seesaw_arm() {
  xa = SEE_CW_X - SEE_CW[0] / 2;
  xb = SEE_CUP_C - SEE_CUP_L / 2 + SEE_CUP_T;
  union() {
    translate([xa, -SEE_ARM_W / 2, -SEE_ARM_H / 2])
      cube([xb - xa, SEE_ARM_W, SEE_ARM_H]);
    rotate([90, 0, 0]) {
      cylinder(h = SEE_ARM_W, r = SEE_ARM_H / 2, center = true);
      for (s = [-1, 1])                                  // as skate_knuckle: cylinder()
        translate([0, 0, s * SEE_ARM_W / 2 - (s < 0 ? SKATE_PIN_L : 0)])   // only grows +z
          cylinder(h = SKATE_PIN_L, d = SKATE_PIN_D);
    }
    translate([SEE_CW_X, 0, 0]) cube(SEE_CW, center = true);
    seesaw_tray();
  }
}

// The gate that limits the swing. Rather than work out where the two stop faces go, take a
// solid straddling the counterweight and subtract the counterweight swept through its
// range: what is left is a pad below and a bridge above, touching at exactly the two
// limits by construction.
module seesaw_gate() {
  w = SEE_ARM_W + 2 * SEE_CLR;
  difference() {
    translate([SEE_STOP_X - SEE_STOP_L / 2, -(w / 2 + 4), 0])
      cube([SEE_STOP_L, w + 8, see_pivot() + 16]);   // tall enough to leave a
                                        // real bridge over the beam: at +10 the
                                        // swept void reaches 55.5, and a gate
                                        // capped at 56 left 0.5 mm of it — the
                                        // cup-down stop simply was not there
    see_stop_void();
  }
}

// The swept beam, built as one 2D fan and extruded once along the axle. Unioning rotated
// boxes in 3D instead leaves every one of them sharing the same two y faces, and
// subtracting that left slivers in the gate's side walls.
module see_stop_void() {
  translate([0, 0, see_pivot()]) rotate([90, 0, 0])
    linear_extrude(height = SEE_ARM_W + 2 * SEE_CLR, center = true)
      // the two rotations run opposite ways: rotate([90,0,0]) puts the profile in the
      // world XZ plane, where a positive 2D rotation tilts the cup UP, while the arm's
      // own rotate([0,a,0]) tilts it DOWN. Sweeping this fan the intuitive way cut the
      // mirror image of the range — cup-up stopped at 10 and cup-down never stopped at all
      for (i = [0:SEE_STOP_STEPS])
        rotate(-SEE_DOWN + i * (SEE_UP + SEE_DOWN) / SEE_STOP_STEPS)
          translate([SEE_STOP_X, 0])
            square([SEE_STOP_L + 20, SEE_ARM_H + 2 * SEE_CLR], center = true);
}

// The mount: a 44 x 44 base on the grid with a stud under it, a pedestal, and two ears
// carrying the same snap hinge as the skate ramp — same axle, same throat, so the
// tolerance comb gauges this piece too.
module seesaw_mount() {
  ey    = see_ey();
  ptop  = see_pivot() - 10;                    // pedestal stops clear of the swinging beam
  etop  = see_pivot() + SKATE_EAR_END;
  difference() {
    union() {
      cuboid([SIDE, SIDE, SEE_BASE_H], chamfer = CHAMFER, edges = "Z", anchor = BOTTOM);
      down(STUD_H) cyl(h = STUD_H, d = STUD_D, anchor = BOTTOM);
      translate([0, 0, SEE_BASE_H - EPS])
        cuboid([SEE_PED_W, SEE_PED_W, ptop - SEE_BASE_H + EPS], chamfer = CHAMFER,
               edges = "Z", anchor = BOTTOM);
      for (s = [-1, 1])
        translate([-SEE_PED_W / 2, s * ey - SKATE_EAR_T / 2, ptop - EPS])
          cube([SEE_PED_W, SKATE_EAR_T, etop - ptop + EPS]);
      seesaw_gate();
    }
    for (s = [-1, 1]) {
      translate([0, s * ey, see_pivot()]) rotate([90, 0, 0])
        cylinder(h = SKATE_EAR_T + 2, d = SKATE_PIN_D + 2 * SKATE_CLR, center = true);
      translate([0, s * ey, etop])
        cube([SKATE_SNAP_W, SKATE_EAR_T + 2, 2 * (etop - see_pivot())], center = true);
    }
  }
}

// The two parts laid out for printing. The arm goes on its side: every feature of the tray
// is then a vertical wall, and nothing needs support.
module seesaw() {
  seesaw_mount();
  translate([0, 60, SEE_CW[1] / 2]) rotate([90, 0, 0]) seesaw_arm();
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
