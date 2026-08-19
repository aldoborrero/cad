# SPDX-License-Identifier: LGPL-2.1-or-later
"""Render the real Timeline widget offscreen to PNGs.

Uses the addon's actual view/panel/theme code — the only thing faked is the
document behind it and the feature icons (real ones come from
feature.ViewObject.Icon, which needs a FreeCAD GUI).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from freecad_timeline import model
from freecad_timeline.panel import TimelineDock
from freecad_timeline.qtcompat import Enums, QtCore, QtGui, QtWidgets
from tests.fakes import FakeBody, FakeDocument, FakeFeature, FakeObject

OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "resources",
    "screenshots",
)
os.makedirs(OUT, exist_ok=True)

app = QtWidgets.QApplication([])


# ---------------------------------------------------------------------------
# stand-in feature icons (real ones come from the view provider)
# ---------------------------------------------------------------------------


def _icon(draw):
    pixmap = QtGui.QPixmap(64, 64)
    pixmap.fill(QtGui.QColor(0, 0, 0, 0))
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(Enums.Antialiasing, True)
    draw(painter)
    painter.end()
    return QtGui.QIcon(pixmap)


BLUE = QtGui.QColor("#4d7ea8")
STEEL = QtGui.QColor("#93a4b3")
YELLOW = QtGui.QColor("#d9b45b")
RED = QtGui.QColor("#c1543f")


def _solid_base(painter, color=BLUE):
    painter.setPen(QtGui.QPen(QtGui.QColor("#2c4a63"), 3))
    painter.setBrush(color)
    painter.drawRect(12, 22, 40, 30)


def draw_pad(painter):
    _solid_base(painter)
    painter.setBrush(YELLOW)
    painter.setPen(QtGui.QPen(QtGui.QColor("#8a6f28"), 3))
    painter.drawRect(12, 8, 40, 16)


def draw_pocket(painter):
    _solid_base(painter)
    painter.setBrush(QtGui.QColor("#22303c"))
    painter.setPen(QtGui.QPen(QtGui.QColor("#2c4a63"), 3))
    painter.drawEllipse(22, 26, 20, 20)


def draw_fillet(painter):
    painter.setPen(QtGui.QPen(QtGui.QColor("#2c4a63"), 3))
    painter.setBrush(BLUE)
    path = QtGui.QPainterPath()
    path.moveTo(12, 52)
    path.lineTo(12, 30)
    path.quadTo(12, 12, 32, 12)
    path.lineTo(52, 12)
    path.lineTo(52, 52)
    path.closeSubpath()
    painter.drawPath(path)


def draw_chamfer(painter):
    painter.setPen(QtGui.QPen(QtGui.QColor("#2c4a63"), 3))
    painter.setBrush(BLUE)
    points = [(12, 52), (12, 28), (30, 12), (52, 12), (52, 52)]
    painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y) for x, y in points]))


def draw_pattern(painter):
    painter.setPen(QtGui.QPen(QtGui.QColor("#2c4a63"), 2))
    painter.setBrush(BLUE)
    for column in range(3):
        for row in range(2):
            painter.drawRect(10 + column * 17, 18 + row * 20, 13, 15)


def draw_sketch(painter):
    painter.setPen(QtGui.QPen(QtGui.QColor("#8f9ba8"), 3))
    painter.setBrush(QtGui.QColor(0, 0, 0, 0))
    painter.drawRect(12, 16, 40, 34)
    painter.setPen(QtGui.QPen(RED, 4))
    for x, y in ((12, 16), (52, 16), (12, 50), (52, 50)):
        painter.drawPoint(x, y)


def draw_datum(painter):
    painter.setPen(QtGui.QPen(QtGui.QColor("#7a8b57"), 3))
    painter.setBrush(QtGui.QColor(154, 180, 110, 130))
    points = [(8, 40), (34, 20), (56, 28), (30, 48)]
    painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x, y) for x, y in points]))


ICONS = {
    "Pad": _icon(draw_pad),
    "Pocket": _icon(draw_pocket),
    "Fillet": _icon(draw_fillet),
    "Chamfer": _icon(draw_chamfer),
    "LinearPattern": _icon(draw_pattern),
    "Sketch": _icon(draw_sketch),
    "Datum": _icon(draw_datum),
}


class ViewObject:
    def __init__(self, icon):
        self.Icon = icon


# ---------------------------------------------------------------------------
# a plausible body
# ---------------------------------------------------------------------------


def build_body():
    doc = FakeDocument()
    body = FakeBody(document=doc, label="Bracket")
    doc.add(body)

    sketch = FakeObject(
        "Sketch", "Sketcher::SketchObject", label="Profile", document=doc
    )
    sketch.ViewObject = ViewObject(ICONS["Sketch"])
    doc.add(sketch)
    body.addObject(sketch)

    plane = FakeObject(
        "DatumPlane", "PartDesign::Plane", label="Mount plane", document=doc
    )
    plane.ViewObject = ViewObject(ICONS["Datum"])
    doc.add(plane)

    features = [
        ("Pad", "PartDesign::Pad", "Base plate", "Pad"),
        ("Pocket", "PartDesign::Pocket", "Cable slot", "Pocket"),
        ("Fillet", "PartDesign::Fillet", "Edge fillet", "Fillet"),
        ("LinearPattern", "PartDesign::LinearPattern", "Bolt holes", "LinearPattern"),
        ("Chamfer", "PartDesign::Chamfer", "Lip chamfer", "Chamfer"),
    ]
    made = {}
    for name, type_id, label, icon in features:
        kwargs = {}
        if type_id == "PartDesign::LinearPattern":
            kwargs = {"TransformMode": "Features", "Originals": [made["Pocket"]]}
        feature = FakeFeature(name, type_id, label=label, document=doc, **kwargs)
        feature.ViewObject = ViewObject(ICONS[icon])
        doc.add(feature)
        body.addObject(feature)
        made[name] = feature

    body.Group.insert(3, plane)  # datum sits between fillet and pattern
    return doc, body, made


# ---------------------------------------------------------------------------
# palettes
# ---------------------------------------------------------------------------


def light_palette():
    return QtGui.QPalette()


def dark_palette(window, base, text, highlight, disabled):
    palette = QtGui.QPalette()
    palette.setColor(Enums.RoleWindow, QtGui.QColor(window))
    palette.setColor(Enums.RoleBase, QtGui.QColor(base))
    palette.setColor(Enums.RoleText, QtGui.QColor(text))
    palette.setColor(Enums.RoleWindowText, QtGui.QColor(text))
    palette.setColor(Enums.RoleHighlight, QtGui.QColor(highlight))
    palette.setColor(Enums.RoleHighlightedText, QtGui.QColor("#ffffff"))
    palette.setColor(Enums.RoleMid, QtGui.QColor("#55595e"))
    # Without these the scrollbar renders in default light chrome against a
    # dark window, which is a lie about how it looks under a real dark theme.
    palette.setColor(Enums.RoleButton, QtGui.QColor(window))
    palette.setColor(Enums.RoleButtonText, QtGui.QColor(text))
    palette.setColor(Enums.ColorDisabled, Enums.RoleText, QtGui.QColor(disabled))
    palette.setColor(Enums.ColorDisabled, Enums.RoleWindowText, QtGui.QColor(disabled))
    return palette


PRODARK = dark_palette("#333333", "#2a2a2a", "#d6d6d6", "#3d7eb8", "#7a7a7a")
OPENDARK = dark_palette("#21252b", "#1b1f24", "#cdd3de", "#4b7bec", "#6b7280")


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------


DOCK_HEIGHT = 34  # the compact strip, like Fusion's


def make_dock(palette, width=940, height=None):
    window = QtWidgets.QMainWindow()
    window.setPalette(palette)
    central = QtWidgets.QWidget()
    window.setCentralWidget(central)

    dock = TimelineDock()
    dock.setPalette(palette)
    window.addDockWidget(Enums.BottomDockWidgetArea, dock)
    window.resize(width, 400)
    window.show()
    # Give the dock the height it would actually settle at, instead of every
    # pixel the main window has left over.
    window.resizeDocks([dock], [height or DOCK_HEIGHT], Enums.Vertical)
    QtWidgets.QApplication.processEvents()
    return window, dock


def render(widget, path, scale=2):
    QtWidgets.QApplication.processEvents()
    size = widget.size()
    pixmap = QtGui.QPixmap(size * scale)
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(widget.palette().color(Enums.RoleWindow))
    widget.render(pixmap)
    pixmap.save(path)
    print("wrote", path, pixmap.width(), "x", pixmap.height())
    return pixmap


def populate(dock, body, show_non_solid=False, select=None, show_labels=False):
    entries = model.build_timeline(body, show_non_solid=show_non_solid)
    dock.panel.set_show_non_solid(show_non_solid)
    dock.panel.set_show_labels(show_labels)
    dock.panel.show_entries(body.Label, entries, model.tip_slot(entries))
    if select:
        dock.view.select_names({select}, emit=False)
    QtWidgets.QApplication.processEvents()
    return entries


def build_long_body(count=34):
    """A deep history — the case the compact strip exists for."""
    doc, body, made = build_body()
    icons = ["Pad", "Pocket", "Fillet", "Chamfer", "LinearPattern"]
    types = [
        "PartDesign::Pad",
        "PartDesign::Pocket",
        "PartDesign::Fillet",
        "PartDesign::Chamfer",
        "PartDesign::Pad",
    ]
    for index in range(count):
        icon = icons[index % len(icons)]
        feature = FakeFeature(
            f"Extra{index}",
            types[index % len(types)],
            label=f"Feature {index + 1}",
            document=doc,
        )
        feature.ViewObject = ViewObject(ICONS[icon])
        doc.add(feature)
        body.addObject(feature)
    return doc, body, made


# 0 — a deep history in the compact strip
doc, body, parts = build_long_body()
body.Tip = body.Group[24]
window0, dock0 = make_dock(PRODARK)
populate(dock0, body)
render(dock0, os.path.join(OUT, "00-compact-long.png"))

# 1 — light theme, everything up to date
doc, body, parts = build_body()
window, dock = make_dock(light_palette())
populate(dock, body, select="Fillet")
render(dock, os.path.join(OUT, "01-light.png"))

# 2 — ProDark, rolled back to the fillet, pattern suppressed
doc, body, parts = build_body()
body.Tip = parts["Fillet"]
parts["LinearPattern"].Suppressed = True
window2, dock2 = make_dock(PRODARK)
populate(dock2, body, select="Pocket")
render(dock2, os.path.join(OUT, "02-prodark-rollback.png"))

# 3 — OpenTheme dark with sketches and datums shown
doc, body, parts = build_body()
body.Tip = parts["Chamfer"]
window3, dock3 = make_dock(OPENDARK)
populate(dock3, body, show_non_solid=True)
render(dock3, os.path.join(OUT, "03-opendark-non-solid.png"))

# 4 — mid-drag: drop indicator plus the marker being dragged
doc, body, parts = build_body()
body.Tip = parts["Fillet"]
window4, dock4 = make_dock(PRODARK)
populate(dock4, body, select="Chamfer")
dock4.view._drop_slot = 1
dock4.view._marker_drag = True
dock4.view._marker_preview = 3
render(dock4, os.path.join(OUT, "04-dragging.png"))

# 4b — a failed feature and an out-of-date one
doc, body, parts = build_body()
parts["Pocket"].State = ["Invalid"]
parts["Pocket"]._status_string = "Pocket: Resulting shape is empty"
parts["Chamfer"].State = ["Touched"]
window4b, dock4b = make_dock(PRODARK)
populate(dock4b, body)
render(dock4b, os.path.join(OUT, "07-status.png"))

# 4c — the same strip with feature names turned on
doc, body, parts = build_body()
body.Tip = parts["Fillet"]
window4c, dock4c = make_dock(PRODARK, height=90)
populate(dock4c, body, show_labels=True)
render(dock4c, os.path.join(OUT, "08-labels-on.png"))

# 5 — placeholder, no active body
window5, dock5 = make_dock(PRODARK)
dock5.panel.show_placeholder()
render(dock5, os.path.join(OUT, "05-placeholder.png"))

# 6 — context menu, composited over the strip
doc, body, parts = build_body()
body.Tip = parts["Fillet"]
window6, dock6 = make_dock(PRODARK)
entries = populate(dock6, body, select="LinearPattern")

menu = QtWidgets.QMenu()
menu.setPalette(PRODARK)
pattern = next(e for e in entries if e.name == "LinearPattern")
for text, enabled, checkable in [
    ("Set tip here", True, False),
    ("Suppress", True, False),
    (None, None, None),
    ("Rename…", True, False),
    ("Delete", True, False),
    (None, None, None),
    ("Move tip to start", True, False),
    ("Move tip to end", True, False),
    (None, None, None),
    ("Show sketches and datums", True, True),
]:
    if text is None:
        menu.addSeparator()
        continue
    action = menu.addAction(text)
    action.setEnabled(enabled)
    if checkable:
        action.setCheckable(True)
menu.adjustSize()
QtWidgets.QApplication.processEvents()

SCALE = 2
menu_pixmap = QtGui.QPixmap(menu.size() * SCALE)
menu_pixmap.setDevicePixelRatio(SCALE)
menu_pixmap.fill(PRODARK.color(Enums.RoleWindow))
menu.render(menu_pixmap)

dock_pixmap = QtGui.QPixmap(dock6.size() * SCALE)
dock_pixmap.setDevicePixelRatio(SCALE)
dock_pixmap.fill(PRODARK.color(Enums.RoleWindow))
dock6.render(dock_pixmap)

# A bottom dock has no room below it, so Qt opens the menu upward. Reserve
# space above the dock for it and tint it like the 3D view behind.
item_rect = dock6.view.visualItemRect(dock6.view.item(3))
anchor = dock6.view.viewport().mapTo(dock6, item_rect.topLeft())

above = menu.height() + 16
canvas = QtGui.QPixmap(QtCore.QSize(dock6.width(), dock6.height() + above) * SCALE)
canvas.setDevicePixelRatio(SCALE)

painter = QtGui.QPainter(canvas)
painter.setRenderHint(Enums.Antialiasing, True)
painter.fillRect(QtCore.QRect(0, 0, dock6.width(), above), QtGui.QColor("#3c4147"))
painter.drawPixmap(QtCore.QPoint(0, above), dock_pixmap)

origin = QtCore.QPoint(anchor.x() + 8, above + anchor.y() - menu.height())
painter.fillRect(
    QtCore.QRect(origin.x() + 4, origin.y() + 4, menu.width(), menu.height()),
    QtGui.QColor(0, 0, 0, 100),
)
painter.drawPixmap(origin, menu_pixmap)
painter.setPen(QtGui.QPen(QtGui.QColor("#4a4a4a")))
painter.drawRect(
    QtCore.QRect(origin.x(), origin.y(), menu.width() - 1, menu.height() - 1)
)
painter.end()

canvas.save(os.path.join(OUT, "06-context-menu.png"))
print(
    "wrote",
    os.path.join(OUT, "06-context-menu.png"),
    canvas.width(),
    "x",
    canvas.height(),
)
