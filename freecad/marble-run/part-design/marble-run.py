"""marble-run part-design — Hape Quadrilla-compatible marble run (FreeCAD Part Design).

The Part Design sibling of ../part (Part/CSG): every piece is a PartDesign Body
with a sketch-driven, editable feature tree. Each piece is built in its own
document and saved as an editable .FCStd (into exports/, git-ignored) plus a
STEP + STL. A `marble` reference sphere is emitted as a plain Part solid.

Build (nested, so run the script path directly):
    freecadcmd freecad/marble-run/part-design/marble-run.py

NOTE: this approach could not be executed in the authoring environment (no
freecadcmd). The tapered bowl of `connector` and the side channel of `turn` are
the two features most likely to need a sign/axis tweak on first local run.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import FreeCAD as App  # noqa: E402
import Part  # noqa: E402
import MeshPart  # noqa: E402

import params as P  # noqa: E402
import pdlib as L  # noqa: E402


def _new_body(doc):
    body = doc.addObject("PartDesign::Body", "Body")
    doc.recompute()
    return body, L.origin_plane(body, "XY")


def build_blank(doc):
    body, xy = _new_body(doc)
    sb = L.new_sketch(body, "Sketch_body", xy)
    L.sk_polygon(sb, L.chamfered_square_pts(P.SIDE, P.CHAMFER))
    L.pad(body, "Body_pad", sb, P.HEIGHT)
    doc.recompute()
    ss = L.new_sketch(body, "Sketch_stud", xy)
    L.sk_circle(ss, P.STUD_D / 2)
    L.pad(body, "Stud_pad", ss, P.STUD_H, reversed=True)
    doc.recompute()
    sk = L.new_sketch(body, "Sketch_socket", xy, offset_z=P.HEIGHT)
    L.sk_circle(sk, P.SOCKET_D / 2)
    L.pocket(body, "Socket_pocket", sk, P.SOCKET_DEPTH)
    doc.recompute()
    return body


def build_straight(doc):
    body = build_blank(doc)
    sk = L.new_sketch(body, "Sketch_bore", L.origin_plane(body, "XY"))
    L.sk_circle(sk, P.BORE_D / 2)
    L.pocket(body, "Bore_pocket", sk, through=True, midplane=True)
    doc.recompute()
    return body


def build_turn(doc):
    body = build_blank(doc)
    xy = L.origin_plane(body, "XY")
    zmid = P.HEIGHT * 0.45
    # vertical drop: bore pocketed down from the top plane to the exit centre-line
    sv = L.new_sketch(body, "Sketch_vbore", xy, offset_z=P.HEIGHT)
    L.sk_circle(sv, P.BORE_D / 2)
    L.pocket(body, "Vbore_pocket", sv, length=P.HEIGHT - zmid)
    doc.recompute()
    # side exit: circle on the YZ plane (normal +X), pocketed out to the +X face.
    # reversed=True cuts along +X (toward the +X face); flip if the exit lands on -X.
    yz = L.origin_plane(body, "YZ")
    sh = L.new_sketch(body, "Sketch_hbore", yz)
    L.sk_circle_at(sh, 0, zmid, P.BORE_D / 2)  # local (u=Y, v=Z) -> global z=zmid
    L.pocket(body, "Hbore_pocket", sh, length=P.SIDE / 2 + P.CHAMFER + 1, reversed=True)
    doc.recompute()
    return body


def build_connector(doc):
    body, xy = _new_body(doc)
    sb = L.new_sketch(body, "Sketch_body", xy)
    L.sk_polygon(sb, L.chamfered_square_pts(P.SIDE, P.CHAMFER))
    L.pad(body, "Body_pad", sb, P.MINI_H)
    doc.recompute()
    ss = L.new_sketch(body, "Sketch_stud", xy)
    L.sk_circle(ss, P.STUD_D / 2)
    L.pad(body, "Stud_pad", ss, P.STUD_H, reversed=True)
    doc.recompute()
    # catch bowl: Ø mouth on top, tapered pocket narrowing to the bore
    taper = math.degrees(math.atan2((P.FUNNEL_TOP_D - P.BORE_D) / 2, P.FUNNEL_DEPTH))
    sk = L.new_sketch(body, "Sketch_bowl", xy, offset_z=P.MINI_H)
    L.sk_circle(sk, P.FUNNEL_TOP_D / 2)
    L.pocket(body, "Bowl_pocket", sk, length=P.FUNNEL_DEPTH, taper=-taper)
    doc.recompute()
    sb2 = L.new_sketch(body, "Sketch_bore", xy)
    L.sk_circle(sb2, P.BORE_D / 2)
    L.pocket(body, "Bore_pocket", sb2, through=True, midplane=True)
    doc.recompute()
    return body


BODY_PIECES = {
    "block-blank": build_blank,
    "block-straight": build_straight,
    "block-turn": build_turn,
    "connector-funnel": build_connector,
}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "exports")
    os.makedirs(out, exist_ok=True)

    for name, build in BODY_PIECES.items():
        doc = App.newDocument(name)
        body = build(doc)
        doc.recompute()
        shape = body.Shape
        shape.exportStep(os.path.join(out, name + ".step"))
        MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.1).write(
            os.path.join(out, name + ".stl")
        )
        doc.saveAs(os.path.join(out, name + ".FCStd"))  # editable feature tree
        App.closeDocument(doc.Name)
        print("wrote", name, "(.step/.stl/.FCStd)")

    # marble: a plain Part sphere (no feature tree needed)
    marble = Part.makeSphere(P.MARBLE_D / 2)
    marble.exportStep(os.path.join(out, "marble.step"))
    MeshPart.meshFromShape(Shape=marble, LinearDeflection=0.1).write(
        os.path.join(out, "marble.stl")
    )
    print("wrote marble (.step/.stl)")


main()
