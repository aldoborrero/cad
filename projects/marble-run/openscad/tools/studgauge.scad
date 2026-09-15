// studgauge — five studs stepping through Ø30, to measure a real block's socket.
//
// It has been printed and read: **gauge 2, Ø29.5**, which is what STUD_D now is. The
// recorded 28 was a shade under, which is why studs felt slack in a real set, and Ø30.0 --
// the value proposed before this was printed -- would have been too big to seat. Kept
// because the same row re-measures a second set, or a warped one, in 9 cm3.
//
// Offer each stud up to the socket of a block you already own: the right STUD_D is the
// largest that seats without forcing and lifts off without a fight.
//
// Pips as everywhere in this project: count them, 1 is the tightest. Here that is the
// SMALLEST, Ø29.0, and 5 is Ø31.0, with Ø30.0 in the middle at 3.
//
// Two things this deliberately does not do.
//
// It is SHORT -- 5 mm against the real stud's 8. It gauges the socket's DIAMETER, which was
// the open question, and full height was not wanted. Note the cost, which is the trap
// fitcheck's row 1 documents in reverse: friction over the full 8.5 mm of engagement is what
// really decides "goes in without forcing", so a short stud reads a touch loose. If two
// neighbours feel the same, raise SG_H to STUD_H and reprint those two.
//
// And it does not itself set STUD_D -- it only says what to set it to. Changing the number
// first and measuring afterwards is how a guess becomes a fact nobody checked.
//
// `include` rather than `use`, so this reads the library's parameters directly.
include <../lib.scad>

SG_NOM   = 30;    // the proposed stud Ø, in the middle of the row
SG_N     = 5;     // gauges, odd so the nominal is the middle one
SG_STEP  = 0.5;   // between neighbours, on the diameter
SG_H     = 5;     // engagement height, short on purpose (see above)
SG_WALL  = 3;     // bored through, so it prints on the bed with no support and cannot trap
SG_RIB_W = 6;
SG_RIB_H = 3;
SG_PIP_D = 1.6;
SG_PIP_H = 1.0;
SG_WELD  = 1.5;   // how far a stud and the rib interpenetrate. Two solids that merely share
                  // a face come back as separate shells, not one body.

function sg_d(i) = SG_NOM + (i - (SG_N - 1) / 2) * SG_STEP;   // 29.0 .. 31.0
function sg_x(i) = (i - (SG_N - 1) / 2) * (sg_d(SG_N - 1) + 4);

// i + 1 pips, so the leftmost gauge reads as one
module sg_pips(i, y) {
  for (k = [0:i])
    translate([(k - i / 2) * (SG_PIP_D + 1.2), y, SG_RIB_H - 0.4])
      cylinder(h = SG_PIP_H + 0.4, d = SG_PIP_D, $fn = 20);
}

module mr_studgauge() {
  // The rib is hung off the SMALLEST gauge, so every one of them overlaps it by at least
  // SG_WELD -- hung off the nominal, Ø29.0 would have touched it along a line and come away
  // as a loose piece.
  ry  = -sg_d(0) / 2 - SG_RIB_W / 2 + SG_WELD;
  len = (SG_N - 1) * (sg_d(SG_N - 1) + 4) + sg_d(SG_N - 1) + 3;
  difference() {
    union() {
      for (i = [0:SG_N - 1])
        translate([sg_x(i), 0, 0]) cylinder(h = SG_H, d = sg_d(i), $fn = 96);
      translate([0, ry, SG_RIB_H / 2]) cube([len, SG_RIB_W, SG_RIB_H], center = true);
      for (i = [0:SG_N - 1]) translate([sg_x(i), 0, 0]) sg_pips(i, ry);
    }
    for (i = [0:SG_N - 1])
      translate([sg_x(i), 0, -EPS])
        cylinder(h = SG_H + 2 * EPS, d = sg_d(i) - 2 * SG_WALL, $fn = 64);
  }
}

mr_studgauge();
