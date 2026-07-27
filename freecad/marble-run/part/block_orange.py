"""block-orange (Vertical) — marble drops straight through, top to bottom."""

import lib

NAME = "block-orange"


def build():
    return lib.carve(lib.HEIGHT, lib.ch_top(), lib.ex_vertical())
