"""block-green (Sideways, bottom) — 60 deg side exit + bottom exit + low crossing."""

import lib

NAME = "block-green"


def build():
    return lib.carve(
        lib.HEIGHT, lib.ch_top(), lib.ex_side(60, 0), lib.ex_bottom(), lib.ex_across()
    )
