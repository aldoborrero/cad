// tower — straight-drop towers (one continuous piece each). The marble enters the
// top dish, falls straight down the vertical bore and exits the bottom stud. Smooth
// column (no tier lines): 3-tier and 2-tier laid out side by side for the plate.
use <../lib.scad>

module mr_drop_tower_3() { tower(3); }
module mr_drop_tower_2() { tower(2); }

mr_drop_tower_3();
translate([60, 0, 0]) mr_drop_tower_2();
