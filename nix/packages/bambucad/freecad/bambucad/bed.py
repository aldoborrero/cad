"""The printer bed, drawn in the 3D view.

It is a Coin scene-graph node, not a document object: nothing here is saved into
the .FCStd, appears in the tree, can be selected, or gets swept up by "export
everything visible".

The geometry below is plain arithmetic so it can be tested without FreeCAD;
pivy is imported inside the functions that need it, for the same reason.
"""


def rectangle(profile):
    """The plate outline at Z=0, counter-clockwise from the origin corner."""
    return [
        (0, 0, 0),
        (profile.width, 0, 0),
        (profile.width, profile.depth, 0),
        (0, profile.depth, 0),
    ]


def zones(profile):
    """One outline per excluded zone, in the same order as the profile."""
    return [
        [
            (zone.xmin, zone.ymin, 0),
            (zone.xmax, zone.ymin, 0),
            (zone.xmax, zone.ymax, 0),
            (zone.xmin, zone.ymax, 0),
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


def scene_node(profile):
    """The whole bed as one Coin node: plate, outline, excluded zones."""
    from pivy import coin

    root = coin.SoSeparator()
    plate = rectangle(profile)
    # Measured, not eyeballed: at 0.75 transparency the first attempt rendered
    # #212223 over the #1F1F1F viewport, contrast 1.03 — invisible. This blends to
    # #3F4448, contrast 1.67 against the background and 2.23 against the shape grey,
    # so the plate reads as a surface without competing with the model on it.
    root.addChild(_face(coin, plate, (0.33, 0.36, 0.39), 0.40))
    root.addChild(_outline(coin, plate, (0.45, 0.75, 0.99)))
    for zone in zones(profile):
        # Kept clearly above the plate: blends to #AA3E34, contrast 2.71.
        root.addChild(_face(coin, zone, (0.90, 0.30, 0.24), 0.30))
    return root


def show(profile):
    """Draw the bed in the active 3D view, replacing whatever was there."""
    global _drawn
    import FreeCADGui
    from PySide import QtCore
    from pivy import coin

    hide()
    view = FreeCADGui.ActiveDocument.ActiveView
    graph = view.getSceneGraph()

    switch = coin.SoSwitch()
    switch.addChild(scene_node(profile))
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
