# SPDX-License-Identifier: LGPL-2.1-or-later
"""Qt-layer smoke tests.

These run offscreen (``QT_QPA_PLATFORM=offscreen``) and are skipped entirely
when no Qt binding is importable, so the suite still passes in a bare
interpreter.  They cover the parts of the widget that are easy to get wrong
without a screen: slot geometry, marker placement, the drop-to-slot
translation, and — by actually rendering — that no paint path raises.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("freecad_timeline.qtcompat", reason="no Qt binding available")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from freecad_timeline import model
from freecad_timeline.panel import (
    TimelinePanel,
    placeholder_empty,
    placeholder_no_body,
)
from freecad_timeline.qtcompat import QtGui, QtWidgets
from freecad_timeline.view import ENTRY_ROLE, TimelineView

from .fakes import FakeBody, FakeDocument, FakeFeature


@pytest.fixture(autouse=True)
def _cleanup(destroy_widgets):
    """Route the shared teardown through autouse for this module."""


@pytest.fixture
def body_with_four_pads():
    doc = FakeDocument()
    body = FakeBody(document=doc)
    doc.add(body)
    pads = []
    for name in ("Pad", "Pocket", "Fillet", "Chamfer"):
        pad = FakeFeature(name, document=doc)
        doc.add(pad)
        body.addObject(pad)
        pads.append(pad)
    body.Tip = pads[2]
    return doc, body, pads


@pytest.fixture
def view(qapp, body_with_four_pads):
    _doc, body, _pads = body_with_four_pads
    widget = TimelineView()
    widget.resize(600, 90)
    entries = model.build_timeline(body)
    widget.setEntries(entries, model.tip_slot(entries))
    widget.show()
    QtWidgets.QApplication.processEvents()
    return widget


# --------------------------------------------------------------------------
# content
# --------------------------------------------------------------------------


def test_entries_populate_items(view):
    assert view.count() == 4
    assert [view.item(i).data(ENTRY_ROLE).name for i in range(4)] == [
        "Pad",
        "Pocket",
        "Fillet",
        "Chamfer",
    ]


def test_tooltip_mentions_state(view):
    from freecad_timeline.qtcompat import Enums

    tip_item = view.item(2)
    tooltip = tip_item.data(Enums.ToolTipRole)
    assert "tip" in tooltip

    rolled_back = view.item(3).data(Enums.ToolTipRole)
    assert "rolled back" in rolled_back


def test_tooltip_escapes_labels(qapp, body_with_four_pads):
    """Labels are user text; unescaped they would be parsed as markup."""
    from freecad_timeline.qtcompat import Enums

    _doc, body, pads = body_with_four_pads
    pads[0].Label = "M6 <clearance> & tap"

    widget = TimelineView()
    entries = model.build_timeline(body)
    widget.setEntries(entries, model.tip_slot(entries))

    tooltip = widget.item(0).data(Enums.ToolTipRole)
    assert "&lt;clearance&gt;" in tooltip
    assert "&amp;" in tooltip
    assert "<clearance>" not in tooltip


def test_tooltip_reports_the_recompute_error(qapp, body_with_four_pads):
    from freecad_timeline.qtcompat import Enums

    _doc, body, pads = body_with_four_pads
    pads[1].State = ["Invalid"]
    pads[1]._status_string = "Pocket: Resulting shape is empty"

    widget = TimelineView()
    entries = model.build_timeline(body)
    widget.setEntries(entries, model.tip_slot(entries))

    tooltip = widget.item(1).data(Enums.ToolTipRole)
    assert "Recompute failed" in tooltip
    assert "Resulting shape is empty" in tooltip


def test_tooltip_escapes_the_error_message(qapp, body_with_four_pads):
    from freecad_timeline.qtcompat import Enums

    _doc, body, pads = body_with_four_pads
    pads[1].State = ["Invalid"]
    pads[1]._status_string = "failed on <Edge1>"

    widget = TimelineView()
    entries = model.build_timeline(body)
    widget.setEntries(entries, model.tip_slot(entries))

    assert "&lt;Edge1&gt;" in widget.item(1).data(Enums.ToolTipRole)


def test_tooltip_flags_out_of_date(qapp, body_with_four_pads):
    from freecad_timeline.qtcompat import Enums

    _doc, body, pads = body_with_four_pads
    pads[0].State = ["Touched"]

    widget = TimelineView()
    entries = model.build_timeline(body)
    widget.setEntries(entries, model.tip_slot(entries))

    assert "Out of date" in widget.item(0).data(Enums.ToolTipRole)


def test_base_feature_is_not_draggable(qapp):
    from freecad_timeline.qtcompat import Enums

    from .fakes import FakeObject

    doc = FakeDocument()
    body = FakeBody(document=doc)
    doc.add(body)
    base = FakeObject("Box", "Part::Box", document=doc)
    body.BaseFeature = base
    pad = FakeFeature("Pad", document=doc)
    doc.add(pad)
    body.addObject(pad)

    widget = TimelineView()
    entries = model.build_timeline(body, show_non_solid=True)
    widget.setEntries(entries, model.tip_slot(entries))

    assert not (widget.item(0).flags() & Enums.ItemIsDragEnabled)
    assert widget.item(1).flags() & Enums.ItemIsDragEnabled


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------


def test_slot_positions_are_monotonic_and_bracket_the_items(view):
    positions = view.slot_positions()
    assert len(positions) == view.count() + 1
    assert positions == sorted(positions)
    assert positions[0] < view.visualItemRect(view.item(0)).center().x()
    assert positions[-1] > view.visualItemRect(view.item(3)).center().x()


def test_slot_at_snaps_to_nearest_boundary(view):
    positions = view.slot_positions()
    for index, x in enumerate(positions):
        assert view.slot_at(x) == index
    # A point in the middle of item 1 is closer to boundary 1 or 2, never 0.
    middle = view.visualItemRect(view.item(1)).center().x()
    assert view.slot_at(middle) in (1, 2)


def test_marker_sits_at_the_tip_boundary(view):
    positions = view.slot_positions()
    # Tip is the third feature, so the marker belongs after 3 items.
    assert view._marker_x() == positions[3]


def test_marker_at_start_when_no_tip(qapp, body_with_four_pads):
    _doc, body, _pads = body_with_four_pads
    body.Tip = None
    widget = TimelineView()
    widget.resize(600, 90)
    entries = model.build_timeline(body)
    widget.setEntries(entries, model.tip_slot(entries))
    assert widget._marker_x() == widget.slot_positions()[0]
    assert all(entry.dimmed for entry in entries)


def test_item_size_grows_with_the_font(qapp):
    """The strip used to be a fixed 88x68 regardless of the UI font, so a large
    font just meant more elision."""
    from freecad_timeline.view import item_size

    small = QtGui.QFontMetrics(QtGui.QFont("Sans", 8))
    large = QtGui.QFontMetrics(QtGui.QFont("Sans", 20))
    labels = ["Base plate"]

    assert (
        item_size(large, labels, True).height()
        > item_size(small, labels, True).height()
    )
    assert (
        item_size(large, labels, True).width() > item_size(small, labels, True).width()
    )


def test_compact_cells_are_square_and_iconsized(qapp):
    """The default strip is icon-only, like Fusion's: no label, no extra height."""
    from freecad_timeline.view import ICON_SIZE_COMPACT, item_size

    metrics = QtGui.QFontMetrics(QtGui.QFont("Sans", 10))
    cell = item_size(metrics, ["A very long feature name"], False)

    assert cell.width() == cell.height()
    assert cell.width() < ICON_SIZE_COMPACT * 2
    # Labels do not influence it at all.
    assert cell == item_size(metrics, ["x"], False)


def test_compact_is_much_denser_than_labelled(qapp):
    from freecad_timeline.view import item_size

    metrics = QtGui.QFontMetrics(QtGui.QFont("Sans", 10))
    labels = ["Base plate", "Cable slot"]
    assert (
        item_size(metrics, labels, False).width() * 2
        < item_size(metrics, labels, True).width()
    )


def test_item_size_fits_the_widest_label(qapp):
    """averageCharWidth() under-measures real text; the width is taken from the
    labels themselves so names that fit are not truncated."""
    from freecad_timeline.view import item_size

    metrics = QtGui.QFontMetrics(QtGui.QFont("Sans", 10))
    narrow = item_size(metrics, ["Pad"], True)
    wide = item_size(metrics, ["Pad", "Counterbore"], True)

    assert wide.width() > narrow.width()
    assert wide.width() >= metrics.horizontalAdvance("Counterbore")


def test_item_size_clamps_a_runaway_label(qapp):
    """One absurd feature name must not stretch every item in the strip."""
    from freecad_timeline.view import LABEL_MAX_EM, item_size

    metrics = QtGui.QFontMetrics(QtGui.QFont("Sans", 10))
    huge = item_size(metrics, ["x" * 500], True)
    assert huge.width() <= metrics.horizontalAdvance("M") * LABEL_MAX_EM


def test_item_size_never_narrower_than_the_icon(qapp):
    from freecad_timeline.view import ICON_SIZE_LABELLED, item_size

    tiny = QtGui.QFontMetrics(QtGui.QFont("Sans", 1))
    assert item_size(tiny, (), True).width() >= ICON_SIZE_LABELLED
    assert item_size(tiny, (), True).height() >= ICON_SIZE_LABELLED


def test_all_rows_share_the_widest_width(qapp, body_with_four_pads):
    """uniformItemSizes is on, so a short label must not get a narrower box."""
    _doc, body, pads = body_with_four_pads
    pads[0].Label = "A"
    pads[1].Label = "A considerably longer name"

    widget = TimelineView()
    entries = model.build_timeline(body)
    widget.setEntries(entries, model.tip_slot(entries))

    widths = {widget.item(i).sizeHint().width() for i in range(widget.count())}
    assert len(widths) == 1


def test_rows_follow_the_widget_font(qapp, body_with_four_pads):
    _doc, body, _pads = body_with_four_pads
    entries = model.build_timeline(body)

    small = TimelineView()
    small.set_show_labels(True)
    small.setFont(QtGui.QFont("Sans", 8))
    small.setEntries(entries, model.tip_slot(entries))

    large = TimelineView()
    large.set_show_labels(True)
    large.setFont(QtGui.QFont("Sans", 20))
    large.setEntries(entries, model.tip_slot(entries))

    assert large.item(0).sizeHint().height() > small.item(0).sizeHint().height(), (
        "row height ignored the font"
    )


def test_marker_grab_radius_scales_with_the_font(qapp):
    from freecad_timeline.view import MARKER_GRAB_MIN

    small = TimelineView()
    small.setFont(QtGui.QFont("Sans", 8))
    large = TimelineView()
    large.setFont(QtGui.QFont("Sans", 24))

    assert large._grab_radius() > small._grab_radius()
    assert small._grab_radius() >= MARKER_GRAB_MIN


def test_near_marker_hit_test(view):
    x = view._marker_x()
    assert view._near_marker(x)
    assert view._near_marker(x + 5)
    assert not view._near_marker(x + 40)


# --------------------------------------------------------------------------
# painting
# --------------------------------------------------------------------------


def _render(widget):
    pixmap = QtGui.QPixmap(widget.size())
    pixmap.fill()
    widget.render(pixmap)
    return pixmap


def test_rendering_does_not_raise(view):
    assert not _render(view).isNull()


def test_rendering_with_suppressed_and_dimmed_entries(qapp, body_with_four_pads):
    _doc, body, pads = body_with_four_pads
    pads[0].Suppressed = True
    widget = TimelineView()
    widget.resize(600, 90)
    entries = model.build_timeline(body)
    widget.setEntries(entries, model.tip_slot(entries))
    widget.show()
    QtWidgets.QApplication.processEvents()

    assert entries[0].suppressed
    assert entries[3].after_tip
    assert not _render(widget).isNull()


def test_rendering_with_a_real_icon(qapp, body_with_four_pads):
    """The icon path differs from the placeholder path; exercise both."""
    _doc, body, pads = body_with_four_pads

    pixmap = QtGui.QPixmap(32, 32)
    pixmap.fill(QtGui.QColor("red"))
    icon = QtGui.QIcon(pixmap)

    class ViewObject:
        Icon = icon

    for pad in pads:
        pad.ViewObject = ViewObject()

    widget = TimelineView()
    widget.resize(600, 90)
    entries = model.build_timeline(body)
    widget.setEntries(entries, model.tip_slot(entries))
    assert widget._icon_for(entries[0]) is icon
    assert not _render(widget).isNull()


def test_rendering_an_empty_view_does_not_raise(qapp):
    widget = TimelineView()
    widget.resize(400, 90)
    widget.setEntries([], 0)
    assert not _render(widget).isNull()


def test_status_badges_paint(qapp, body_with_four_pads):
    _doc, body, pads = body_with_four_pads
    pads[0].State = ["Invalid"]
    pads[1].State = ["Touched"]
    # A failed feature that is also rolled back and suppressed — the badge is
    # drawn at full opacity even then.
    pads[3].State = ["Invalid"]
    pads[3].Suppressed = True

    widget = TimelineView()
    widget.resize(600, 90)
    entries = model.build_timeline(body)
    widget.setEntries(entries, model.tip_slot(entries))
    widget.show()
    QtWidgets.QApplication.processEvents()

    assert entries[0].failed
    assert entries[1].out_of_date
    assert entries[3].failed
    assert entries[3].suppressed
    assert entries[3].after_tip
    assert not _render(widget).isNull()


def test_error_badge_is_visible_in_the_rendered_pixels(qapp, body_with_four_pads):
    """The badge must actually change the output, not just avoid raising."""
    _doc, body, pads = body_with_four_pads

    widget = TimelineView()
    widget.resize(600, 90)
    entries = model.build_timeline(body)
    widget.setEntries(entries, model.tip_slot(entries))
    widget.show()
    QtWidgets.QApplication.processEvents()
    before = _render(widget).toImage()

    pads[0].State = ["Invalid"]
    entries = model.build_timeline(body)
    widget.setEntries(entries, model.tip_slot(entries))
    QtWidgets.QApplication.processEvents()
    after = _render(widget).toImage()

    assert before != after, "the error badge did not change any pixels"


def test_error_and_warning_colours_differ_and_adapt(qapp):
    from freecad_timeline import theme
    from freecad_timeline.qtcompat import Enums

    widget = QtWidgets.QWidget()
    light = theme.colors(widget)

    palette = QtGui.QPalette(widget.palette())
    palette.setColor(Enums.RoleWindow, QtGui.QColor(28, 28, 28))
    palette.setColor(Enums.RoleBase, QtGui.QColor(20, 20, 20))
    widget.setPalette(palette)
    dark = theme.colors(widget)

    assert light.error != light.warning
    assert dark.error.lightness() > light.error.lightness()
    assert dark.warning.lightness() > light.warning.lightness()


def test_drop_indicator_paints(view):
    view._drop_slot = 2
    assert not _render(view).isNull()


def test_marker_drag_state_paints(view):
    view._marker_drag = True
    view._marker_preview = 1
    assert not _render(view).isNull()
    assert view._marker_x() == view.slot_positions()[1]


# --------------------------------------------------------------------------
# theme
# --------------------------------------------------------------------------


def test_palette_derived_colors_follow_the_widget_palette(view):
    from freecad_timeline import theme

    light = theme.colors(view)

    palette = QtGui.QPalette(view.palette())
    from freecad_timeline.qtcompat import Enums

    palette.setColor(Enums.RoleWindow, QtGui.QColor(30, 30, 30))
    palette.setColor(Enums.RoleBase, QtGui.QColor(20, 20, 20))
    palette.setColor(Enums.RoleText, QtGui.QColor(230, 230, 230))
    view.setPalette(palette)

    dark = theme.colors(view)
    assert dark.dark is True
    assert dark.text != light.text
    assert not _render(view).isNull()


def test_dim_text_is_pulled_apart_when_theme_gives_no_contrast(qapp):
    from freecad_timeline import theme
    from freecad_timeline.qtcompat import Enums

    widget = QtWidgets.QWidget()
    palette = QtGui.QPalette(widget.palette())
    same = QtGui.QColor(200, 200, 200)
    palette.setColor(Enums.ColorActive, Enums.RoleText, same)
    palette.setColor(Enums.ColorDisabled, Enums.RoleText, same)
    palette.setColor(Enums.ColorActive, Enums.RoleBase, QtGui.QColor(0, 0, 0))
    widget.setPalette(palette)

    colors = theme.colors(widget)
    assert colors.dim_text != colors.text
    assert colors.dim_text.lightness() < colors.text.lightness()


# --------------------------------------------------------------------------
# signals
# --------------------------------------------------------------------------


def test_move_request_carries_source_and_slot(view):
    received = []
    view.moveRequested.connect(lambda sources, slot: received.append((sources, slot)))

    view._drag_rows = [0]
    view._drop_slot = 3

    class FakeDrop:
        def source(self):
            return view

        def setDropAction(self, action):
            self.action = action

        def accept(self):
            self.accepted = True

        def ignore(self):
            self.accepted = False

    view.dropEvent(FakeDrop())
    assert received == [([0], 3)]
    assert view._drop_slot is None


def test_drop_from_a_foreign_widget_is_ignored(view):
    received = []
    view.moveRequested.connect(lambda sources, slot: received.append((sources, slot)))

    other = QtWidgets.QWidget()
    view._drag_rows = [0]
    view._drop_slot = 2

    class ForeignDrop:
        def source(self):
            return other

        def setDropAction(self, action):
            pass

        def accept(self):
            pass

        def ignore(self):
            self.ignored = True

    view.dropEvent(ForeignDrop())
    assert received == []


def test_tip_slot_signal_on_marker_release(view):
    received = []
    view.tipSlotRequested.connect(received.append)

    view._marker_drag = True
    view._marker_preview = 1

    class FakeRelease:
        def button(self):
            from freecad_timeline.qtcompat import Enums

            return Enums.LeftButton

        def accept(self):
            pass

    view.mouseReleaseEvent(FakeRelease())
    assert received == [1]


def test_marker_release_on_the_same_slot_emits_nothing(view):
    received = []
    view.tipSlotRequested.connect(received.append)

    view._marker_drag = True
    view._marker_preview = view._tip_slot

    class FakeRelease:
        def button(self):
            from freecad_timeline.qtcompat import Enums

            return Enums.LeftButton

        def accept(self):
            pass

    view.mouseReleaseEvent(FakeRelease())
    assert received == []


def _release_event(point):
    """A real QMouseEvent — QListWidget's C++ handler needs one."""
    from freecad_timeline.qtcompat import Enums, QtCore

    return QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonRelease,
        QtCore.QPointF(point),
        Enums.LeftButton,
        Enums.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )


def test_click_on_a_feature_picks_it(view):
    received = []
    view.picked.connect(received.append)

    center = view.visualItemRect(view.item(1)).center()
    view.mouseReleaseEvent(_release_event(center))

    assert [entry.name for entry in received] == ["Pocket"]


def test_click_on_empty_space_does_not_pick(view):
    """Clicking past the last feature must not re-emit the current one."""
    view.select_names({"Pocket"})
    received = []
    view.picked.connect(received.append)

    from freecad_timeline.qtcompat import QtCore

    empty = QtCore.QPoint(
        view.viewport().rect().right() - 2, view.viewport().rect().bottom() - 2
    )
    assert view.itemAt(empty) is None
    view.mouseReleaseEvent(_release_event(empty))

    assert received == []


def test_refresh_does_not_invent_a_selection(view):
    """QListWidget makes row 0 current as soon as items exist. A refresh must
    not promote that into a real highlight."""
    assert not view.selectedItems()

    before = _render(view).toImage()
    view.setEntries(view.entries(), view._tip_slot)
    QtWidgets.QApplication.processEvents()

    assert not view.selectedItems()
    assert _render(view).toImage() == before, "an unselected refresh repainted"


# --------------------------------------------------------------------------
# multi-selection and keyboard
# --------------------------------------------------------------------------


def _select_rows(view, rows):
    view.clearSelection()
    for row in rows:
        view.item(row).setSelected(True)


def test_selected_entries_are_in_timeline_order(view):
    _select_rows(view, [3, 1])
    assert [e.name for e in view.selected_entries()] == ["Pocket", "Chamfer"]
    assert view.selected_rows() == [1, 3]


def test_multi_selection_survives_a_refresh(view):
    _select_rows(view, [0, 2])
    view.setEntries(view.entries(), view._tip_slot)
    assert [e.name for e in view.selected_entries()] == ["Pad", "Fillet"]


def test_select_names_mirrors_a_tree_multi_selection(view):
    matched = view.select_names({"Pad", "Chamfer"})
    assert matched == 2
    assert [e.name for e in view.selected_entries()] == ["Pad", "Chamfer"]


def test_select_names_moves_current_without_collapsing_the_selection(view):
    """setCurrentItem would reduce an ExtendedSelection to one row."""
    view.select_names({"Pocket", "Fillet"})
    assert len(view.selected_entries()) == 2
    assert view.current_entry().name == "Pocket"


def test_select_names_with_no_match_clears(view):
    _select_rows(view, [0])
    assert view.select_names({"Nope"}) == 0
    assert view.selected_entries() == []


def _set_current_only(view, row):
    """Move the cursor without disturbing the selection."""
    from freecad_timeline.qtcompat import Enums

    view.selectionModel().setCurrentIndex(
        view.indexFromItem(view.item(row)), Enums.SelectionNoUpdate
    )


def test_drag_takes_the_whole_selection_when_started_inside_it(view):
    _select_rows(view, [1, 2])
    _set_current_only(view, 2)
    view.startDrag(None)
    assert view._drag_rows == [1, 2]


def test_drag_outside_the_selection_moves_only_that_row(view):
    _select_rows(view, [1, 2])
    _set_current_only(view, 0)
    view.startDrag(None)
    assert view._drag_rows == [0]


def _key_event(key):
    from freecad_timeline.qtcompat import QtCore

    return QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyPress, key, QtCore.Qt.KeyboardModifier.NoModifier
    )


def test_delete_key_emits_the_selection(view):
    from freecad_timeline.qtcompat import QtCore

    received = []
    view.deleteRequested.connect(received.append)
    _select_rows(view, [0, 1])

    view.keyPressEvent(_key_event(QtCore.Qt.Key.Key_Delete))

    assert len(received) == 1
    assert [e.name for e in received[0]] == ["Pad", "Pocket"]


def test_delete_key_with_no_selection_does_nothing(view):
    from freecad_timeline.qtcompat import QtCore

    received = []
    view.deleteRequested.connect(received.append)
    view.clearSelection()

    view.keyPressEvent(_key_event(QtCore.Qt.Key.Key_Delete))
    assert received == []


def test_f2_emits_rename(view):
    from freecad_timeline.qtcompat import QtCore

    received = []
    view.renameRequested.connect(received.append)
    view.setCurrentRow(2)

    view.keyPressEvent(_key_event(QtCore.Qt.Key.Key_F2))
    assert [e.name for e in received] == ["Fillet"]


def test_return_emits_edit(view):
    from freecad_timeline.qtcompat import QtCore

    received = []
    view.editRequested.connect(received.append)
    view.setCurrentRow(1)

    view.keyPressEvent(_key_event(QtCore.Qt.Key.Key_Return))
    assert [e.name for e in received] == ["Pocket"]


def test_other_keys_fall_through(view):
    """Arrow navigation must still reach QListWidget."""
    from freecad_timeline.qtcompat import QtCore

    view.setCurrentRow(0)
    view.keyPressEvent(_key_event(QtCore.Qt.Key.Key_Right))
    assert view.currentRow() == 1


def test_selection_survives_a_refresh(view):
    view.select_names({"Pocket"})
    assert view.current_entry().name == "Pocket"

    # Same content, rebuilt — as a recompute-driven refresh would.
    view.setEntries(view.entries(), view._tip_slot)
    assert view.current_entry() is not None
    assert view.current_entry().name == "Pocket"


# --------------------------------------------------------------------------
# panel
# --------------------------------------------------------------------------


def test_panel_shows_placeholder_without_a_body(qapp):
    panel = TimelinePanel()
    panel.show_placeholder()
    assert panel._stack.currentWidget() is panel._placeholder
    assert panel._placeholder.text() == placeholder_no_body()


def test_panel_shows_empty_body_placeholder(qapp):
    panel = TimelinePanel()
    panel.show_entries("Body", [], 0)
    assert panel._stack.currentWidget() is panel._placeholder
    assert panel._placeholder.text() == placeholder_empty()


def test_panel_switches_to_the_strip(qapp, body_with_four_pads):
    _doc, body, _pads = body_with_four_pads
    panel = TimelinePanel()
    entries = model.build_timeline(body)
    panel.show_entries("Body", entries, model.tip_slot(entries))
    assert panel._stack.currentWidget() is panel.view
    assert panel.view.count() == 4


def test_body_name_goes_in_the_dock_title(qapp, body_with_four_pads):
    """Fusion has no header row on the strip, so the name belongs in the
    title bar."""
    from freecad_timeline.panel import TimelineDock

    _doc, body, _pads = body_with_four_pads
    dock = TimelineDock()
    entries = model.build_timeline(body)
    dock.panel.show_entries("Bracket", entries, model.tip_slot(entries))

    assert "Bracket" in dock.windowTitle()


def test_dock_title_escapes_the_body_name(qapp, body_with_four_pads):
    from freecad_timeline.panel import TimelineDock

    _doc, body, _pads = body_with_four_pads
    dock = TimelineDock()
    entries = model.build_timeline(body)
    dock.panel.show_entries("A & B <script>", entries, 0)

    assert "&amp;" in dock.windowTitle()
    assert "<script>" not in dock.windowTitle()


def test_non_solid_toggle_emits(qapp):
    panel = TimelinePanel()
    received = []
    panel.showNonSolidChanged.connect(received.append)
    panel.set_show_non_solid(True)
    assert received == [True]
    assert panel.show_non_solid() is True
