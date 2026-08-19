# SPDX-License-Identifier: LGPL-2.1-or-later
"""The dock widget and its chrome.

Laid out like Fusion's timeline: one short row pinned to the bottom of the
window — transport controls, the feature strip, an options button — rather than
a titled panel with a header row of its own. The body name goes in the dock's
title bar, which is where the user is already looking for it.
"""

from __future__ import annotations

from collections.abc import Sequence
from html import escape
from typing import Any

from .model import TimelineEntry
from .qtcompat import Enums, QtCore, QtWidgets, translate
from .view import TimelineView

__all__ = [
    "OBJECT_NAME",
    "TimelineDock",
    "TimelinePanel",
    "placeholder_empty",
    "placeholder_no_body",
]

#: Object name used to find (and avoid duplicating) the dock in the main window.
OBJECT_NAME = "TimelineDockWidget"


def placeholder_no_body() -> str:
    """Resolved on each call, not at import: FreeCAD may set the UI language
    after this module has already been loaded."""
    return translate("No active body — activate a PartDesign body to see its timeline.")


def placeholder_empty() -> str:
    return translate("This body has no features yet.")


class TimelinePanel(QtWidgets.QWidget):  # type: ignore[misc]  # Qt shim is Any
    """Transport controls, the feature strip, and an options button, in one row."""

    #: Emitted when the "show sketches and datums" toggle changes.
    showNonSolidChanged = QtCore.Signal(bool)
    #: Emitted when the "show labels" toggle changes.
    showLabelsChanged = QtCore.Signal(bool)
    #: Tip navigation: -2 start, -1 back, +1 forward, +2 end.
    tipStepRequested = QtCore.Signal(int)

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)

        self.view = TimelineView(self)

        transport = QtWidgets.QHBoxLayout()
        transport.setContentsMargins(0, 0, 0, 0)
        transport.setSpacing(0)
        self._transport = {}
        for key, pixmap, tip in (
            (-2, Enums.SkipBackward, translate("Move tip to the start")),
            (-1, Enums.SeekBackward, translate("Step the tip back one feature")),
            (1, Enums.SeekForward, translate("Step the tip forward one feature")),
            (2, Enums.SkipForward, translate("Move tip to the end")),
        ):
            button = QtWidgets.QToolButton(self)
            button.setIcon(self.style().standardIcon(pixmap))
            button.setToolTip(tip)
            button.setAutoRaise(True)
            button.clicked.connect(
                lambda _checked=False, step=key: self.tipStepRequested.emit(step)
            )
            transport.addWidget(button)
            self._transport[key] = button

        self._options = QtWidgets.QToolButton(self)
        self._options.setText("⋮")  # vertical ellipsis
        self._options.setToolTip(translate("Timeline options"))
        self._options.setAutoRaise(True)
        self._options.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
            if hasattr(QtWidgets.QToolButton, "ToolButtonPopupMode")
            else QtWidgets.QToolButton.InstantPopup
        )
        self._options.setMenu(self._build_options_menu())
        # Structural only, no colours: drop the little dropdown triangle so the
        # button stays as narrow as Fusion's.
        self._options.setStyleSheet("QToolButton::menu-indicator { image: none; }")

        self._placeholder = QtWidgets.QLabel(placeholder_no_body(), self)
        self._placeholder.setAlignment(Enums.AlignCenter)
        self._placeholder.setEnabled(False)  # picks up the theme's disabled text

        self._stack = QtWidgets.QStackedWidget(self)
        self._stack.addWidget(self._placeholder)
        self._stack.addWidget(self.view)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(4)
        layout.addLayout(transport)
        layout.addWidget(self._stack, 1)
        layout.addWidget(self._options)

        self._body_label = ""

    # ------------------------------------------------------------------

    def _build_options_menu(self) -> QtWidgets.QMenu:
        menu = QtWidgets.QMenu(self)

        self._non_solid_action = menu.addAction(translate("Sketches and datums"))
        self._non_solid_action.setCheckable(True)
        self._non_solid_action.toggled.connect(self.showNonSolidChanged)

        self._labels_action = menu.addAction(translate("Feature names"))
        self._labels_action.setCheckable(True)
        self._labels_action.toggled.connect(self._on_labels_toggled)

        return menu

    def _on_labels_toggled(self, checked: bool) -> None:
        self.view.set_show_labels(checked)
        self.showLabelsChanged.emit(bool(checked))

    def set_transport_enabled(self, back: bool, forward: bool) -> None:
        """Grey out the steps that would run off either end."""
        self._transport[-2].setEnabled(back)
        self._transport[-1].setEnabled(back)
        self._transport[1].setEnabled(forward)
        self._transport[2].setEnabled(forward)

    # -- toggles -------------------------------------------------------

    def show_non_solid(self) -> bool:
        return bool(self._non_solid_action.isChecked())

    def set_show_non_solid(self, value: bool) -> None:
        self._non_solid_action.setChecked(bool(value))

    def show_labels(self) -> bool:
        return bool(self._labels_action.isChecked())

    def set_show_labels(self, value: bool) -> None:
        self._labels_action.setChecked(bool(value))

    # -- content -------------------------------------------------------

    def body_label(self) -> str:
        return self._body_label

    def show_placeholder(self, text: str | None = None) -> None:
        self._placeholder.setText(placeholder_no_body() if text is None else text)
        self._stack.setCurrentWidget(self._placeholder)
        self._body_label = ""
        self.set_transport_enabled(False, False)
        self.view.setEntries([], 0)
        self._retitle()

    def show_entries(
        self, body_label: str, entries: Sequence[TimelineEntry], tip_slot: int
    ) -> None:
        self._body_label = body_label
        if not entries:
            self.show_placeholder(placeholder_empty())
            self._body_label = body_label
            self._retitle()
            return
        self.view.setEntries(entries, tip_slot)
        self._stack.setCurrentWidget(self.view)
        self._retitle()

    def _retitle(self) -> None:
        """Fusion has no header row on the timeline; the body name belongs in
        the dock's title bar."""
        dock = self.parent()
        if not isinstance(dock, QtWidgets.QDockWidget):
            return
        base = translate("Timeline")
        dock.setWindowTitle(
            f"{base} — {escape(self._body_label)}" if self._body_label else base
        )


class TimelineDock(QtWidgets.QDockWidget):  # type: ignore[misc]  # Qt shim is Any
    """``QDockWidget`` hosting the panel, docked at the bottom."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(translate("Timeline"), parent)
        self.setObjectName(OBJECT_NAME)
        self.panel = TimelinePanel(self)
        self.setWidget(self.panel)
        self.setAllowedAreas(Enums.BottomDockWidgetArea | Enums.TopDockWidgetArea)

    @property
    def view(self) -> TimelineView:
        return self.panel.view
