// iotorero-mount — outlet cradle for the round Athom / IoTorero IR remote.
// Rests on the (rectangular) USB charger plugged into a Schuko outlet; the puck
// hangs in a cradle below. Retention = discrete tabs over the lower semicircle
// with 45deg self-supporting lips (slide the puck in from the open top).
// Prints flat, no supports.

use <../lib/common.scad>

// ---------- Puck (MEASURED) ----------
DEVICE_DIA      = 65;    // base Ø (measured 64.33)
DEVICE_STRAIGHT = 25;    // straight cylindrical wall (edge height)
DEVICE_H        = 29;    // total height at the centre of the dome

// ---------- Charger brick (RECTANGULAR Schuko — TODO: measure) ----------
BRICK_W       = 45;      // TODO
BRICK_H       = 50;      // TODO
BRICK_R       = 5;       // corner radius
BRICK_FIT     = 0.6;     // clearance so the plate slips over the brick

// ---------- Plate ----------
PLATE_T       = 4;
RIM           = 6;
LEDGE         = 6;       // annular ledge the flat base rests on
CH_GAP        = 16;      // gap between puck ring and brick aperture

// ---------- Retaining tabs (lower semicircle; mouth open at top) ----------
RING_H        = DEVICE_STRAIGHT;
LIP           = 2;
LIP_H         = 2.5;     // >= LIP+FIT so the lip underside is a <=45deg self-supporting chamfer
FIT           = 0.5;
RING_WALL     = 3;
TAB_ANGLES    = [150, 190, 230, 270, 310, 350];
TAB_HALF      = 11;

// ---------- Cable clip ----------
CABLE_DIA     = 4;
CLIP_WALL     = 2;

SHOW_PUCK     = false;   // set true to preview the device in place
$fn = 140;

// ---------- Derived ----------
a       = DEVICE_DIA / 2;
apW     = BRICK_W + 2 * BRICK_FIT;
apH     = BRICK_H + 2 * BRICK_FIT;
ch_y    = a + RIM + CH_GAP + apH / 2;
holeR   = a - LEDGE;
ro      = a + FIT + RING_WALL;

// ---------- Plate ----------
module blob2d() {
  hull() {
    circle(r = a + RIM);
    translate([0, ch_y]) rrect(apW + 2 * RIM, apH + 2 * RIM, BRICK_R + RIM);
  }
}
module plate() {
  linear_extrude(PLATE_T) difference() {
    blob2d();
    circle(r = holeR);
    translate([0, ch_y]) rrect(apW, apH, BRICK_R);
  }
}

// Full ring + chamfered lip, kept only at the tab angles.
module tabs() {
  translate([0, 0, PLATE_T]) intersection() {
    difference() {
      cylinder(h = RING_H, r = ro);
      union() {
        translate([0, 0, -1]) cylinder(h = RING_H - LIP_H + 1, r = a + FIT);
        translate([0, 0, RING_H - LIP_H]) cylinder(h = LIP_H + 0.1, r1 = a + FIT, r2 = a - LIP);
      }
    }
    union() for (t = TAB_ANGLES) ring_sector(ro + 3, t, TAB_HALF, -1, RING_H + 3);
  }
}

// ---------- Assembly ----------
WELD   = 0.6;   // sink cradle/clip into the plate for a single manifold body
neck_y = (a + (ch_y - apH / 2)) / 2;
union() {
  plate();
  translate([0, 0, -WELD]) tabs();
  translate([a - CABLE_DIA - 2, neck_y, PLATE_T - WELD]) cable_clip(CABLE_DIA, CLIP_WALL);
}
if (SHOW_PUCK)
  translate([0, 0, PLATE_T]) color("silver", 0.3) dome_puck(DEVICE_DIA, DEVICE_STRAIGHT, DEVICE_H);
