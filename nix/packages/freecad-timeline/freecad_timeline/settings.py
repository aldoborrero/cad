# SPDX-License-Identifier: LGPL-2.1-or-later
"""Persisted preferences, stored in FreeCAD's parameter tree.

FreeCAD's own docks persist their visibility through ``DockWindowManager``,
which writes to ``BaseApp/MainWindow/DockWindows`` — but that is C++ only and
manages just the docks it registered itself.  A dock added from Python via
``addDockWidget`` gets none of it, so without this module the timeline would
reappear on every start even after the user closed it.

``FreeCAD`` is imported lazily so the module stays importable headlessly, and
every accessor degrades to its default when the parameter tree is unreachable.
"""

from __future__ import annotations

import contextlib
from typing import Any

__all__ = [
    "PARAMETER_PATH",
    "SHOW_LABELS",
    "SHOW_NON_SOLID",
    "VISIBLE",
    "get_bool",
    "parameter_group",
    "set_bool",
]

PARAMETER_PATH = "User parameter:BaseApp/Preferences/Mod/Timeline"

#: Whether the dock was on screen when FreeCAD last closed.
VISIBLE = "Visible"
#: Whether sketches, datums and other non-solid members are shown.
SHOW_NON_SOLID = "ShowNonSolid"

#: Whether feature names are shown under the icons (off = Fusion-like strip).
SHOW_LABELS = "ShowLabels"


def parameter_group() -> Any:
    """The addon's parameter group, or ``None`` outside FreeCAD."""
    try:
        import FreeCAD

        return FreeCAD.ParamGet(PARAMETER_PATH)
    except Exception:
        return None


def get_bool(name: str, default: bool = False) -> bool:
    group = parameter_group()
    if group is None:
        return default
    try:
        return bool(group.GetBool(name, default))
    except Exception:
        return default


def set_bool(name: str, value: bool) -> None:
    group = parameter_group()
    if group is None:
        return
    with contextlib.suppress(Exception):
        group.SetBool(name, bool(value))
