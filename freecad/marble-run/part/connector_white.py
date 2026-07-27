"""connector-white (Wheat) — thin chamfered cube with a straight Ø30 hole, no stud
(quadri-plot MiniWhiteBlock). A spacer/ring the marble drops straight through."""

import lib

NAME = "connector-white"


def build():
    body = lib.chamfered_body(lib.SIDE, lib.MINI_H, lib.CHAMFER)
    hole = lib.z_cyl(lib.SOCKET_D, -1, lib.MINI_H + 1)
    return body.cut(hole).removeSplitter()
