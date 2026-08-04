"""The printer bed, drawn in the 3D view.

It is a Coin scene-graph node, not a document object: nothing here is saved into
the .FCStd, appears in the tree, can be selected, or gets swept up by "export
everything visible".

The geometry below is plain arithmetic so it can be tested without FreeCAD;
pivy is imported inside the functions that need it, for the same reason.
"""

from freecad.bambucad import fit

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
DEFAULT_COLOURS = {
    "plate": "#444747",  # 1.76 against the viewport
    "grid": "#6E6E76",  # 1.86 against the plate it is drawn on
    "grid_bold": "#8A8D93",  # every fifth line, as Bambu does
    "zone": "#A5A8A8",  # 3.92 against the plate
}


def parse_colour(value):
    """ "#RRGGBB" as the 0..1 floats Coin wants. Raises ValueError on rubbish."""
    digits = str(value).lstrip("#")
    if len(digits) != 6:
        raise ValueError(f"expected #RRGGBB, got {value!r}")
    return tuple(int(digits[i : i + 2], 16) / 255 for i in (0, 2, 4))


def colour_from_uint(value):
    """Gui::PrefColorButton stores 0xRRGGBBAA; drop the alpha, keep the hex."""
    return "#%06X" % ((int(value) >> 8) & 0xFFFFFF)


def colours(overrides):
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


def grid(profile):
    """Grid segments in model coordinates, split into (thin, bold).

    10 mm apart with every fifth line bolder, which is what calc_gridlines does.
    """
    dx, dy = fit.offset(profile)
    thin, bold = [], []
    for axis, (length, other) in enumerate(
        ((profile.width, profile.depth), (profile.depth, profile.width))
    ):
        count = 0
        position = 0.0
        while position <= length + 1e-9:
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


def rectangle(profile):
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


def zones(profile):
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


_drawn = None  # (scene graph, switch) of the bed currently in a view


def _material(coin, colour, transparency):
    material = coin.SoMaterial()
    material.diffuseColor.setValue(*colour)
    material.transparency.setValue(transparency)
    return material


def _face(coin, points, colour, transparency):
    node = coin.SoSeparator()
    node.addChild(_material(coin, colour, transparency))
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, len(points), points)
    node.addChild(coords)
    face = coin.SoFaceSet()
    face.numVertices.setValue(len(points))
    node.addChild(face)
    return node


def _outline(coin, points, colour):
    node = coin.SoSeparator()
    node.addChild(_material(coin, colour, 0.0))
    style = coin.SoDrawStyle()
    style.lineWidth.setValue(2)
    node.addChild(style)
    closed = list(points) + [points[0]]
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, len(closed), closed)
    node.addChild(coords)
    line = coin.SoLineSet()
    line.numVertices.setValue(len(closed))
    node.addChild(line)
    return node


def _segments(coin, lines, colour, width):
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


def scene_node(profile, palette=None):
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
    return root


def show(profile, palette=None, placement=None):
    """Draw the bed in the active 3D view, replacing whatever was there."""
    global _drawn
    import FreeCADGui
    from PySide import QtCore
    from pivy import coin

    hide()
    view = FreeCADGui.ActiveDocument.ActiveView
    graph = view.getSceneGraph()

    switch = coin.SoSwitch()
    switch.addChild(_placed(scene_node(profile, palette), placement))
    switch.whichChild = 0
    _drawn = (graph, switch)

    # Deferred on purpose: inserting while an event handler is running mutates the
    # graph mid-traversal, which is the trap FreeCAD's own trackers document.
    QtCore.QTimer.singleShot(0, lambda: graph.addChild(switch))


def hide():
    """Take the bed back out of the view. Safe when nothing is drawn."""
    global _drawn
    if _drawn is None:
        return
    graph, switch = _drawn
    _drawn = None
    if graph.findChild(switch) >= 0:
        graph.removeChild(switch)


def visible():
    return _drawn is not None


def _placed(node, placement):
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


def placement_from_face(face):
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


def under(shapes):
    """The placement that puts the plate under the lowest point of `shapes`."""
    import FreeCAD

    if not shapes:
        return FreeCAD.Placement()
    lowest = min(shape.BoundBox.ZMin for shape in shapes)
    return FreeCAD.Placement(FreeCAD.Vector(0, 0, lowest), FreeCAD.Rotation())
