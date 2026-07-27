"""block-teal (Sideways, bottom) — 60 deg side exit + a low horizontal crossing."""

import lib

NAME = "block-teal"


def build():
    return lib.carve(lib.HEIGHT, lib.ch_top(), lib.ex_side(60, 0), lib.ex_across())
