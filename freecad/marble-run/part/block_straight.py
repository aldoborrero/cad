"""block-straight (orange) — marble drops straight through the bottom stud."""

import lib

NAME = "block-straight"


def build():
    s = lib.block_base(lib.HEIGHT)
    z1 = lib.HEIGHT - lib.SOCKET_DEPTH  # socket floor
    bore = lib.z_cyl(lib.BORE_D, -lib.STUD_H, z1)  # through the stud, up to the socket
    return s.cut(bore).removeSplitter()
