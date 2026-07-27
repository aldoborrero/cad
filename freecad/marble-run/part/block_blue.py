"""block-blue (Sideways, bottom) — 60 deg side exit + bottom exit + a back exit."""

import lib

NAME = "block-blue"


def build():
    return lib.carve(
        lib.HEIGHT, lib.ch_top(), lib.ex_side(60, 0), lib.ex_bottom(), lib.ex_back()
    )
