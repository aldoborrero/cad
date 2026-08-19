# SPDX-License-Identifier: LGPL-2.1-or-later
"""Addon entry point.

FreeCAD executes this at startup for every directory under ``Mod``.  The
timeline is not a workbench — it is a global dock that should be available
whatever workbench is active — so instead of registering a workbench we defer
creating the dock until the main window exists, then add it once.

Creating widgets directly from here is unsafe: ``InitGui.py`` runs while the
main window is still being assembled.  A zero-delay single-shot timer moves the
work to the first spin of the event loop, by which point ``getMainWindow()``
returns a fully built window.
"""

import os
import sys

import FreeCAD
import FreeCADGui

ADDON_DIRECTORY = os.path.dirname(__file__)

# The addon ships its Python package alongside this file; Mod directories are
# not on sys.path automatically.
if ADDON_DIRECTORY not in sys.path:
    sys.path.append(ADDON_DIRECTORY)


class TimelineCommand:
    """``Timeline_Show`` — reveal the timeline dock."""

    def GetResources(self):
        from freecad_timeline.qtcompat import translate

        return {
            "Pixmap": os.path.join(
                ADDON_DIRECTORY, "resources", "icons", "Timeline.svg"
            ),
            "MenuText": translate("Feature timeline"),
            "ToolTip": translate(
                "Show the horizontal feature timeline for the active body"
            ),
        }

    def IsActive(self):
        return True

    def Activated(self):
        from freecad_timeline.integration import show_timeline

        show_timeline()


def _install_dock():
    try:
        from freecad_timeline import translations
        from freecad_timeline.integration import show_timeline

        # Register catalogues before any widget is built, so the first render
        # is already translated.
        translations.install()

        # Respect a dock the user closed in a previous session; it is still
        # added, so its View -> Panels entry brings it back.
        show_timeline(honour_saved_visibility=True)
    except Exception:
        import traceback

        FreeCAD.Console.PrintError(
            f"Timeline: failed to create the dock widget\n{traceback.format_exc()}\n"
        )


def _schedule_install():
    """Defer dock creation to the first event-loop iteration."""
    try:
        from PySide import QtCore
    except ImportError:  # pragma: no cover - non-standard FreeCAD build
        FreeCAD.Console.PrintError("Timeline: PySide is not available\n")
        return
    QtCore.QTimer.singleShot(0, _install_dock)


FreeCADGui.addCommand("Timeline_Show", TimelineCommand())
_schedule_install()
