// rail-s, split in two — optional. The whole S is 374 x 375 and will not fit a 256 mm
// bed. It is already two 60° arcs meeting at the centre node, so each half is one arc
// (~201 x 201) and the joint sits at that shared node.
use <../lib.scad>

module mr_rail_s_a() { rail_s_half(keep_near = true); }
module mr_rail_s_b() { rail_s_half(keep_near = false); }

mr_rail_s_a();
mr_rail_s_b();
