# SPDX-License-Identifier: LGPL-2.1-or-later
"""The horizontal feature strip.

:class:`TimelineView` renders the entries produced by
:func:`freecad_timeline.model.build_timeline` and turns gestures into signals.
It performs no document mutation itself — the controller in
:mod:`freecad_timeline.integration` owns that — so the view can be driven and
inspected without a document behind it.
"""

from __future__ import annotations

from collections.abc import Sequence
from html import escape
from typing import Any

from . import theme
from .model import TimelineEntry
from .qtcompat import Enums, QtCore, QtGui, QtWidgets, event_position, translate

__all__ = ["ENTRY_ROLE", "FeatureDelegate", "TimelineView"]

#: Item data role holding the :class:`~freecad_timeline.model.TimelineEntry`.
ENTRY_ROLE = Enums.UserRole + 1

#: Icon size in the default, Fusion-like compact strip. Fusion's own timeline
#: runs about 19px per feature, which is what lets ~55 of them fit across a
#: window instead of a dozen.
ICON_SIZE_COMPACT = 20
#: Icon size once labels are shown and the strip is allowed to be tall.
ICON_SIZE_LABELLED = 32
ITEM_SPACING = 2
#: Space around the icon, and between icon and label.
ITEM_PADDING = 3
#: Widest an item may get, in "M" widths. Past this, labels elide instead of
#: stretching the strip. Expressed in em so it tracks the UI font.
LABEL_MAX_EM = 8
#: How close to the marker the pointer must be to grab it, in units of the
#: font's height so the target scales with the UI rather than staying 7px.
MARKER_GRAB_RATIO = 0.5
MARKER_GRAB_MIN = 6
#: Vertical room reserved above the strip for the rollback marker's handle.
MARKER_HANDLE = 5


def icon_size(show_labels: bool) -> int:
    return ICON_SIZE_LABELLED if show_labels else ICON_SIZE_COMPACT


def item_size(font_metrics, labels=(), show_labels: bool = False) -> QtCore.QSize:
    """Size of one feature cell.

    Compact (the default) is icon-only, matching Fusion's timeline: a single
    ~20px row so a long history stays scannable instead of scrolling after a
    dozen features. The name lives in the tooltip.

    With labels on, the cell grows to fit the text. Width is measured from the
    labels rather than a character count — ``averageCharWidth()`` under-measures
    real text badly enough to truncate names that fit — and clamped so one long
    feature name cannot stretch every cell.
    """
    icon = icon_size(show_labels)
    minimum = icon + 2 * ITEM_PADDING

    if not show_labels:
        return QtCore.QSize(minimum, minimum)

    line = font_metrics.height()
    em = max(1, font_metrics.horizontalAdvance("M"))
    maximum = max(minimum, em * LABEL_MAX_EM)
    needed = (
        max(
            (font_metrics.horizontalAdvance(str(label)) for label in labels),
            default=0,
        )
        + 2 * ITEM_PADDING
    )
    width = max(minimum, min(maximum, needed))
    height = ITEM_PADDING + icon + ITEM_PADDING + line + ITEM_PADDING
    return QtCore.QSize(width, height)


class FeatureDelegate(QtWidgets.QStyledItemDelegate):
    """Paints one feature: icon over an elided label.

    Rolled-back features fade out, suppressed ones are struck through, and both
    states also switch the icon to Qt's *disabled* rendering so the effect is
    consistent with whatever icon theme is in use.
    """

    def _show_labels(self, option) -> bool:
        widget = option.widget
        return bool(getattr(widget, "show_labels", lambda: False)())

    def sizeHint(self, option, index):
        entry = index.data(ENTRY_ROLE)
        labels = [entry.label] if entry is not None else []
        return item_size(option.fontMetrics, labels, self._show_labels(option))

    @staticmethod
    def _paint_status_badge(painter, palette, icon_rect, entry):
        """A corner badge for a failed or out-of-date feature.

        Painted at full opacity even on a dimmed (rolled-back) item: a broken
        feature is exactly what the user is scanning for, so fading it away
        would defeat the point.
        """
        painter.save()
        painter.setOpacity(1.0)

        failed = entry.failed
        color = palette.error if failed else palette.warning
        # Relative to the icon: a fixed 15px badge would swamp a compact cell.
        side = icon_rect.width()
        size = max(8, int(side * (0.48 if failed else 0.34)))
        badge = QtCore.QRect(0, 0, size, size)
        badge.moveCenter(
            QtCore.QPoint(icon_rect.right() - 1, icon_rect.top() + size // 2 - 2)
        )

        # Ring the badge in the background colour so it reads against the icon.
        painter.setPen(QtGui.QPen(palette.background, 2))
        painter.setBrush(color)
        painter.drawEllipse(badge)

        if failed:
            glyph = (
                QtGui.QColor("#ffffff")
                if color.lightness() < 150
                else QtGui.QColor("#000000")
            )
            font = QtGui.QFont(painter.font())
            font.setBold(True)
            font.setPixelSize(max(6, size - 4))
            painter.setFont(font)
            painter.setPen(QtGui.QPen(glyph))
            painter.drawText(badge, int(Enums.AlignCenter), "!")

        painter.restore()

    def paint(self, painter, option, index):
        entry: TimelineEntry | None = index.data(ENTRY_ROLE)
        if entry is None:
            super().paint(painter, option, index)
            return

        widget = option.widget
        palette = (
            theme.colors(widget)
            if widget is not None
            else theme.Palette(option.palette)
        )
        selected = bool(option.state & Enums.StateSelected)
        hovered = bool(option.state & Enums.StateMouseOver)

        painter.save()
        painter.setRenderHint(Enums.Antialiasing, True)

        rect = option.rect.adjusted(1, 1, -1, -1)

        if selected or hovered:
            fill = QtGui.QColor(palette.highlight)
            fill.setAlpha(150 if selected else 50)
            painter.setPen(Enums.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, 4, 4)

        if entry.after_tip:
            painter.setOpacity(theme.DIM_OPACITY)
        elif entry.suppressed:
            painter.setOpacity(theme.GHOST_OPACITY)

        # -- icon ---------------------------------------------------------
        show_labels = self._show_labels(option)
        side = icon_size(show_labels)
        icon = index.data(Enums.DecorationRole)
        icon_rect = QtCore.QRect(0, 0, side, side)
        if show_labels:
            icon_rect.moveCenter(
                QtCore.QPoint(rect.center().x(), rect.top() + side // 2 + ITEM_PADDING)
            )
        else:
            icon_rect.moveCenter(rect.center())
        if isinstance(icon, QtGui.QIcon) and not icon.isNull():
            mode = (
                Enums.IconDisabled
                if (entry.after_tip or entry.suppressed)
                else Enums.IconNormal
            )
            icon.paint(painter, icon_rect, Enums.AlignCenter, mode, Enums.IconOff)
        else:
            # No view provider (headless object, or an icon that failed to
            # load): draw a neutral placeholder rather than nothing.
            painter.setPen(QtGui.QPen(palette.separator, 1))
            painter.setBrush(Enums.NoBrush)
            painter.drawRoundedRect(icon_rect.adjusted(4, 4, -4, -4), 3, 3)

        # -- status badge -------------------------------------------------
        if entry.failed or entry.out_of_date:
            self._paint_status_badge(painter, palette, icon_rect, entry)

        if not show_labels:
            painter.restore()
            return

        # -- label --------------------------------------------------------
        font = QtGui.QFont(option.font)
        if entry.suppressed:
            font.setStrikeOut(True)
        if entry.is_tip:
            font.setBold(True)
        painter.setFont(font)

        if selected:
            text_color = palette.highlight_text
        elif entry.after_tip:
            text_color = palette.dim_text
        else:
            text_color = palette.text
        painter.setPen(QtGui.QPen(text_color))

        # Derived from the metrics, not from magic offsets: item_size() budgets
        # exactly one line under the icon, so anything less clips descenders.
        metrics = QtGui.QFontMetrics(font)
        text_rect = QtCore.QRect(
            rect.left() + ITEM_PADDING,
            icon_rect.bottom() + ITEM_PADDING,
            rect.width() - 2 * ITEM_PADDING,
            metrics.height(),
        )
        elided = metrics.elidedText(entry.label, Enums.ElideRight, text_rect.width())
        painter.drawText(text_rect, int(Enums.AlignHCenter | Enums.AlignTop), elided)

        painter.restore()


class TimelineView(QtWidgets.QListWidget):
    """Horizontal strip of features with a draggable rollback marker.

    Signals carry :class:`~freecad_timeline.model.TimelineEntry` objects (or
    slot indices) and never touch the document.
    """

    #: A feature was clicked; argument is the entry.
    picked = QtCore.Signal(object)
    #: A feature was double-clicked and should be opened for editing.
    editRequested = QtCore.Signal(object)
    #: The rollback marker was dropped on a slot (0 == before everything).
    tipSlotRequested = QtCore.Signal(int)
    #: Features were dragged onto a slot: (source rows, destination slot).
    moveRequested = QtCore.Signal(object, int)
    #: Delete was pressed; argument is the list of selected entries.
    deleteRequested = QtCore.Signal(object)
    #: F2 was pressed; argument is the entry to rename.
    renameRequested = QtCore.Signal(object)
    #: Right click; arguments are the entry under the cursor (or ``None``) and
    #: the global position.
    menuRequested = QtCore.Signal(object, object)

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)

        self._entries: list[TimelineEntry] = []
        self._tip_slot = 0
        self._marker_drag = False
        self._marker_preview: int | None = None
        self._drop_slot: int | None = None
        self._drag_rows: list[int] | None = None
        #: Compact (icon-only) by default, like Fusion's own timeline.
        self._show_labels = False

        self.setViewMode(Enums.IconMode)
        self.setFlow(Enums.LeftToRight)
        self.setWrapping(False)
        self.setMovement(Enums.Static)
        self.setResizeMode(Enums.Adjust)
        self.setUniformItemSizes(True)
        self.setSpacing(ITEM_SPACING)
        self.setIconSize(QtCore.QSize(*(2 * (icon_size(False),))))
        self.setSelectionMode(Enums.ExtendedSelection)
        self.setHorizontalScrollMode(Enums.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Enums.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Enums.ScrollBarAlwaysOff)
        self.setFrameShape(Enums.NoFrame)
        self.setMouseTracking(True)
        self.setItemDelegate(FeatureDelegate(self))

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)  # we draw our own
        self.setDragDropMode(Enums.DragDrop)

        self.setContextMenuPolicy(Enums.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.itemDoubleClicked.connect(self._on_double_click)

        self._apply_metrics()

    # ------------------------------------------------------------------
    # content
    # ------------------------------------------------------------------

    def show_labels(self) -> bool:
        return self._show_labels

    def set_show_labels(self, value: bool) -> None:
        """Switch between the compact icon strip and the labelled one."""
        value = bool(value)
        if value == self._show_labels:
            return
        self._show_labels = value
        self._apply_metrics()
        self.setEntries(self._entries, self._tip_slot)

    def _apply_metrics(self) -> None:
        side = icon_size(self._show_labels)
        self.setIconSize(QtCore.QSize(side, side))
        cell = item_size(
            self.fontMetrics(), [e.label for e in self._entries], self._show_labels
        )
        # The horizontal scrollbar lives inside this widget, so its height has
        # to be part of the budget — otherwise it eats into the icon row.
        bar = self.horizontalScrollBar().sizeHint().height()
        height = cell.height() + 2 * ITEM_SPACING + bar
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)

    def entries(self) -> list[TimelineEntry]:
        return list(self._entries)

    def setEntries(self, entries: Sequence[TimelineEntry], tip_slot: int) -> None:
        """Replace the strip's contents.

        The current selection is restored by object name where possible, so a
        refresh triggered by a recompute does not steal the user's place.
        """
        # Capture the *selection*, not the current item: QListWidget makes row
        # 0 current as soon as items are added, so restoring from currentItem()
        # would turn that bookkeeping into a real highlight and the first
        # feature would light up on its own after every recompute.
        previous_names = [entry.name for entry in self.selected_entries()]

        self.blockSignals(True)
        self.clear()
        self._entries = list(entries)
        self._tip_slot = tip_slot
        self._marker_preview = None
        self._drop_slot = None

        # uniformItemSizes is on, so every item shares the width the widest
        # label needs (clamped) rather than each measuring itself.
        shared_size = item_size(
            self.fontMetrics(),
            [entry.label for entry in self._entries],
            self._show_labels,
        )
        for entry in self._entries:
            item = QtWidgets.QListWidgetItem(entry.label)
            item.setData(ENTRY_ROLE, entry)
            item.setData(Enums.ToolTipRole, self._tooltip(entry))
            icon = self._icon_for(entry)
            if icon is not None:
                item.setData(Enums.DecorationRole, icon)
            item.setSizeHint(shared_size)
            flags = Enums.ItemIsEnabled | Enums.ItemIsSelectable
            if not entry.is_base:
                # "Impossible to move the base feature of a body."
                flags |= Enums.ItemIsDragEnabled
            item.setFlags(flags)
            self.addItem(item)

        if previous_names:
            self.select_names(previous_names, emit=False)
        self.blockSignals(False)
        self.viewport().update()

    @staticmethod
    def _icon_for(entry: TimelineEntry):
        """``feature.ViewObject.Icon``, or ``None`` when there is no GUI
        representation (headless object, freshly deleted proxy)."""
        try:
            view_object = getattr(entry.obj, "ViewObject", None)
            if view_object is None:
                return None
            icon = getattr(view_object, "Icon", None)
            return icon if isinstance(icon, QtGui.QIcon) else None
        except Exception:
            return None

    @staticmethod
    def _tooltip(entry: TimelineEntry) -> str:
        """Rich-text tooltip.

        Labels are user-supplied, so every interpolated value is escaped — a
        feature called ``M6 <clearance>`` would otherwise be parsed as markup
        and silently lose text.
        """
        lines = [f"<b>{escape(entry.label)}</b>"]
        if entry.name and entry.name != entry.label:
            lines.append(f"<i>{escape(entry.name)}</i>")

        notes = []
        if entry.is_base:
            notes.append(translate("base feature"))
        if entry.is_tip:
            notes.append(translate("tip"))
        if entry.suppressed:
            notes.append(translate("suppressed"))
        if entry.after_tip:
            notes.append(translate("rolled back"))
        if entry.kind != "solid":
            notes.append(translate(entry.kind))
        if notes:
            lines.append(", ".join(notes))

        if entry.failed:
            lines.append(
                "<b>{}</b><br>{}".format(
                    escape(translate("Recompute failed")),
                    escape(
                        entry.status_message or translate("This feature is in error.")
                    ),
                )
            )
        elif entry.out_of_date:
            lines.append(escape(translate("Out of date — needs a recompute.")))

        return "<br>".join(lines)

    def current_entry(self) -> TimelineEntry | None:
        item = self.currentItem()
        return item.data(ENTRY_ROLE) if item is not None else None

    def selected_entries(self) -> list[TimelineEntry]:
        """Selected entries, in timeline order."""
        rows = sorted(self.row(item) for item in self.selectedItems())
        entries = []
        for row in rows:
            entry = self.item(row).data(ENTRY_ROLE)
            if entry is not None:
                entries.append(entry)
        return entries

    def selected_rows(self) -> list[int]:
        return sorted(self.row(item) for item in self.selectedItems())

    def select_names(self, names, emit: bool = True) -> int:
        """Select every entry whose internal name is in ``names``.

        Used to mirror a multi-selection made in the model tree.  Returns how
        many rows matched.
        """
        wanted = set(names)
        blocked = self.signalsBlocked()
        if not emit:
            self.blockSignals(True)
        try:
            self.clearSelection()
            matched = 0
            first = None
            for row in range(self.count()):
                item = self.item(row)
                entry = item.data(ENTRY_ROLE)
                if entry is not None and entry.name in wanted:
                    item.setSelected(True)
                    matched += 1
                    if first is None:
                        first = item
            if first is not None:
                # setCurrentItem() would collapse an ExtendedSelection down to
                # this one row; NoUpdate moves the cursor and leaves it alone.
                self.selectionModel().setCurrentIndex(
                    self.indexFromItem(first), Enums.SelectionNoUpdate
                )
                self.scrollToItem(first)
            return matched
        finally:
            self.blockSignals(blocked)

    def clear_selection(self) -> None:
        self.blockSignals(True)
        self.clearSelection()
        self.setCurrentItem(None)
        self.blockSignals(False)

    # ------------------------------------------------------------------
    # slot geometry
    # ------------------------------------------------------------------

    def slot_positions(self) -> list[int]:
        """Viewport x for every slot boundary, ``0..count``."""
        count = self.count()
        if count == 0:
            return [self.viewport().rect().left() + 10]

        rects = [self.visualItemRect(self.item(row)) for row in range(count)]
        half = max(ITEM_SPACING // 2, 2)
        positions = [rects[0].left() - half]
        for index in range(1, count):
            positions.append((rects[index - 1].right() + rects[index].left()) // 2)
        positions.append(rects[-1].right() + half)
        return positions

    def slot_at(self, x: int) -> int:
        positions = self.slot_positions()
        return min(range(len(positions)), key=lambda i: abs(positions[i] - x))

    def _marker_x(self) -> int:
        positions = self.slot_positions()
        slot = (
            self._marker_preview if self._marker_preview is not None else self._tip_slot
        )
        slot = max(0, min(slot, len(positions) - 1))
        return positions[slot]

    def _grab_radius(self) -> int:
        return max(
            MARKER_GRAB_MIN, int(self.fontMetrics().height() * MARKER_GRAB_RATIO)
        )

    def _near_marker(self, x: int) -> bool:
        return abs(x - self._marker_x()) <= self._grab_radius()

    # ------------------------------------------------------------------
    # painting
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QtGui.QPainter(self.viewport())
        painter.setRenderHint(Enums.Antialiasing, True)
        palette = theme.colors(self)

        self._paint_marker(painter, palette)
        if self._drop_slot is not None:
            self._paint_drop_indicator(painter, palette)
        painter.end()

    def _paint_marker(self, painter, palette):
        """The rollback marker: a full-height rule with a grab handle on top."""
        if self.count() == 0:
            return

        x = self._marker_x()
        top = self.viewport().rect().top()
        bottom = self.viewport().rect().bottom()
        dragging = self._marker_drag

        rows = self.viewport().rect()
        bottom = min(bottom, rows.top() + self._row_height())

        painter.setPen(QtGui.QPen(palette.tip, 3 if dragging else 2))
        painter.drawLine(x, top + MARKER_HANDLE, x, bottom)

        # A flat cap at the top of the row rather than a tab over the icons.
        handle = QtCore.QRect(0, 0, 9, MARKER_HANDLE)
        handle.moveCenter(QtCore.QPoint(x, top + MARKER_HANDLE // 2))
        painter.setPen(Enums.NoPen)
        painter.setBrush(palette.tip)
        painter.drawRoundedRect(handle, 2, 2)

        if dragging:
            painter.setBrush(QtGui.QColor(palette.tip_shadow))
            painter.drawRect(QtCore.QRect(x - 2, top + MARKER_HANDLE, 4, bottom - top))

    def _row_height(self) -> int:
        """Height of the icon row, excluding the scrollbar underneath it."""
        if self.count():
            return self.visualItemRect(self.item(0)).height() + 2 * ITEM_SPACING
        return self.viewport().rect().height()

    def _paint_drop_indicator(self, painter, palette):
        positions = self.slot_positions()
        slot = max(0, min(self._drop_slot, len(positions) - 1))
        x = positions[slot]
        top = self.viewport().rect().top()
        bottom = top + self._row_height()

        painter.setPen(QtGui.QPen(palette.drop, 2, Enums.DashLine))
        painter.drawLine(x, top, x, bottom)

    # ------------------------------------------------------------------
    # mouse: marker dragging and selection
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Enums.LeftButton and self.count():
            position = event_position(event)
            if self._near_marker(position.x()):
                self._marker_drag = True
                self._marker_preview = self._tip_slot
                self.setCursor(Enums.SizeHorCursor)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        position = event_position(event)
        if self._marker_drag:
            self._marker_preview = self.slot_at(position.x())
            self.viewport().update()
            event.accept()
            return

        if self.count() and self._near_marker(position.x()):
            self.setCursor(Enums.SizeHorCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._marker_drag:
            slot = self._marker_preview
            self._marker_drag = False
            self._marker_preview = None
            self.unsetCursor()
            self.viewport().update()
            event.accept()
            if slot is not None and slot != self._tip_slot:
                self.tipSlotRequested.emit(slot)
            return

        released_on = self.itemAt(event_position(event))
        super().mouseReleaseEvent(event)
        # Only a click that landed on a feature is a pick; clicking the empty
        # strip must not re-select whatever happened to be current.
        if released_on is not None and event.button() == Enums.LeftButton:
            entry = released_on.data(ENTRY_ROLE)
            if entry is not None:
                self.picked.emit(entry)

    def leaveEvent(self, event):
        if not self._marker_drag:
            self.unsetCursor()
        super().leaveEvent(event)

    # ------------------------------------------------------------------
    # keyboard
    # ------------------------------------------------------------------

    def keyPressEvent(self, event):
        """Delete removes the selection, F2 renames, Return edits.

        Arrow-key navigation and Ctrl/Shift range selection come from
        QListWidget itself.
        """
        key = event.key()
        keys = QtCore.Qt.Key

        if key == keys.Key_Delete:
            entries = self.selected_entries()
            if entries:
                event.accept()
                self.deleteRequested.emit(entries)
                return
        elif key == keys.Key_F2:
            entry = self.current_entry()
            if entry is not None:
                event.accept()
                self.renameRequested.emit(entry)
                return
        elif key in (keys.Key_Return, keys.Key_Enter):
            entry = self.current_entry()
            if entry is not None:
                event.accept()
                self.editRequested.emit(entry)
                return

        super().keyPressEvent(event)

    def _on_double_click(self, item):
        entry = item.data(ENTRY_ROLE)
        if entry is not None:
            self.editRequested.emit(entry)

    def _on_context_menu(self, point):
        item = self.itemAt(point)
        entry = item.data(ENTRY_ROLE) if item is not None else None
        if item is not None and not item.isSelected():
            # Right-clicking outside the selection targets just that item;
            # right-clicking inside it keeps the whole selection.
            self.setCurrentItem(item)
        self.menuRequested.emit(entry, self.viewport().mapToGlobal(point))

    # ------------------------------------------------------------------
    # drag and drop reordering
    # ------------------------------------------------------------------

    def startDrag(self, supportedActions):
        # Drag the whole selection when the pressed row is part of it, so a
        # multi-selection reorders as a block.
        rows = self.selected_rows()
        current = self.currentRow()
        self._drag_rows = rows if current in rows else [current]
        super().startDrag(Enums.MoveAction)

    def dragEnterEvent(self, event):
        if event.source() is self:
            event.setDropAction(Enums.MoveAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.source() is not self:
            event.ignore()
            return
        self._drop_slot = self.slot_at(event_position(event).x())
        self.viewport().update()
        event.setDropAction(Enums.MoveAction)
        event.accept()

    def dragLeaveEvent(self, event):
        self._drop_slot = None
        self.viewport().update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        """Never let ``QListWidget`` move the row itself.

        The document is the source of truth: we ask the controller to reorder
        the body and then rebuild the strip from the new ``Group``.  Letting Qt
        also move the item would double-apply the change whenever the document
        edit is rejected or adjusted.
        """
        slot = self._drop_slot
        sources = self._drag_rows
        self._drop_slot = None
        self._drag_rows = None
        self.viewport().update()

        if event.source() is not self or not sources or slot is None:
            event.ignore()
            return

        event.setDropAction(Enums.IgnoreAction)
        event.accept()
        self.moveRequested.emit(list(sources), slot)
