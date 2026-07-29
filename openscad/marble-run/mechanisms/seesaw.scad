// seesaw (Wippe) — a tipping cup on a balance arm. The marble drops into the cup at the
// end of the raised arm, the arm swings down, and past level the cup's floor tips the
// marble out of its open end; the counterweight then rides the empty arm back up.
// Two parts, joined by the same snap hinge as the skate ramp. See lib.scad for why a
// plain pivoted trough cannot work.
use <../lib.scad>

module mr_seesaw() { seesaw(); }
// the two halves on their own, so either can be reprinted alone — and so the arm's
// balance can be re-measured from its STL after any parameter change
module mr_seesaw_arm() { rotate([90, 0, 0]) seesaw_arm(); }
module mr_seesaw_mount() { seesaw_mount(); }

mr_seesaw();
