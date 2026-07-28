// rail-curve120, split in two — optional. The whole rail is 338 x 338, so it does not
// fit a 256 mm bed; cut at its middle (60°) node each half is ~201 x 201. Print half A
// and half B, then lower B onto A: the dovetails align them and the stud of the block
// under the shared node pins the joint shut. Set JOINT=false in lib.scad for a plain
// butt cut instead.
use <../lib.scad>

module mr_rail_curve120_a() { rail_curve_half(120, 60, keep_near = true); }
module mr_rail_curve120_b() { rail_curve_half(120, 60, keep_near = false); }

mr_rail_curve120_a();
translate([0, 0, 30]) mr_rail_curve120_b();
