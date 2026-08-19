# SPDX-License-Identifier: LGPL-2.1-or-later
"""Timeline — a horizontal, Fusion 360-style feature timeline for FreeCAD.

The package is split so that the interesting logic can be tested without a GUI:

``model``
    Pure, Qt-free reading of a body (``Group``/``Tip``/``Suppressed``,
    feature classification, ordering, move planning).
``commands``
    Transaction-wrapped mutations, also Qt-free.
``qtcompat``, ``theme``, ``view``, ``panel``
    The Qt layer.
``observers``, ``integration``
    Active-body tracking and the wiring that installs the dock widget.

Only :mod:`model` and :mod:`commands` are imported here; everything Qt-related
is imported lazily so ``import freecad_timeline`` stays safe in a headless
interpreter.
"""

from typing import Any

from . import commands, model

__version__ = "1.0.0"

__all__ = ["__version__", "commands", "model"]


def show_timeline() -> Any:
    """Create (or reveal) the timeline dock.  Requires a running FreeCAD GUI."""
    from .integration import show_timeline as _show

    return _show()
