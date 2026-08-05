// fitcheck — the tolerance comb. Print this before anything else.
//
// Four numbers in this project are guesses marked "tune on a test print", and three of them
// gate parts that cost 70 cm3 or more. This is ~50 cm3 and settles all of them in one go:
//
//   STACK_CLEAR   the Ø28 stud in the Ø30 socket — the whole system rides on this fit
//   JOINT_CLEAR   the sliding dovetail that rejoins a split rail
//   SKATE_SNAP_W  the throat the skate ramp's axle snaps through
//   SKATE_CLR     and how freely it then turns
//
// Each row is five of the same feature, one step apart. Count the pips in front of a
// feature to know which is which: 1 is always the tightest and 5 the loosest. On the
// dovetail and the snap hinge the nominal sits in the middle, at 3; on the socket it is at
// 5, for the reason given over that row. Pips rather than engraved numbers, so no font.
//
// Read it by feel, not by eye. The one you want is the tightest that still goes together
// without forcing, and comes apart again.
//
// Every feature is at its REAL engagement depth. A Ø30 hole in a 2.5 mm plate would gauge
// the diameter but not the friction, and friction over the socket's full 8.5 mm is what
// actually decides whether a stud goes in without forcing — the first draft got this wrong
// and would have read far too loose. So the features are bosses standing straight on the
// bed, tied together by a 3 mm rib, rather than sunk into a backing plate: same test at a
// fifth of the plastic.
//
// It prints as six pieces — three combs, and three loose gauges (a stud, a tenon, an axle)
// to try in them.
//
// `include` rather than `use`, so this reads the library's parameters directly.
include <../lib.scad>

FIT_N     = 5;      // features per row, odd so the middle is nominal
FIT_STEP  = 0.15;   // between neighbours, on the width
FIT_RIB_W = 6;      // the tie bar that holds a row together
FIT_RIB_H = 3;
FIT_PIP_D = 1.6;
FIT_PIP_H = 1.0;
FIT_WELD  = 1.5;    // how far a boss and its rib interpenetrate. They have to overlap in a
                    // volume: two solids that merely share a face come out as separate
                    // shells, which is how the first build ended up in 25 pieces.

function fit_d(i) = (i - (FIT_N - 1) / 2) * FIT_STEP;      // -2..+2 steps
function fit_x(i, pitch) = (i - (FIT_N - 1) / 2) * pitch;
function fit_span(pitch, w) = (FIT_N - 1) * pitch + w;     // a row's overall length
// the rib overhangs the row a little on purpose: cut flush, its end plane landed on the
// end boss's own end face, and coplanar faces come back as paper-thin shells
function fit_rib_len(pitch, w) = fit_span(pitch, w) + 3;

// i + 1 pips, so the leftmost feature reads as one
module fit_pips(i, y) {
  for (k = [0:i])
    translate([(k - i / 2) * (FIT_PIP_D + 1.2), y, FIT_RIB_H - 0.4])
      cylinder(h = FIT_PIP_H + 0.4, d = FIT_PIP_D, $fn = 20);
}

module fit_rib(len, y) {
  translate([0, y, FIT_RIB_H / 2]) cube([len, FIT_RIB_W, FIT_RIB_H], center = true);
}

/* ---- row 1: the socket ---------------------------------------------------------------
   Five rings bored as deep as a real socket. Push the loose stud into each: the one that
   seats without slop and lifts off without a fight sets STACK_CLEAR. Bored right through
   rather than blind, so a stud that grips can be pushed back out.

   This row runs one way only, and 5 is the nominal rather than 3. STACK_CLEAR is currently
   1 mm — a whole millimetre of air on each side of the stud — and stepping either side of
   that would have gauged five fits that are all far too loose to tell apart. So the row
   starts at nominal and tightens: Ø30.0 down to Ø28.4, which is a 0.2 mm slip fit. */
FIT_SOCK_WALL = 3;
FIT_SOCK_H    = SOCKET_DEPTH + 1;                     // 9.5
FIT_SOCK_STEP = 0.4;
FIT_SOCK_OD   = SOCKET_D + 2 * FIT_SOCK_WALL;         // 36
FIT_P_SOCK    = FIT_SOCK_OD + 3;

function fit_sock_d(i) = (i - (FIT_N - 1)) * FIT_SOCK_STEP;   // -1.6 .. 0

module fit_sockets() {
  ry = -FIT_SOCK_OD / 2 - FIT_RIB_W / 2 + FIT_WELD;
  difference() {
    union() {
      for (i = [0:FIT_N - 1])
        translate([fit_x(i, FIT_P_SOCK), 0, 0])
          cylinder(h = FIT_SOCK_H, d = FIT_SOCK_OD, $fn = 96);
      fit_rib(fit_rib_len(FIT_P_SOCK, FIT_SOCK_OD), ry);
      for (i = [0:FIT_N - 1]) translate([fit_x(i, FIT_P_SOCK), 0, 0]) fit_pips(i, ry);
    }
    for (i = [0:FIT_N - 1])
      translate([fit_x(i, FIT_P_SOCK), 0, -EPS])
        cylinder(h = FIT_SOCK_H + 2 * EPS, d = SOCKET_D + fit_sock_d(i), $fn = 96);
  }
}

// the nominal stud to try them with. Hollow: only its outside diameter is the gauge, and
// it prints face-down on its Ø28 end, so the void needs no support. The stem is a handle.
module fit_stud() {
  difference() {
    union() {
      cylinder(h = STUD_H, d = STUD_D, $fn = 96);
      translate([0, 0, STUD_H - EPS]) cylinder(h = 14, d = 12, $fn = 48);
    }
    translate([0, 0, -EPS]) cylinder(h = STUD_H - 2.5, d = STUD_D - 10, $fn = 64);
  }
}

/* ---- row 2: the dovetail -------------------------------------------------------------
   The split-rail joint assembles by lowering one half onto the other, so the pocket is a
   slot through the full rail height and the tenon drops in from above. Five pockets at
   JOINT_CLEAR + step, in bosses RAIL_H tall so the tenon engages over its whole length. */
// `over` extends the slot past both ends, and is deliberately independent of `grow`: tied
// to it, the tightest pocket (grow < 0, an interference fit) stopped short of the boss's
// faces and came out as a sealed cavity instead of a slot.
module fit_dovetail(grow = 0, h = RAIL_H, over = 0) {
  translate([0, 0, -over])
    linear_extrude(height = h + 2 * over)
      offset(delta = grow)
        polygon([[-JOINT_W0 / 2, 0], [JOINT_W0 / 2, 0],
                 [JOINT_W1 / 2, JOINT_D], [-JOINT_W1 / 2, JOINT_D]]);
}

FIT_JOINT_W = JOINT_W1 + 2 * JOINT_CLEAR + 8;   // 13.4: pocket plus a 4 mm wall each side
FIT_JOINT_D = JOINT_D + 6;                      // 15
FIT_P_JOINT = FIT_JOINT_W + 6;

module fit_joints() {
  ry = -FIT_JOINT_D / 2 - FIT_RIB_W / 2 + FIT_WELD;
  difference() {
    union() {
      for (i = [0:FIT_N - 1])
        translate([fit_x(i, FIT_P_JOINT), 0, 0])
          cuboid([FIT_JOINT_W, FIT_JOINT_D, RAIL_H], chamfer = 1, edges = "Z",
                 anchor = BOTTOM);
      fit_rib(fit_rib_len(FIT_P_JOINT, FIT_JOINT_W), ry);
      for (i = [0:FIT_N - 1]) translate([fit_x(i, FIT_P_JOINT), 0, 0]) fit_pips(i, ry);
    }
    for (i = [0:FIT_N - 1])
      translate([fit_x(i, FIT_P_JOINT), -JOINT_D / 2, 0])
        fit_dovetail(JOINT_CLEAR + fit_d(i), RAIL_H, 1);
  }
}

// the male, loose, on a stub you can hold
module fit_tenon() {
  translate([0, -JOINT_D / 2, 0]) fit_dovetail();
  translate([0, JOINT_D / 2 + 5, 0])
    cuboid([12, 12, RAIL_H], chamfer = 1, edges = "Z", anchor = BOTTOM);
}

/* ---- row 3: the snap hinge -----------------------------------------------------------
   Five ear pairs whose throat is SKATE_SNAP_W + step. Press the loose axle in: too narrow
   and the ears split, too wide and it falls out. SKATE_CLR shows up as how freely it then
   turns, so judge that on the same part.

   The ears are skate_mount's, minus the ring: same thickness, same height, same bore, and
   the same short outboard arm — that arm is ~11x more flexible than the inboard one, so it
   does essentially all the springing and the missing ring barely changes the force. */
FIT_EAR_IN  = 10;                             // ear material inboard of the axis
FIT_EAR_L   = FIT_EAR_IN + SKATE_EAR_END;
FIT_P_SNAP  = FIT_EAR_L + 6;

module fit_snaps() {
  gap = SKATE_W + 2 * SKATE_CLR;              // as skate_mount: the ramp runs between them
  ey  = (gap + SKATE_EAR_T) / 2;
  len = fit_rib_len(FIT_P_SNAP, FIT_EAR_L);
  ry  = ey + SKATE_EAR_T / 2 + FIT_RIB_W / 2 - FIT_WELD;
  difference() {
    union() {
      for (i = [0:FIT_N - 1])
        for (s = [-1, 1])
          translate([fit_x(i, FIT_P_SNAP) - FIT_EAR_IN, s * ey - SKATE_EAR_T / 2, 0])
            cube([FIT_EAR_L, SKATE_EAR_T, SKATE_H]);
      // a rib outside each line of ears, closed into a frame by a tie at each end. The
      // ties stop short of the ribs' ends and faces: flush would share a plane, and a
      // shared plane comes back as a paper-thin shell of its own.
      for (s = [-1, 1]) {
        fit_rib(len, s * ry);
        translate([s * (len / 2 - FIT_RIB_W / 2 - 1), 0, FIT_RIB_H / 2])
          cube([FIT_RIB_W, 2 * ry, FIT_RIB_H], center = true);
      }
      for (i = [0:FIT_N - 1]) translate([fit_x(i, FIT_P_SNAP), 0, 0]) fit_pips(i, -ry);
    }
    for (i = [0:FIT_N - 1])
      for (s = [-1, 1]) {
        translate([fit_x(i, FIT_P_SNAP), s * ey, SKATE_H / 2]) rotate([90, 0, 0])
          cylinder(h = SKATE_EAR_T + 2, d = SKATE_PIN_D + 2 * SKATE_CLR, center = true,
                   $fn = 48);
        translate([fit_x(i, FIT_P_SNAP), s * ey, SKATE_H])
          cube([SKATE_SNAP_W + fit_d(i), SKATE_EAR_T + 2, SKATE_H], center = true);
      }
  }
}

// the loose axle, on a blade: it prints flat, and it gives you something to turn so the
// running clearance can be felt once the axle has snapped in
module fit_axle() {
  l = SKATE_W + 2 * SKATE_CLR + 2 * SKATE_EAR_T;
  translate([0, 0, SKATE_PIN_D / 2]) rotate([90, 0, 0])
    cylinder(h = l, d = SKATE_PIN_D, center = true, $fn = 48);
  translate([0, -(l / 2 + 11), 0])
    cuboid([12, 24, 1.8], chamfer = 1, edges = "Z", anchor = BOTTOM);
}

module mr_fitcheck() {
  sock  = fit_span(FIT_P_SOCK, FIT_SOCK_OD);
  joint = fit_span(FIT_P_JOINT, FIT_JOINT_W);
  snap  = fit_span(FIT_P_SNAP, FIT_EAR_L);
  translate([0, 56, 0]) fit_sockets();
  translate([0, 12, 0]) fit_joints();
  translate([0, -38, 0]) fit_snaps();
  translate([joint / 2 + 26, 12, 0]) fit_tenon();
  translate([snap / 2 + 14, -38, 0]) fit_axle();
  translate([snap / 2 + 43, -38, 0]) fit_stud();
}

mr_fitcheck();
