# SPDX-License-Identifier: LGPL-2.1-or-later
"""Qt import shim and enum access that works on both Qt5 and Qt6 builds.

FreeCAD ships a ``PySide`` alias package that points at PySide2 on Qt5 builds
and PySide6 on Qt6 builds, so ``from PySide import QtCore, QtGui, QtWidgets``
is the portable spelling inside FreeCAD.  The direct PySide6/PySide2 fallbacks
exist only so this module can be imported outside FreeCAD (linting, IDEs).

Qt6 moved enum members into scoped enum classes: ``Qt.BottomDockWidgetArea``
became ``Qt.DockWidgetArea.BottomDockWidgetArea``.  PySide6 usually still
accepts the short form, but that forgiving lookup can be disabled, so
:func:`enum_of` resolves the scoped name first and falls back to the flat one.
"""

from __future__ import annotations

try:  # inside FreeCAD
    from PySide import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover - only outside FreeCAD
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtGui, QtWidgets

__all__ = [
    "CONTEXT",
    "Enums",
    "Qt",
    "QtCore",
    "QtGui",
    "QtWidgets",
    "enum_of",
    "translate",
]

Qt = QtCore.Qt

#: Translation context for every user-facing string in the addon.
CONTEXT = "Timeline"


def translate(text: str, disambiguation: str | None = None, n: int = -1) -> str:
    """Mark and translate a user-facing string.

    Calls are resolved at runtime, not at import, so a language chosen after
    the module loads still applies.  ``lupdate`` scans for this to build the
    ``.ts`` catalogues; see ``resources/translations/README.md``.

    Pass ``n`` for strings containing ``%n`` so translators can supply the
    plural forms their language needs; Qt substitutes the number itself. With
    no catalogue loaded Qt falls back to the source text, which still has to
    read correctly — hence the "%n feature(s)" phrasing.

    Only the Qt layer uses this — :mod:`.model` and :mod:`.commands` stay free
    of Qt, so their transaction names (which land in the Edit ▸ Undo label)
    remain untranslated English.
    """
    return QtCore.QCoreApplication.translate(CONTEXT, text, disambiguation, n)


def enum_of(owner, name, *scopes):
    """Resolve an enum member across Qt5/Qt6 spellings.

    Tries ``owner.<scope>.<name>`` for each scope in turn, then ``owner.<name>``.
    """
    for scope in scopes:
        holder = getattr(owner, scope, None)
        if holder is not None:
            member = getattr(holder, name, None)
            if member is not None:
                return member
    member = getattr(owner, name, None)
    if member is None:
        raise AttributeError(
            "Cannot resolve {}.{} (scopes tried: {})".format(
                owner, name, ", ".join(scopes)
            )
        )
    return member


class Enums:
    """The enum members the timeline uses, resolved once at import time."""

    # Qt namespace
    BottomDockWidgetArea = enum_of(Qt, "BottomDockWidgetArea", "DockWidgetArea")
    TopDockWidgetArea = enum_of(Qt, "TopDockWidgetArea", "DockWidgetArea")
    RichText = enum_of(Qt, "RichText", "TextFormat")
    NoBrush = enum_of(Qt, "NoBrush", "BrushStyle")
    Vertical = enum_of(Qt, "Vertical", "Orientation")
    ScrollBarAsNeeded = enum_of(Qt, "ScrollBarAsNeeded", "ScrollBarPolicy")
    ScrollBarAlwaysOff = enum_of(Qt, "ScrollBarAlwaysOff", "ScrollBarPolicy")
    CustomContextMenu = enum_of(Qt, "CustomContextMenu", "ContextMenuPolicy")
    ElideRight = enum_of(Qt, "ElideRight", "TextElideMode")
    AlignCenter = enum_of(Qt, "AlignCenter", "AlignmentFlag")
    AlignHCenter = enum_of(Qt, "AlignHCenter", "AlignmentFlag")
    AlignTop = enum_of(Qt, "AlignTop", "AlignmentFlag")
    LeftButton = enum_of(Qt, "LeftButton", "MouseButton")
    UserRole = enum_of(Qt, "UserRole", "ItemDataRole")
    ToolTipRole = enum_of(Qt, "ToolTipRole", "ItemDataRole")
    DecorationRole = enum_of(Qt, "DecorationRole", "ItemDataRole")
    MoveAction = enum_of(Qt, "MoveAction", "DropAction")
    IgnoreAction = enum_of(Qt, "IgnoreAction", "DropAction")
    SizeHorCursor = enum_of(Qt, "SizeHorCursor", "CursorShape")
    ItemIsEnabled = enum_of(Qt, "ItemIsEnabled", "ItemFlag")
    ItemIsSelectable = enum_of(Qt, "ItemIsSelectable", "ItemFlag")
    ItemIsDragEnabled = enum_of(Qt, "ItemIsDragEnabled", "ItemFlag")
    DashLine = enum_of(Qt, "DashLine", "PenStyle")
    NoPen = enum_of(Qt, "NoPen", "PenStyle")

    # QListView / QAbstractItemView
    IconMode = enum_of(QtWidgets.QListView, "IconMode", "ViewMode")
    LeftToRight = enum_of(QtWidgets.QListView, "LeftToRight", "Flow")
    Static = enum_of(QtWidgets.QListView, "Static", "Movement")
    Adjust = enum_of(QtWidgets.QListView, "Adjust", "ResizeMode")
    ExtendedSelection = enum_of(
        QtWidgets.QAbstractItemView, "ExtendedSelection", "SelectionMode"
    )
    DragDrop = enum_of(QtWidgets.QAbstractItemView, "DragDrop", "DragDropMode")
    ScrollPerPixel = enum_of(
        QtWidgets.QAbstractItemView, "ScrollPerPixel", "ScrollMode"
    )
    NoFrame = enum_of(QtWidgets.QFrame, "NoFrame", "Shape")

    # QPalette
    ColorActive = enum_of(QtGui.QPalette, "Active", "ColorGroup")
    ColorDisabled = enum_of(QtGui.QPalette, "Disabled", "ColorGroup")
    RoleText = enum_of(QtGui.QPalette, "Text", "ColorRole")
    RoleWindowText = enum_of(QtGui.QPalette, "WindowText", "ColorRole")
    RoleWindow = enum_of(QtGui.QPalette, "Window", "ColorRole")
    RoleBase = enum_of(QtGui.QPalette, "Base", "ColorRole")
    RoleHighlight = enum_of(QtGui.QPalette, "Highlight", "ColorRole")
    RoleHighlightedText = enum_of(QtGui.QPalette, "HighlightedText", "ColorRole")
    RoleMid = enum_of(QtGui.QPalette, "Mid", "ColorRole")
    RoleButton = enum_of(QtGui.QPalette, "Button", "ColorRole")
    RoleButtonText = enum_of(QtGui.QPalette, "ButtonText", "ColorRole")

    # QMessageBox
    YesRole = enum_of(QtWidgets.QMessageBox, "YesRole", "ButtonRole")
    NoRole = enum_of(QtWidgets.QMessageBox, "NoRole", "ButtonRole")
    ButtonYes = enum_of(QtWidgets.QMessageBox, "Yes", "StandardButton")
    ButtonNo = enum_of(QtWidgets.QMessageBox, "No", "StandardButton")
    ButtonCancel = enum_of(QtWidgets.QMessageBox, "Cancel", "StandardButton")

    # QItemSelectionModel
    SelectionNoUpdate = enum_of(QtCore.QItemSelectionModel, "NoUpdate", "SelectionFlag")

    # QStyle standard pixmaps — the theme's own media glyphs, so the transport
    # controls match whatever icon set FreeCAD is using.
    SkipBackward = enum_of(QtWidgets.QStyle, "SP_MediaSkipBackward", "StandardPixmap")
    SeekBackward = enum_of(QtWidgets.QStyle, "SP_MediaSeekBackward", "StandardPixmap")
    SeekForward = enum_of(QtWidgets.QStyle, "SP_MediaSeekForward", "StandardPixmap")
    SkipForward = enum_of(QtWidgets.QStyle, "SP_MediaSkipForward", "StandardPixmap")

    # QStyle state flags
    StateSelected = enum_of(QtWidgets.QStyle, "State_Selected", "StateFlag")
    StateMouseOver = enum_of(QtWidgets.QStyle, "State_MouseOver", "StateFlag")

    # misc
    Antialiasing = enum_of(QtGui.QPainter, "Antialiasing", "RenderHint")
    IconNormal = enum_of(QtGui.QIcon, "Normal", "Mode")
    IconDisabled = enum_of(QtGui.QIcon, "Disabled", "Mode")
    IconOff = enum_of(QtGui.QIcon, "Off", "State")


def exec_widget(widget, *args):
    """Run a modal ``QMenu``/``QDialog``.

    Qt6 renamed ``exec_()`` to ``exec()``; PySide2 only has the former.
    """
    runner = getattr(widget, "exec_", None) or widget.exec
    return runner(*args)


def event_position(event):
    """Local event position as a ``QPoint``, on Qt5 and Qt6.

    Qt6 deprecated ``QMouseEvent.pos()``/``QDropEvent.pos()`` in favour of
    ``position()``, which returns a ``QPointF``.
    """
    getter = getattr(event, "position", None)
    if getter is not None:
        return getter().toPoint()
    return event.pos()
