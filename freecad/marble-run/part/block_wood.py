"""block-wood (bottom crossing) — vertical through + a low horizontal crossing."""

import lib

NAME = "block-wood"


def build():
    return lib.carve(lib.HEIGHT, lib.ch_top(), lib.ex_vertical(), lib.ex_across())
