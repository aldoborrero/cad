# SPDX-License-Identifier: LGPL-2.1-or-later
"""Document and selection observers.

Both classes are deliberately dumb: they decide *whether* a change is worth a
repaint and then call a single callback.  The debouncing lives in the
controller, so a recompute that fires dozens of ``slotChangedObject`` calls
still results in one refresh.

Every slot takes ``*args``.  FreeCAD invokes these by name with a fixed arity
that has changed across versions, and a ``TypeError`` raised inside an observer
is swallowed into a console traceback on every single document change.
"""

from __future__ import annotations

__all__ = [
    "WATCHED_PROPERTIES",
    "TimelineDocumentObserver",
    "TimelineSelectionObserver",
]

#: Property changes that can alter what the timeline shows.  Anything else
#: (sketch geometry, pad length, placement…) is ignored: it triggers a
#: recompute, and ``slotRecomputedDocument`` already covers that.
WATCHED_PROPERTIES = frozenset(
    {
        "Group",
        "Tip",
        "BaseFeature",
        "Label",
        "Suppressed",
        "Visibility",
        "TransformMode",
        "Originals",
    }
)


class TimelineDocumentObserver:
    """Register with ``App.addDocumentObserver``."""

    def __init__(self, callback):
        self._callback = callback

    def _notify(self):
        try:
            self._callback()
        except Exception:  # never let an observer break the document
            import traceback

            traceback.print_exc()

    # -- object level ------------------------------------------------------

    def slotCreatedObject(self, *args):
        self._notify()

    def slotDeletedObject(self, *args):
        self._notify()

    def slotChangedObject(self, *args):
        # args == (obj, property_name)
        if len(args) >= 2 and args[1] not in WATCHED_PROPERTIES:
            return
        self._notify()

    # -- document level ----------------------------------------------------

    def slotDeletedDocument(self, *args):
        self._notify()

    def slotActivateDocument(self, *args):
        self._notify()

    def slotRelabelDocument(self, *args):
        self._notify()

    def slotRecomputedDocument(self, *args):
        self._notify()

    def slotUndoDocument(self, *args):
        self._notify()

    def slotRedoDocument(self, *args):
        self._notify()


class TimelineSelectionObserver:
    """Register with ``Gui.Selection.addObserver``.

    Mirrors the callback names in ``SelectionObserverPython.cpp``.  Preselection
    (hover) is intentionally not handled — it fires continuously as the mouse
    moves over the 3D view.
    """

    def __init__(self, callback):
        self._callback = callback

    def _notify(self):
        try:
            self._callback()
        except Exception:
            import traceback

            traceback.print_exc()

    def addSelection(self, *args):
        self._notify()

    def removeSelection(self, *args):
        self._notify()

    def setSelection(self, *args):
        self._notify()

    def clearSelection(self, *args):
        self._notify()
