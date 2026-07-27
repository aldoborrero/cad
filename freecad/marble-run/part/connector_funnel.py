"""connector-funnel (purple) — thin landing connector: dish on top, bore to a stud."""

import lib

NAME = "connector-funnel"


def build():
    s = lib.block_base(lib.MINI_H)
    bore = lib.z_cyl(lib.BORE_D, lib.LOWEXIT, lib.MINI_H + 0.05)
    return s.cut(bore).removeSplitter()
