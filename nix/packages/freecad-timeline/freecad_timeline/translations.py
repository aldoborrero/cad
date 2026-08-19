# SPDX-License-Identifier: LGPL-2.1-or-later
"""Load the addon's ``.qm`` catalogues into FreeCAD.

``FreeCADGui.addLanguagePath`` registers a directory with FreeCAD's own
translator machinery, so catalogues named ``Timeline_<locale>.qm`` are picked
up and — importantly — reloaded when the user changes language in
Preferences, rather than only at startup.
"""

from __future__ import annotations

import os

__all__ = ["TRANSLATIONS_DIRECTORY", "available_locales", "install"]

TRANSLATIONS_DIRECTORY = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "resources",
    "translations",
)


def available_locales(directory: str | None = None) -> list[str]:
    """Locales with a compiled catalogue, e.g. ``["de", "es-ES"]``."""
    directory = directory or TRANSLATIONS_DIRECTORY
    if not os.path.isdir(directory):
        return []
    locales = []
    for name in sorted(os.listdir(directory)):
        if name.startswith("Timeline_") and name.endswith(".qm"):
            locales.append(name[len("Timeline_") : -len(".qm")])
    return locales


def install(directory: str | None = None) -> bool:
    """Register the catalogue directory with FreeCAD.

    Returns ``True`` when the path was registered.  Safe to call outside
    FreeCAD, or with no catalogues shipped yet, in which case Qt simply falls
    back to the English source strings.
    """
    directory = directory or TRANSLATIONS_DIRECTORY
    if not os.path.isdir(directory):
        return False
    try:
        import FreeCADGui

        FreeCADGui.addLanguagePath(directory)
        return True
    except Exception:
        return False
