# SPDX-License-Identifier: LGPL-2.1-or-later
"""FreeCAD wiring: active-body tracking, observers, and the dock's lifecycle.

This is the only module that imports ``FreeCAD``/``FreeCADGui`` at call time.
It translates view signals into :mod:`freecad_timeline.commands` calls and
document/selection events into debounced refreshes.
"""

from __future__ import annotations

import contextlib
from typing import Any

from . import commands, model, settings
from .observers import TimelineDocumentObserver, TimelineSelectionObserver
from .panel import OBJECT_NAME, TimelineDock
from .qtcompat import Enums, QtCore, QtWidgets, exec_widget, translate

__all__ = ["TimelineController", "controller", "show_timeline"]

#: Key ``PartDesignGui`` stores the active body under
#: (``PDBODYKEY`` in ``src/Gui/ActiveObjectList.h``).
PDBODY_KEY = "pdbody"

#: Coalescing window, in ms.  A recompute emits a burst of change signals; we
#: want one repaint at the end of it, not one per feature.
REFRESH_DELAY_MS = 60


def _app():
    import FreeCAD

    return FreeCAD


def _gui():
    import FreeCADGui

    return FreeCADGui


def is_alive(obj: Any) -> bool:
    """Whether a document object proxy still points at a live C++ object.

    Touching a deleted object raises ``ReferenceError``; this happens routinely
    when a document is closed while the dock is open.
    """
    if obj is None:
        return False
    try:
        obj.Name  # noqa: B018 — the point is the raise, not the value
        return True
    except Exception:
        return False


def body_of(obj: Any) -> Any | None:
    """The PartDesign body containing ``obj``, or ``None``."""
    if not is_alive(obj):
        return None
    if obj.isDerivedFrom("PartDesign::Body"):
        return obj
    try:
        parent = obj.getParentGeoFeatureGroup()
    except Exception:
        parent = None
    if parent is not None and parent.isDerivedFrom("PartDesign::Body"):
        return parent

    # Fall back to a scan: getParentGeoFeatureGroup misses objects that are
    # linked into a body without being grouped by it.
    try:
        document = obj.Document
        for candidate in document.findObjects("PartDesign::Body"):
            if obj in candidate.Group:
                return candidate
    except Exception:
        pass
    return None


def active_body() -> Any | None:
    """The body the timeline should display.

    Primary source is the active view's ``pdbody`` active object, which is what
    PartDesign itself uses.  When nothing is active we fall back to the body
    owning the current selection, so clicking a feature in the tree of a
    non-active body still populates the strip.
    """
    gui = _gui()

    document = getattr(gui, "ActiveDocument", None)
    if document is not None:
        view = getattr(document, "ActiveView", None)
        if view is not None:
            try:
                body = view.getActiveObject(PDBODY_KEY)
            except Exception:
                body = None
            if is_alive(body):
                return body

    try:
        selection = gui.Selection.getSelection()
    except Exception:
        selection = []
    for obj in selection:
        body = body_of(obj)
        if body is not None:
            return body
    return None


class TimelineController(QtCore.QObject):
    """Owns the dock, the observers and the refresh cycle."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.dock = TimelineDock()
        self.panel = self.dock.panel
        self.view = self.dock.view

        self._body: Any | None = None
        self._entries: list[model.TimelineEntry] = []
        self._syncing = False
        self._installed = False

        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(REFRESH_DELAY_MS)
        self._timer.timeout.connect(self.refresh)

        self._document_observer = TimelineDocumentObserver(self.request_refresh)
        self._selection_observer = TimelineSelectionObserver(self._on_selection_changed)

        self.panel.showNonSolidChanged.connect(self._on_show_non_solid_changed)
        self.panel.showLabelsChanged.connect(self._on_show_labels_changed)
        self.panel.tipStepRequested.connect(self._on_tip_step)
        self.dock.toggleViewAction().toggled.connect(self._on_dock_visibility_changed)
        self.view.picked.connect(self._on_picked)
        self.view.editRequested.connect(self._on_edit)
        self.view.tipSlotRequested.connect(self._on_tip_slot)
        self.view.moveRequested.connect(self._on_move)
        self.view.menuRequested.connect(self._on_menu)
        self.view.deleteRequested.connect(self._delete)
        self.view.renameRequested.connect(self._rename)

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def install(self, honour_saved_visibility: bool = False) -> None:
        """Add the dock to the main window and start observing.

        ``honour_saved_visibility`` is used by the startup path: if the user
        closed the dock in a previous session it stays hidden, but is still
        added so its **View → Panels** entry exists.  An explicit invocation of
        the command passes ``False`` and always reveals it.
        """
        if self._installed:
            self.dock.show()
            self.dock.raise_()
            return

        main_window = _gui().getMainWindow()
        existing = main_window.findChild(QtWidgets.QDockWidget, OBJECT_NAME)
        if existing is not None and existing is not self.dock:
            # A stale dock from a previous load of the addon.
            existing.setParent(None)
            existing.deleteLater()

        main_window.addDockWidget(Enums.BottomDockWidgetArea, self.dock)
        # We are added after MainWindow::restoreState() has already run, so Qt
        # has not placed us. restoreDockWidget replays the saved area, size and
        # tabbing for a dock created late; it returns False when there is no
        # stored state, leaving the default bottom placement.
        with contextlib.suppress(Exception):
            main_window.restoreDockWidget(self.dock)

        self.panel.set_show_non_solid(settings.get_bool(settings.SHOW_NON_SOLID, False))
        self.panel.set_show_labels(settings.get_bool(settings.SHOW_LABELS, False))

        visible = (
            settings.get_bool(settings.VISIBLE, True)
            if honour_saved_visibility
            else True
        )
        self.dock.setVisible(visible)
        if visible:
            self.dock.raise_()

        _app().addDocumentObserver(self._document_observer)
        _gui().Selection.addObserver(self._selection_observer)
        self._installed = True
        self.refresh()

    def uninstall(self) -> None:
        """Detach observers and remove the dock.  Safe to call twice."""
        if not self._installed:
            return
        with contextlib.suppress(Exception):
            _app().removeDocumentObserver(self._document_observer)
        with contextlib.suppress(Exception):
            _gui().Selection.removeObserver(self._selection_observer)
        with contextlib.suppress(Exception):
            _gui().getMainWindow().removeDockWidget(self.dock)
        self._installed = False

    # ------------------------------------------------------------------
    # persisted state
    # ------------------------------------------------------------------

    def _on_dock_visibility_changed(self, visible: bool) -> None:
        """Remember whether the dock was on screen.

        Without this the dock reappears on every start, because FreeCAD only
        persists visibility for docks registered with its own
        ``DockWindowManager``.

        Every transition is recorded, including the one ``install()`` causes:
        restoring the stored value writes back what we just read, which is a
        no-op, while an explicit ``Timeline_Show`` genuinely means "keep this
        open from now on" and must not be suppressed.
        """
        settings.set_bool(settings.VISIBLE, bool(visible))

    def _on_show_non_solid_changed(self, checked: bool) -> None:
        settings.set_bool(settings.SHOW_NON_SOLID, bool(checked))
        self.refresh()

    def _on_show_labels_changed(self, checked: bool) -> None:
        settings.set_bool(settings.SHOW_LABELS, bool(checked))

    def _on_tip_step(self, step: int) -> None:
        """Transport buttons: -2 start, -1 back, +1 forward, +2 end."""
        if self._body is None or not self._entries:
            return
        current = model.tip_slot(self._entries)
        if step == -2:
            target = 0
        elif step == 2:
            target = model.last_tip_slot(self._entries)
        else:
            target = model.step_tip_slot(self._entries, current, step)
        if target is None or target == current:
            return
        self._on_tip_slot(target)

    # ------------------------------------------------------------------
    # refresh
    # ------------------------------------------------------------------

    def request_refresh(self) -> None:
        """Schedule a refresh, coalescing bursts of document changes.

        ``QTimer.start()`` on a single-shot timer restarts it, so a hundred
        change notifications during a recompute collapse into one repaint.
        """
        self._timer.start()

    def refresh(self) -> None:
        """Rebuild the strip from the document.

        Everything is re-read: cached ``TimelineEntry`` objects hold references
        to document objects that may have been deleted since the last pass.
        """
        self._timer.stop()

        body = active_body()
        if not is_alive(body):
            self._body = None
            self._entries = []
            self.panel.show_placeholder()
            return

        self._body = body
        try:
            entries = model.build_timeline(
                body, show_non_solid=self.panel.show_non_solid()
            )
            tip_slot = model.tip_slot(entries)
        except Exception:
            # The document changed underneath us; try again on the next event.
            self._entries = []
            self.panel.show_placeholder()
            return

        self._entries = entries
        self.panel.show_entries(str(getattr(body, "Label", "Body")), entries, tip_slot)
        self.panel.set_transport_enabled(
            model.step_tip_slot(entries, tip_slot, -1) is not None,
            model.step_tip_slot(entries, tip_slot, +1) is not None,
        )
        self._sync_selection_into_view()

    # ------------------------------------------------------------------
    # selection sync (both directions)
    # ------------------------------------------------------------------

    def _on_selection_changed(self) -> None:
        if self._syncing:
            return
        # An active-body change arrives as a selection change too, so a full
        # refresh (debounced) is the right response, not just a highlight.
        self.request_refresh()

    def _sync_selection_into_view(self) -> None:
        """Highlight whatever the tree/3D view has selected."""
        if self._syncing:
            return
        try:
            selection = _gui().Selection.getSelection()
        except Exception:
            selection = []

        names = {obj.Name for obj in selection if is_alive(obj)}
        self._syncing = True
        try:
            if names and self.view.select_names(names, emit=False):
                return
            self.view.clear_selection()
        finally:
            self._syncing = False

    def _on_picked(self, entry) -> None:
        """Timeline click -> document selection.

        Pushes the whole timeline selection, so a Ctrl/Shift range picked here
        shows up as the same multi-selection in the tree and 3D view.
        """
        if self._syncing or self._body is None:
            return
        document = getattr(self._body, "Document", None)
        if document is None:
            return

        entries = self.view.selected_entries() or [entry]
        self._syncing = True
        try:
            gui = _gui()
            gui.Selection.clearSelection()
            for selected in entries:
                gui.Selection.addSelection(document.Name, selected.name)
        except Exception:
            pass
        finally:
            self._syncing = False

    def _on_edit(self, entry) -> None:
        """Double click -> open the feature's task dialog."""
        try:
            gui = _gui()
            document = gui.getDocument(self._body.Document.Name)
            document.setEdit(entry.obj)
        except Exception as error:
            self._warn(translate("Cannot edit %s") % entry.label, str(error))

    # ------------------------------------------------------------------
    # mutations
    # ------------------------------------------------------------------

    def _run(self, description: str, function, *args, **kwargs) -> bool:
        """Execute a mutation, reporting failures instead of raising into Qt."""
        try:
            function(*args, **kwargs)
        except commands.DependencyViolation as error:
            self._warn(translate("Dependency violation"), error.describe())
            self.refresh()
            return False
        except Exception as error:
            self._warn(description, str(error))
            self.refresh()
            return False
        self.refresh()
        return True

    def _on_tip_slot(self, slot: int) -> None:
        if self._body is None:
            return
        entry = model.entry_at_slot(self._entries, slot)
        target = entry.obj if entry is not None else None
        if entry is not None and not entry.tip_allowed:
            self._warn(
                translate("Cannot set tip"),
                translate("Only a solid feature can be the tip of a body (%s).")
                % entry.label,
            )
            self.refresh()
            return
        self._run(
            translate("Cannot move the tip"), commands.set_tip, self._body, target
        )

    def _on_move(self, source_rows, slot: int) -> None:
        if self._body is None:
            return
        rows = (
            list(source_rows)
            if isinstance(source_rows, (list, tuple))
            else [source_rows]
        )
        self._run(
            translate("Cannot move the feature"),
            commands.move_selection_to_slot,
            self._body,
            self._entries,
            rows,
            slot,
        )

    # ------------------------------------------------------------------
    # context menu
    # ------------------------------------------------------------------

    def _on_menu(self, entry, global_position) -> None:
        if self._body is None:
            return

        menu = QtWidgets.QMenu(self.view)

        # Act on the whole selection when the clicked feature is part of it.
        selection = self.view.selected_entries()
        if entry is not None and entry not in selection:
            selection = [entry]
        several = len(selection) > 1

        if entry is not None:
            # A tip is a single position, so this always targets the clicked
            # feature even with several selected.
            set_tip = menu.addAction(translate("Set tip here"))
            set_tip.setEnabled(entry.tip_allowed and not entry.is_tip)
            set_tip.triggered.connect(
                lambda _checked=False, e=entry: self._run(
                    translate("Cannot move the tip"),
                    commands.set_tip,
                    self._body,
                    e.obj,
                )
            )

            suppressible = [e.obj for e in selection if hasattr(e.obj, "Suppressed")]
            unsuppress = bool(suppressible) and all(
                bool(getattr(obj, "Suppressed", False)) for obj in suppressible
            )
            if several:
                text = (
                    translate("Unsuppress %n feature(s)", None, len(suppressible))
                    if unsuppress
                    else translate("Suppress %n feature(s)", None, len(suppressible))
                )
            else:
                text = translate("Unsuppress") if unsuppress else translate("Suppress")
            suppress = menu.addAction(text)
            suppress.setEnabled(bool(suppressible))
            suppress.triggered.connect(
                lambda _checked=False, objs=suppressible: self._run(
                    translate("Cannot change suppression"),
                    commands.toggle_suppressed_many,
                    objs,
                )
            )

            menu.addSeparator()
            rename = menu.addAction(translate("Rename…"))
            rename.setEnabled(not several)
            rename.triggered.connect(lambda _checked=False, e=entry: self._rename(e))

            deletable = [e for e in selection if not e.is_base]
            delete = menu.addAction(
                translate("Delete %n feature(s)", None, len(deletable))
                if several
                else translate("Delete")
            )
            delete.setEnabled(bool(deletable))
            delete.triggered.connect(
                lambda _checked=False, es=deletable: self._delete(es)
            )
            menu.addSeparator()

        clear_tip = menu.addAction(translate("Move tip to start"))
        clear_tip.setEnabled(getattr(self._body, "Tip", None) is not None)
        clear_tip.triggered.connect(
            lambda _checked=False: self._run(
                translate("Cannot move the tip"), commands.set_tip, self._body, None
            )
        )

        tip_to_end = menu.addAction(translate("Move tip to end"))
        last_solid = next(
            (e for e in reversed(self._entries) if e.tip_allowed and not e.is_base),
            None,
        )
        tip_to_end.setEnabled(last_solid is not None and not last_solid.is_tip)
        if last_solid is not None:
            tip_to_end.triggered.connect(
                lambda _checked=False, e=last_solid: self._run(
                    translate("Cannot move the tip"),
                    commands.set_tip,
                    self._body,
                    e.obj,
                )
            )

        menu.addSeparator()
        show_non_solid = menu.addAction(translate("Show sketches and datums"))
        show_non_solid.setCheckable(True)
        show_non_solid.setChecked(self.panel.show_non_solid())
        show_non_solid.toggled.connect(self.panel.set_show_non_solid)

        exec_widget(menu, global_position)

    def _rename(self, entry) -> None:
        new_label, accepted = QtWidgets.QInputDialog.getText(
            self.view,
            translate("Rename feature"),
            translate("Label:"),
            text=entry.label,
        )
        if not accepted:
            return
        self._run(
            translate("Cannot rename the feature"),
            commands.rename_feature,
            entry.obj,
            new_label,
        )

    def _delete(self, entries) -> None:
        """Delete one or several features as a single undo step.

        Offers to take along any body member only the doomed features use — a
        Pad's profile sketch, say — but never one another feature still needs.
        """
        if not isinstance(entries, (list, tuple)):
            entries = [entries]
        entries = [e for e in entries if e is not None and not e.is_base]
        if not entries:
            return

        targets = [e.obj for e in entries]
        doomed = {id(obj) for obj in targets}
        children = []
        for obj in targets:
            for child in model.exclusive_children(self._body, obj):
                if id(child) not in doomed:
                    doomed.add(id(child))
                    children.append(child)

        if len(entries) == 1:
            message = translate("Delete %s?") % entries[0].label
        else:
            message = translate("Delete %n feature(s)?", None, len(entries))

        if children:
            question = QtWidgets.QMessageBox(self.view)
            question.setWindowTitle(translate("Delete feature"))
            question.setText(message)
            question.setInformativeText(
                translate("Nothing else uses %s. Delete it too?")
                % ", ".join(commands.iter_labels(children))
            )
            yes = question.addButton(translate("Delete both"), Enums.YesRole)
            only = question.addButton(translate("Features only"), Enums.NoRole)
            question.addButton(Enums.ButtonCancel)
            exec_widget(question)

            clicked = question.clickedButton()
            if clicked is yes:
                targets.extend(children)
            elif clicked is not only:
                return
        else:
            confirm = QtWidgets.QMessageBox.question(
                self.view,
                translate("Delete feature"),
                message,
                Enums.ButtonYes | Enums.ButtonNo,
                Enums.ButtonNo,
            )
            if confirm != Enums.ButtonYes:
                return

        self._run(
            translate("Cannot delete the feature"),
            commands.delete_features,
            self._body,
            targets,
        )

    # ------------------------------------------------------------------

    def _warn(self, title: str, message: str) -> None:
        with contextlib.suppress(Exception):
            _app().Console.PrintWarning(f"Timeline: {title} — {message}\n")
        QtWidgets.QMessageBox.warning(self.view, title, message)


_controller: TimelineController | None = None


def controller() -> TimelineController:
    """The process-wide controller, created on first use."""
    global _controller
    if _controller is None:
        _controller = TimelineController()
    return _controller


def show_timeline(honour_saved_visibility: bool = False) -> TimelineController:
    """Create the dock if needed and reveal it.

    The startup path passes ``honour_saved_visibility=True`` so a dock the user
    closed last session stays closed; the toolbar command leaves it ``False``
    and always shows it.
    """
    instance = controller()
    instance.install(honour_saved_visibility=honour_saved_visibility)
    return instance
