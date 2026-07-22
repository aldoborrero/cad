// <project> — one-line description
//
// Shared helpers:   use <../lib/common.scad>
// BOSL2 primitives: include <BOSL2/std.scad>   (on OPENSCADPATH via the flake)

use <../lib/common.scad>

// ---------- Parameters ----------
SIZE = 20;   // mm

$fn = 96;

// ---------- Model ----------
cube(SIZE, center = true);
