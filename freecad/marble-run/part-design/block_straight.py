"""block-straight (orange) — through bore drilled top-to-bottom."""

import lib

NAME = "block-straight"


def build(doc):
    body = lib.base_block(doc, lib.HEIGHT)
    sk = lib.new_sketch(body, "Sketch_bore", lib.origin_plane(body, "XY"))
    lib.sk_circle(sk, lib.BORE_D / 2)
    lib.pocket(body, "Bore_pocket", sk, through=True, midplane=True)
    doc.recompute()
    return body
