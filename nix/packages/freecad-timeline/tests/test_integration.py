# SPDX-License-Identifier: LGPL-2.1-or-later
"""Controller tests with a stand-in FreeCAD.

``integration`` imports ``FreeCAD``/``FreeCADGui`` lazily inside ``_app()`` and
``_gui()``, so injecting fake modules into ``sys.modules`` exercises the real
controller code: active-body resolution, debounced refresh, placeholder
handling, and two-way selection sync.
"""

from __future__ import annotations

import sys

import pytest

pytest.importorskip("freecad_timeline.qtcompat", reason="no Qt binding available")

import types

from freecad_timeline import integration
from freecad_timeline.qtcompat import Enums, QtWidgets
from freecad_timeline.view import ENTRY_ROLE

from .fakes import FakeBody, FakeDocument, FakeFeature, FakeObject

# --------------------------------------------------------------------------
# fake FreeCAD
# --------------------------------------------------------------------------


class FakeSelection:
    def __init__(self, document=None):
        self.document = document
        self._selected = []
        self.observers = []

    def getSelection(self, *args):
        return list(self._selected)

    def clearSelection(self, *args):
        self._selected = []

    def addSelection(self, doc_name, obj_name, *args):
        obj = self.document.getObject(obj_name) if self.document else None
        if obj is not None:
            self._selected.append(obj)

    def addObserver(self, observer):
        self.observers.append(observer)

    def removeObserver(self, observer):
        if observer in self.observers:
            self.observers.remove(observer)


class FakeActiveView:
    def __init__(self, body=None):
        self.body = body

    def getActiveObject(self, key):
        return self.body if key == integration.PDBODY_KEY else None


class FakeGuiDocument:
    def __init__(self):
        self.edited = []

    def setEdit(self, obj, *args):
        self.edited.append(obj)
        return True


class FakeParameterGroup:
    def __init__(self):
        self.store = {}

    def GetBool(self, name, default=False):
        return self.store.get(name, default)

    def SetBool(self, name, value):
        self.store[name] = bool(value)


@pytest.fixture
def freecad(qapp, monkeypatch):
    """Install fake FreeCAD / FreeCADGui modules for the duration of a test."""
    document = FakeDocument()
    body = FakeBody(document=document)
    document.add(body)

    parts = {}
    sketch = FakeObject("Sketch", "Sketcher::SketchObject", document=document)
    document.add(sketch)
    body.addObject(sketch)
    parts["sketch"] = sketch

    for name in ("Pad", "Fillet"):
        feature = FakeFeature(name, document=document)
        document.add(feature)
        body.addObject(feature)
        parts[name.lower()] = feature

    main_window = QtWidgets.QMainWindow()
    main_window.resize(900, 500)
    # Actually show it: QWidget.isVisible() is False whenever an ancestor is
    # hidden, and a dock's toggleViewAction only tracks real visibility, so a
    # never-shown window would make every visibility assertion vacuous.
    main_window.show()
    QtWidgets.QApplication.processEvents()

    gui_document = FakeGuiDocument()
    selection = FakeSelection(document)

    parameters = FakeParameterGroup()

    app_module = types.ModuleType("FreeCAD")
    app_module.ParamGet = lambda _path: parameters
    app_module.parameters = parameters
    app_module.observers = []
    app_module.addDocumentObserver = app_module.observers.append
    app_module.removeDocumentObserver = lambda o: app_module.observers.remove(o)
    app_module.Console = types.SimpleNamespace(
        PrintWarning=lambda *a: None, PrintError=lambda *a: None
    )

    gui_module = types.ModuleType("FreeCADGui")
    gui_module.ActiveDocument = types.SimpleNamespace(ActiveView=FakeActiveView(body))
    gui_module.Selection = selection
    gui_module.getMainWindow = lambda: main_window
    gui_module.getDocument = lambda name: gui_document

    monkeypatch.setitem(sys.modules, "FreeCAD", app_module)
    monkeypatch.setitem(sys.modules, "FreeCADGui", gui_module)

    yield types.SimpleNamespace(
        app=app_module,
        gui=gui_module,
        document=document,
        body=body,
        parts=parts,
        selection=selection,
        gui_document=gui_document,
        main_window=main_window,
    )

    main_window.close()


@pytest.fixture
def controller(freecad):
    instance = integration.TimelineController()
    yield instance
    instance.uninstall()
    instance.dock.setParent(None)
    instance.dock.deleteLater()


# --------------------------------------------------------------------------
# active body resolution
# --------------------------------------------------------------------------


def test_active_body_from_pdbody(freecad):
    assert integration.active_body() is freecad.body


def test_active_body_falls_back_to_selection(freecad):
    freecad.gui.ActiveDocument.ActiveView.body = None
    freecad.selection.addSelection(freecad.document.Name, "Pad")

    # The Pad's body is found by scanning, since the fake has no
    # getParentGeoFeatureGroup.
    assert integration.active_body() is freecad.body


def test_no_active_body_and_no_selection(freecad):
    freecad.gui.ActiveDocument.ActiveView.body = None
    assert integration.active_body() is None


def test_no_active_document(freecad):
    freecad.gui.ActiveDocument = None
    assert integration.active_body() is None


def test_is_alive_detects_a_dead_proxy():
    class Dead:
        @property
        def Name(self):
            raise ReferenceError("object has been deleted")

    assert integration.is_alive(Dead()) is False
    assert integration.is_alive(None) is False
    assert integration.is_alive(FakeFeature("Pad")) is True


def test_body_of_returns_the_body_itself(freecad):
    assert integration.body_of(freecad.body) is freecad.body


# --------------------------------------------------------------------------
# refresh
# --------------------------------------------------------------------------


def test_refresh_populates_the_strip(controller, freecad):
    controller.refresh()
    assert controller.view.count() == 2
    assert [e.name for e in controller.view.entries()] == ["Pad", "Fillet"]
    assert controller.panel._stack.currentWidget() is controller.view


def test_refresh_shows_placeholder_without_a_body(controller, freecad):
    freecad.gui.ActiveDocument.ActiveView.body = None
    controller.refresh()
    assert controller.panel._stack.currentWidget() is controller.panel._placeholder


def test_refresh_survives_a_closed_document(controller, freecad):
    """The dock stays open when the document goes away."""
    controller.refresh()
    assert controller.view.count() == 2

    class DeadBody:
        @property
        def Name(self):
            raise ReferenceError("deleted")

    freecad.gui.ActiveDocument.ActiveView.body = DeadBody()
    controller.refresh()
    assert controller.panel._stack.currentWidget() is controller.panel._placeholder


def test_refresh_honours_the_non_solid_toggle(controller, freecad):
    controller.panel.set_show_non_solid(True)
    controller.refresh()
    assert [e.name for e in controller.view.entries()] == ["Sketch", "Pad", "Fillet"]


def test_refresh_is_debounced(controller, freecad):
    """Many change notifications collapse into a single pending refresh."""
    for _ in range(50):
        controller.request_refresh()
    assert controller._timer.isActive()
    assert controller.view.count() == 0, "nothing painted before the timer fires"

    controller.refresh()
    assert not controller._timer.isActive()
    assert controller.view.count() == 2


def test_multiple_documents_follow_the_active_one(controller, freecad):
    other_document = FakeDocument("Other")
    other_body = FakeBody("Body", document=other_document, label="Other body")
    other_document.add(other_body)
    other_pad = FakeFeature("OtherPad", document=other_document)
    other_document.add(other_pad)
    other_body.addObject(other_pad)

    controller.refresh()
    assert [e.name for e in controller.view.entries()] == ["Pad", "Fillet"]

    freecad.gui.ActiveDocument.ActiveView.body = other_body
    controller.refresh()
    assert [e.name for e in controller.view.entries()] == ["OtherPad"]


# --------------------------------------------------------------------------
# selection sync
# --------------------------------------------------------------------------


def test_document_selection_highlights_the_timeline(controller, freecad):
    freecad.selection.addSelection(freecad.document.Name, "Fillet")
    controller.refresh()
    assert controller.view.current_entry().name == "Fillet"


def test_timeline_click_selects_in_the_document(controller, freecad):
    controller.refresh()
    entry = controller.view.entries()[0]
    controller._on_picked(entry)

    assert [obj.Name for obj in freecad.selection.getSelection()] == ["Pad"]


def test_selection_sync_does_not_loop(controller, freecad, monkeypatch):
    """Picking sets the document selection; FreeCAD dispatches selection
    observers synchronously from inside that call, and the re-entrant
    notification must not schedule another refresh."""
    controller.refresh()
    entry = controller.view.entries()[1]

    real_add = freecad.selection.addSelection

    def add_and_notify(*args, **kwargs):
        result = real_add(*args, **kwargs)
        controller._on_selection_changed()  # what Gui.Selection does
        return result

    monkeypatch.setattr(freecad.selection, "addSelection", add_and_notify)
    controller._timer.stop()

    controller._on_picked(entry)

    assert freecad.selection.getSelection()[0].Name == "Fillet"
    assert not controller._timer.isActive(), "re-entrant notification was not guarded"


def test_clearing_the_document_selection_clears_the_strip(controller, freecad):
    freecad.selection.addSelection(freecad.document.Name, "Pad")
    controller.refresh()
    assert controller.view.current_entry() is not None

    freecad.selection.clearSelection()
    controller.refresh()
    assert controller.view.current_entry() is None


def test_double_click_opens_the_editor(controller, freecad):
    controller.refresh()
    entry = controller.view.entries()[0]
    controller._on_edit(entry)
    assert freecad.gui_document.edited == [entry.obj]


# --------------------------------------------------------------------------
# mutations through the controller
# --------------------------------------------------------------------------


def test_marker_drop_sets_the_tip(controller, freecad):
    controller.refresh()
    controller._on_tip_slot(1)
    assert freecad.body.Tip is freecad.parts["pad"]
    assert freecad.document.committed == ["Move tip to selected feature"]


def test_marker_drop_at_slot_zero_clears_the_tip(controller, freecad):
    controller.refresh()
    controller._on_tip_slot(0)
    assert freecad.body.Tip is None


def test_marker_drop_onto_a_sketch_is_refused(controller, freecad, monkeypatch):
    warnings = []
    monkeypatch.setattr(controller, "_warn", lambda title, msg: warnings.append(title))

    controller.panel.set_show_non_solid(True)
    controller.refresh()
    # Slot 1 is now the sketch, which cannot be a tip.
    controller._on_tip_slot(1)

    assert warnings == ["Cannot set tip"]
    assert freecad.document.transactions == []


def test_drag_reorder_through_the_controller(controller, freecad):
    controller.refresh()
    controller._on_move(1, 0)  # drag Fillet to the front

    assert freecad.body.Group == [
        freecad.parts["fillet"],
        freecad.parts["sketch"],
        freecad.parts["pad"],
    ]


def test_reorder_failure_is_reported_and_refreshed(controller, freecad, monkeypatch):
    warnings = []
    monkeypatch.setattr(controller, "_warn", lambda title, msg: warnings.append(title))

    # Fillet's profile depends on Pad, so moving Pad after Fillet is illegal.
    freecad.parts["fillet"].OutList = [freecad.parts["sketch"]]
    freecad.parts["sketch"].OutList = [freecad.parts["pad"]]

    controller.refresh()
    controller._on_move(1, 0)

    assert warnings == ["Dependency violation"]
    assert freecad.document.aborted == ["Move a feature inside body"]


def test_install_adds_the_dock_and_observers(controller, freecad):
    controller.install()

    assert controller.dock.parent() is freecad.main_window
    assert len(freecad.app.observers) == 1
    assert len(freecad.selection.observers) == 1

    controller.uninstall()
    assert freecad.app.observers == []
    assert freecad.selection.observers == []


def test_install_is_idempotent(controller, freecad):
    controller.install()
    controller.install()
    assert len(freecad.app.observers) == 1


def test_uninstall_without_install_is_safe(controller, freecad):
    controller.uninstall()


# --------------------------------------------------------------------------
# multi-selection
# --------------------------------------------------------------------------


def _select(view, names):
    view.clearSelection()
    for row in range(view.count()):
        entry = view.item(row).data(ENTRY_ROLE)
        if entry is not None and entry.name in names:
            view.item(row).setSelected(True)


def test_timeline_multi_selection_pushes_all_to_the_document(controller, freecad):
    controller.refresh()
    _select(controller.view, {"Pad", "Fillet"})

    controller._on_picked(controller.view.selected_entries()[0])

    assert sorted(o.Name for o in freecad.selection.getSelection()) == ["Fillet", "Pad"]


def test_document_multi_selection_highlights_the_timeline(controller, freecad):
    freecad.selection.addSelection(freecad.document.Name, "Pad")
    freecad.selection.addSelection(freecad.document.Name, "Fillet")
    controller.refresh()

    assert sorted(e.name for e in controller.view.selected_entries()) == [
        "Fillet",
        "Pad",
    ]


def test_delete_several_features_in_one_transaction(controller, freecad, monkeypatch):
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "question", staticmethod(lambda *a, **k: Enums.ButtonYes)
    )
    controller.refresh()
    entries = controller.view.entries()

    controller._delete(entries)

    assert freecad.document.getObject("Pad") is None
    assert freecad.document.getObject("Fillet") is None
    assert freecad.document.committed == ["Delete feature"]


def test_delete_ignores_the_base_feature(controller, freecad, monkeypatch):
    from .fakes import FakeObject

    base = FakeObject("Box", "Part::Box", document=freecad.document)
    freecad.document.add(base)
    freecad.body.BaseFeature = base
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "question", staticmethod(lambda *a, **k: Enums.ButtonYes)
    )
    controller.panel.set_show_non_solid(True)
    controller.refresh()

    controller._delete(controller.view.entries())

    assert freecad.document.getObject("Box") is not None


def test_delete_cancelled_changes_nothing(controller, freecad, monkeypatch):
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "question", staticmethod(lambda *a, **k: Enums.ButtonNo)
    )
    controller.refresh()

    controller._delete([controller.view.entries()[1]])

    assert freecad.document.getObject("Fillet") is not None
    assert freecad.document.transactions == []


def test_drag_reorders_a_multi_selection(controller, freecad):
    # Show the sketch so the strip has three slots to move between; with only
    # the two solids visible they already occupy slots 0-1 and the drag would
    # correctly be a no-op.
    controller.panel.set_show_non_solid(True)
    controller.refresh()
    assert [e.name for e in controller.view.entries()] == ["Sketch", "Pad", "Fillet"]

    controller._on_move([1, 2], 0)  # drag Pad+Fillet ahead of the sketch

    assert freecad.body.Group == [
        freecad.parts["pad"],
        freecad.parts["fillet"],
        freecad.parts["sketch"],
    ]


def test_on_move_still_accepts_a_bare_row(controller, freecad):
    """The signal now carries a list; a plain int must not break."""
    controller.refresh()
    controller._on_move(1, 0)
    assert freecad.body.Group[0] is freecad.parts["fillet"]


# --------------------------------------------------------------------------
# keyboard
# --------------------------------------------------------------------------


def test_delete_key_reaches_the_controller(controller, freecad, monkeypatch):
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "question", staticmethod(lambda *a, **k: Enums.ButtonYes)
    )
    controller.refresh()
    _select(controller.view, {"Fillet"})

    controller.view.deleteRequested.emit(controller.view.selected_entries())

    assert freecad.document.getObject("Fillet") is None


def test_rename_signal_reaches_the_controller(controller, freecad, monkeypatch):
    monkeypatch.setattr(
        QtWidgets.QInputDialog,
        "getText",
        staticmethod(lambda *a, **k: ("Base plate", True)),
    )
    controller.refresh()
    entry = controller.view.entries()[0]

    controller.view.renameRequested.emit(entry)

    assert freecad.parts["pad"].Label == "Base plate"


# --------------------------------------------------------------------------
# persisted state
# --------------------------------------------------------------------------


def test_closing_the_dock_is_remembered(controller, freecad):
    from freecad_timeline import settings

    controller.install()
    assert freecad.app.parameters.store[settings.VISIBLE] is True

    controller.dock.toggleViewAction().trigger()  # user closes it
    assert freecad.app.parameters.store[settings.VISIBLE] is False

    controller.dock.toggleViewAction().trigger()  # and reopens it
    assert freecad.app.parameters.store[settings.VISIBLE] is True


def test_startup_honours_a_dock_the_user_closed(controller, freecad):
    from freecad_timeline import settings

    freecad.app.parameters.store[settings.VISIBLE] = False
    controller.install(honour_saved_visibility=True)

    assert not controller.dock.isVisible()
    # Still added, so View -> Panels can bring it back.
    assert controller.dock.parent() is freecad.main_window


def test_explicit_command_shows_the_dock_regardless(controller, freecad):
    from freecad_timeline import settings

    freecad.app.parameters.store[settings.VISIBLE] = False
    controller.install(honour_saved_visibility=False)

    assert controller.dock.isVisible()


def test_restoring_a_hidden_dock_leaves_the_preference_alone(controller, freecad):
    from freecad_timeline import settings

    freecad.app.parameters.store[settings.VISIBLE] = False
    controller.install(honour_saved_visibility=True)

    assert freecad.app.parameters.store[settings.VISIBLE] is False


def test_opening_via_the_command_makes_it_stick(controller, freecad):
    """Running Timeline_Show on a dock the user had closed means "keep it
    open", so the preference must flip — not stay hidden next launch."""
    from freecad_timeline import settings

    freecad.app.parameters.store[settings.VISIBLE] = False
    controller.install(honour_saved_visibility=False)

    assert controller.dock.isVisible()
    assert freecad.app.parameters.store[settings.VISIBLE] is True


def test_non_solid_toggle_is_remembered(controller, freecad):
    from freecad_timeline import settings

    controller.install()
    controller.panel.set_show_non_solid(True)

    assert freecad.app.parameters.store[settings.SHOW_NON_SOLID] is True


def test_non_solid_toggle_is_restored_on_startup(controller, freecad):
    from freecad_timeline import settings

    freecad.app.parameters.store[settings.SHOW_NON_SOLID] = True
    controller.install(honour_saved_visibility=True)

    assert controller.panel.show_non_solid() is True
    assert [e.name for e in controller.view.entries()] == ["Sketch", "Pad", "Fillet"]


def test_install_asks_qt_to_restore_the_saved_dock_layout(controller, freecad):
    """We are added after MainWindow::restoreState, so Qt needs an explicit
    restoreDockWidget to replay the stored area and size."""
    restored = []
    original = freecad.main_window.restoreDockWidget
    freecad.main_window.restoreDockWidget = lambda dock: (
        restored.append(dock),
        original(dock),
    )[1]

    controller.install()
    assert restored == [controller.dock]


def test_document_observer_triggers_a_refresh(controller, freecad):
    controller.install()
    observer = freecad.app.observers[0]

    controller._timer.stop()
    observer.slotChangedObject(freecad.parts["pad"], "Suppressed")
    assert controller._timer.isActive()


def test_document_observer_ignores_irrelevant_properties(controller, freecad):
    controller.install()
    observer = freecad.app.observers[0]

    controller._timer.stop()
    observer.slotChangedObject(freecad.parts["pad"], "Length")
    assert not controller._timer.isActive()


# --------------------------------------------------------------------------
# transport controls
# --------------------------------------------------------------------------


def test_transport_steps_the_tip(controller, freecad):
    controller.refresh()
    freecad.body.Tip = freecad.parts["fillet"]
    controller.refresh()

    controller.panel.tipStepRequested.emit(-1)  # step back
    assert freecad.body.Tip is freecad.parts["pad"]

    controller.panel.tipStepRequested.emit(+1)  # and forward again
    assert freecad.body.Tip is freecad.parts["fillet"]


def test_transport_jumps_to_the_ends(controller, freecad):
    controller.refresh()

    controller.panel.tipStepRequested.emit(-2)
    assert freecad.body.Tip is None

    controller.panel.tipStepRequested.emit(2)
    assert freecad.body.Tip is freecad.parts["fillet"]


def test_transport_never_lands_on_a_sketch(controller, freecad):
    controller.panel.set_show_non_solid(True)
    controller.refresh()
    controller.panel.tipStepRequested.emit(-2)

    controller.panel.tipStepRequested.emit(+1)
    assert freecad.body.Tip is freecad.parts["pad"]


def test_transport_greys_out_at_the_ends(controller, freecad):
    controller.refresh()
    freecad.body.Tip = freecad.parts["fillet"]
    controller.refresh()
    assert not controller.panel._transport[2].isEnabled(), "already at the end"
    assert controller.panel._transport[-1].isEnabled()

    controller.panel.tipStepRequested.emit(-2)
    assert not controller.panel._transport[-1].isEnabled(), "already at the start"
    assert controller.panel._transport[1].isEnabled()


def test_transport_disabled_without_a_body(controller, freecad):
    freecad.gui.ActiveDocument.ActiveView.body = None
    controller.refresh()
    assert not controller.panel._transport[1].isEnabled()


def test_label_mode_is_remembered(controller, freecad):
    from freecad_timeline import settings

    controller.install()
    assert controller.view.show_labels() is False, "compact by default, like Fusion"

    controller.panel.set_show_labels(True)
    assert freecad.app.parameters.store[settings.SHOW_LABELS] is True
    assert controller.view.show_labels() is True


def test_label_mode_is_restored_on_startup(controller, freecad):
    from freecad_timeline import settings

    freecad.app.parameters.store[settings.SHOW_LABELS] = True
    controller.install(honour_saved_visibility=True)
    assert controller.view.show_labels() is True
