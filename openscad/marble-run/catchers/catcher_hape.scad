// marble-catcher-hape — the collector in the proportions of the Quadrilla original: the
// wide, shallow Ø112 x 26 dish, its central depression and its ring of ten radial slots,
// with the block on a boss beside it dropping the marble in over the rim.
//
// Optimised only where that does not change what it looks like: the wall is 2.5 mm instead
// of 4 and the top of it leans inwards, which together take 8 cm3 out.
//
// It cannot be made to keep marbles the way the other two do, and the reason is the shape,
// not the finish. The block has to stand on a boss as tall as the rim, so the marble falls
// 35 mm before it lands, and a 26 mm wall does not hold that: 72 % against 98 % for the
// round bowl and 100 % for the wedge, whatever the wall thickness or the lip. Measured
// across four builds it never moved off 72. This one is here for fidelity, not performance.
//
// `include` rather than `use`, so the parameters below override the library's for this file
// only — the modules the include brings in then evaluate against them.
include <../lib.scad>

CATCH_SHAPE   = "round";
CATCH_D       = 112;   // the original's diameter
CATCH_H       = 24;    // and its rim: 2 x MINI_H, so the boss lands on the grid
CATCH_DOCK_H  = 24;    // boss as tall as the rim: too shallow for a port through the wall
CATCH_DISH    = 5;
CATCH_DISH_R  = 46;
CATCH_SLOT_R  = 34;
CATCH_WALL    = 2.5;
CATCH_LIP     = 0;    // the original has no inward lean, and on a 26 mm rim it measured nothing

module mr_catcher_hape() { marble_catcher(); }

mr_catcher_hape();
