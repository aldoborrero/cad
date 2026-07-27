"""connector-funnel (purple) — thin landing connector: tapered catch bowl + stud.

The bowl is a tapered pocket; if it widens instead of narrowing on first local run,
flip the sign of `taper`.
"""

import math

import lib

NAME = "connector-funnel"


def build(doc):
    body = doc.addObject("PartDesign::Body", "Body")
    doc.recompute()
    xy = lib.origin_plane(body, "XY")

    sb = lib.new_sketch(body, "Sketch_body", xy)
    lib.sk_polygon(sb, lib.chamfered_square_pts(lib.SIDE, lib.CHAMFER))
    lib.pad(body, "Body_pad", sb, lib.MINI_H)
    doc.recompute()

    ss = lib.new_sketch(body, "Sketch_stud", xy)
    lib.sk_circle(ss, lib.STUD_D / 2)
    lib.pad(body, "Stud_pad", ss, lib.STUD_H, reversed=True)
    doc.recompute()

    # catch bowl: Ø mouth on top, tapered pocket narrowing to the bore
    taper = math.degrees(
        math.atan2((lib.FUNNEL_TOP_D - lib.BORE_D) / 2, lib.FUNNEL_DEPTH)
    )
    sk = lib.new_sketch(body, "Sketch_bowl", xy, offset_z=lib.MINI_H)
    lib.sk_circle(sk, lib.FUNNEL_TOP_D / 2)
    lib.pocket(body, "Bowl_pocket", sk, length=lib.FUNNEL_DEPTH, taper=-taper)
    doc.recompute()

    sb2 = lib.new_sketch(body, "Sketch_bore", xy)
    lib.sk_circle(sb2, lib.BORE_D / 2)
    lib.pocket(body, "Bore_pocket", sb2, through=True, midplane=True)
    doc.recompute()
    return body
