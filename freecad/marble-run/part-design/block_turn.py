"""block-turn (yellow) — vertical drop + 90 deg side exit on the +X face.

The two channel pockets are the features most likely to need a local tweak:
if the side exit lands on the wrong face, flip `reversed` on Hbore_pocket.
"""

import lib

NAME = "block-turn"


def build(doc):
    body = lib.base_block(doc, lib.HEIGHT)
    zmid = lib.HEIGHT * 0.45

    # vertical drop: bore pocketed down from the top plane to the exit centre-line
    sv = lib.new_sketch(
        body, "Sketch_vbore", lib.origin_plane(body, "XY"), offset_z=lib.HEIGHT
    )
    lib.sk_circle(sv, lib.BORE_D / 2)
    lib.pocket(body, "Vbore_pocket", sv, length=lib.HEIGHT - zmid)
    doc.recompute()

    # side exit: circle on the YZ plane (normal +X), pocketed out to the +X face
    sh = lib.new_sketch(body, "Sketch_hbore", lib.origin_plane(body, "YZ"))
    lib.sk_circle_at(sh, 0, zmid, lib.BORE_D / 2)  # local (u=Y, v=Z) -> global z=zmid
    lib.pocket(
        body, "Hbore_pocket", sh, length=lib.SIDE / 2 + lib.CHAMFER + 1, reversed=True
    )
    doc.recompute()
    return body
