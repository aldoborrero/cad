"""The printer bed, drawn in the 3D view.

It is a Coin scene-graph node, not a document object: nothing here is saved into
the .FCStd, appears in the tree, can be selected, or gets swept up by "export
everything visible".

The geometry below is plain arithmetic so it can be tested without FreeCAD;
pivy is imported inside the functions that need it, for the same reason.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from freecad.slicercad import fit

# Coin nodes, FreeCAD placements and Part faces, which ship no stubs. Named here
# so a signature says which kind of Any it means.
SoNode = Any
Placement = Any
Face = Any
Shape = Any

# PartPlate.cpp draws the plate at GROUND_Z, just under zero, so nothing resting
# on it z-fights with it.
GROUND_Z = -0.03

# Zones and grid go a hair above the plate. Drawing them at the same Z z-fights,
# which shows as a sawtooth edge at oblique angles and looks clean head-on.
ZONE_Z = GROUND_Z + 0.01
GRID_Z = GROUND_Z + 0.005

# Bambu's own palette, read from PartPlate.cpp and kept where it already suits a
# #1F1F1F viewport. SELECT_COLOR and LINE_TOP_DARK_COLOR are theirs verbatim; the
# excluded zone is toned down from their #C3C4C4, which measures 9.43 against our
# darker background and shouts. Every one of these is overridable.
DEFAULT_COLOURS: dict[str, str] = {
    "plate": "#444747",  # 1.76 against the viewport
    "grid": "#6E6E76",  # 1.86 against the plate it is drawn on
    "grid_bold": "#8A8D93",  # every fifth line, as Bambu does
    "zone": "#A5A8A8",  # 3.92 against the plate
    "volume": "#6666FF",  # Bambu's HEIGHT_LIMIT_BOTTOM, 3.85 against the viewport
}

Colour = tuple[float, float, float]
Point = tuple[float, float, float]
Segment = tuple[Point, Point]


def parse_colour(value: str) -> Colour:
    """ "#RRGGBB" as the 0..1 floats Coin wants. Raises ValueError on rubbish."""
    digits = str(value).lstrip("#")
    if len(digits) != 6:
        raise ValueError(f"expected #RRGGBB, got {value!r}")
    red, green, blue = (int(digits[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return red, green, blue


def colour_from_uint(value: int) -> str:
    """Gui::PrefColorButton stores 0xRRGGBBAA; drop the alpha, keep the hex."""
    return "#%06X" % ((int(value) >> 8) & 0xFFFFFF)


def colours(overrides: Mapping[str, str] | None) -> dict[str, str]:
    """The palette, with anything unset or unreadable falling back to default."""
    merged = dict(DEFAULT_COLOURS)
    for key, value in (overrides or {}).items():
        if key not in merged or not value:
            continue
        try:
            parse_colour(value)
        except ValueError:
            continue
        merged[key] = value
    return merged


GRID_STEP = 10.0
GRID_BOLD_EVERY = 5


def grid(profile: fit.Bed) -> tuple[list[Segment], list[Segment]]:
    """Grid segments in model coordinates, split into (thin, bold).

    10 mm apart with every fifth line bolder, which is what calc_gridlines does.
    """
    dx, dy = fit.offset(profile)
    thin: list[Segment] = []
    bold: list[Segment] = []
    for axis, (length, other) in enumerate(
        ((profile.width, profile.depth), (profile.depth, profile.width))
    ):
        count = 0
        position = 0.0
        while position <= length + 1e-9:
            segment: Segment
            if axis == 0:
                segment = (
                    (position - dx, 0 - dy, GRID_Z),
                    (position - dx, other - dy, GRID_Z),
                )
            else:
                segment = (
                    (0 - dx, position - dy, GRID_Z),
                    (other - dx, position - dy, GRID_Z),
                )
            (bold if count % GRID_BOLD_EVERY == 0 else thin).append(segment)
            count += 1
            position += GRID_STEP
    return thin, bold


def rectangle(profile: fit.Bed) -> list[Point]:
    """The plate outline at Z=0, drawn around the model origin.

    Bambu's own origin is the plate's front-left corner, but parts here are
    modelled around (0,0); fit.offset reconciles the two, and the export applies
    the same vector, so nothing in the document has to move.
    """
    dx, dy = fit.offset(profile)
    return [
        (0 - dx, 0 - dy, GROUND_Z),
        (profile.width - dx, 0 - dy, GROUND_Z),
        (profile.width - dx, profile.depth - dy, GROUND_Z),
        (0 - dx, profile.depth - dy, GROUND_Z),
    ]


def zones(profile: fit.Bed) -> list[list[Point]]:
    """One outline per excluded zone, in the same order as the profile."""
    dx, dy = fit.offset(profile)
    return [
        [
            (zone.xmin - dx, zone.ymin - dy, ZONE_Z),
            (zone.xmax - dx, zone.ymin - dy, ZONE_Z),
            (zone.xmax - dx, zone.ymax - dy, ZONE_Z),
            (zone.xmin - dx, zone.ymax - dy, ZONE_Z),
        ]
        for zone in profile.exclusions
    ]


# (scene graph, switch) of the bed currently in a view.
_drawn: tuple[SoNode, SoNode] | None = None


def _material(coin: Any, colour: Colour, transparency: float) -> SoNode:
    material = coin.SoMaterial()
    material.diffuseColor.setValue(*colour)
    material.transparency.setValue(transparency)
    return material


def _face(
    coin: Any, points: Sequence[Point], colour: Colour, transparency: float
) -> SoNode:
    node = coin.SoSeparator()
    node.addChild(_material(coin, colour, transparency))
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, len(points), points)
    node.addChild(coords)
    face = coin.SoFaceSet()
    face.numVertices.setValue(len(points))
    node.addChild(face)
    return node


def _outline(coin: Any, points: Sequence[Point], colour: Colour) -> SoNode:
    node = coin.SoSeparator()
    node.addChild(_material(coin, colour, 0.0))
    style = coin.SoDrawStyle()
    style.lineWidth.setValue(2)
    node.addChild(style)
    closed = [*points, points[0]]
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, len(closed), closed)
    node.addChild(coords)
    line = coin.SoLineSet()
    line.numVertices.setValue(len(closed))
    node.addChild(line)
    return node


def _segments(
    coin: Any, lines: Sequence[Segment], colour: Colour, width: float
) -> SoNode:
    """One Coin node for a list of two-point segments."""
    node = coin.SoSeparator()
    node.addChild(_material(coin, colour, 0.0))
    style = coin.SoDrawStyle()
    style.lineWidth.setValue(width)
    node.addChild(style)
    points = [point for segment in lines for point in segment]
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, len(points), points)
    node.addChild(coords)
    line_set = coin.SoLineSet()
    line_set.numVertices.setValues(0, len(lines), [2] * len(lines))
    node.addChild(line_set)
    return node


def scene_node(
    profile: fit.Bed,
    palette: Mapping[str, str] | None = None,
    show_volume: bool = True,
) -> SoNode:
    """The whole bed as one Coin node: plate, grid, border, excluded zones.

    Opaque like Bambu's own plate, which is why everything sits at GROUND_Z
    rather than at zero.
    """
    from pivy import coin

    palette = colours(palette)
    root = coin.SoSeparator()
    plate = rectangle(profile)
    root.addChild(_face(coin, plate, parse_colour(palette["plate"]), 0.0))

    thin, bold = grid(profile)
    root.addChild(_segments(coin, thin, parse_colour(palette["grid"]), 1))
    root.addChild(_segments(coin, bold, parse_colour(palette["grid_bold"]), 2))
    root.addChild(_outline(coin, plate, parse_colour(palette["grid_bold"])))

    for zone in zones(profile):
        root.addChild(_face(coin, zone, parse_colour(palette["zone"]), 0.0))

    if show_volume and profile.height:
        posts, ring = volume(profile)
        blue = parse_colour(palette["volume"])
        root.addChild(_segments(coin, posts, blue, 1))
        root.addChild(_segments(coin, ring, blue, 2))
    return root


def show(
    profile: fit.Bed,
    palette: Mapping[str, str] | None = None,
    placement: Placement | None = None,
    show_volume: bool = True,
) -> None:
    """Draw the bed in the active 3D view, replacing whatever was there."""
    global _drawn
    import FreeCADGui
    from pivy import coin
    from PySide import QtCore

    hide()
    view = FreeCADGui.ActiveDocument.ActiveView
    graph = view.getSceneGraph()

    switch = coin.SoSwitch()
    switch.addChild(_placed(scene_node(profile, palette, show_volume), placement))
    switch.whichChild = 0
    _drawn = (graph, switch)

    # Deferred on purpose: inserting while an event handler is running mutates the
    # graph mid-traversal, which is the trap FreeCAD's own trackers document. The
    # guard matters — a toggle fast enough to run hide() before this fires would
    # otherwise insert a bed nobody is holding a reference to.
    def insert() -> None:
        if _drawn is not None and _drawn[1] is switch:
            graph.addChild(switch)

    QtCore.QTimer.singleShot(0, insert)


def hide() -> None:
    """Take the bed back out of the view. Safe when nothing is drawn."""
    global _drawn
    if _drawn is None:
        return
    graph, switch = _drawn
    _drawn = None
    if graph.findChild(switch) >= 0:
        graph.removeChild(switch)


def visible() -> bool:
    return _drawn is not None


def _placed(node: SoNode, placement: Placement | None) -> SoNode:
    """Hang `node` off an SoTransform, the way Draft's own trackers do."""
    if placement is None:
        return node
    from pivy import coin

    root = coin.SoSeparator()
    transform = coin.SoTransform()
    base = placement.Base
    transform.translation.setValue(base.x, base.y, base.z)
    axis = placement.Rotation.Axis
    transform.rotation.setValue(
        coin.SbVec3f(axis.x, axis.y, axis.z), placement.Rotation.Angle
    )
    root.addChild(transform)
    root.addChild(node)
    return root


def placement_from_face(face: Face) -> Placement:
    """A bed placement that rests the given planar face on the plate.

    The bed's +Z is the opposite of the face's outward normal: resting a face
    means it ends up facing downwards, which is the semantics Bambu's own
    Selection::flattening_rotate settles.

    This is the essence of Draft's draftgeoutils.geometry.placement_from_face,
    rewritten against Part alone: importing Draft into an addon costs the
    heaviest module in FreeCAD, for a rotation and a centre of mass.
    """
    import FreeCAD

    if not face.Surface.isPlanar():
        raise ValueError("the bed can only rest on a planar face")
    normal = face.normalAt(0, 0)
    rotation = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), normal.negative())
    return FreeCAD.Placement(face.CenterOfMass, rotation)


def under(shapes: Sequence[Shape]) -> Placement:
    """The placement that puts the plate under the lowest point of `shapes`."""
    import FreeCAD

    if not shapes:
        return FreeCAD.Placement()
    lowest = min(shape.BoundBox.ZMin for shape in shapes)
    return FreeCAD.Placement(FreeCAD.Vector(0, 0, lowest), FreeCAD.Rotation())


def volume(profile: fit.Bed) -> tuple[list[Segment], list[Segment]]:
    """The print volume as (corner posts, ring at the height limit).

    The construction is PartPlate::calc_height_limit's: a vertical line at every
    corner of the plate, and a horizontal ring joining them at the limit. Bambu
    draws two rings because it tracks the gantry and the lid separately; a
    profile here carries one height, so one ring.
    """
    corners = rectangle(profile)
    top = profile.height
    posts: list[Segment] = [(corner, (corner[0], corner[1], top)) for corner in corners]
    ring: list[Segment] = [
        ((a[0], a[1], top), (b[0], b[1], top))
        for a, b in zip(corners, corners[1:] + corners[:1], strict=True)
    ]
    return posts, ring
