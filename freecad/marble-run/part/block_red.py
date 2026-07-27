"""block-red (Built-in toggle) — top entry + two 60 deg side exits at 90 deg
(the toggle picks which side the marble takes)."""

import lib

NAME = "block-red"


def build():
    return lib.carve(lib.HEIGHT, lib.ch_top(), lib.ex_side(60, 0), lib.ex_side(60, 90))
