// rail-straight — straight rail in quadri-plot's style (two rails + 8 mm groove),
// 5 nodes at block pitch. Not in quadri-plot itself (only curves); same cross-section.
use <lib.scad>

module mr_rail_straight() { rail_straight(5); }

mr_rail_straight();
