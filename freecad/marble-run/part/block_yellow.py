"""block-yellow (One side lateral) — top entry + a 60 deg sloped side exit."""

import lib

NAME = "block-yellow"


def build():
    return lib.carve(lib.HEIGHT, lib.ch_top(), lib.ex_side(60, 0))
