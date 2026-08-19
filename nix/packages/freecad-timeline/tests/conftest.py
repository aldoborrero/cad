# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fixtures shared by the test modules.

The Qt fixtures live here rather than being repeated per module: three copies
of a session-scoped ``QApplication`` (each with its own module-level reference
to keep it alive) is exactly the kind of duplication that drifts.
"""

from __future__ import annotations

import pytest

#: Held at module scope so the QApplication outlives every widget — letting
#: Python collect it while widgets are still alive crashes Qt at exit.
_APP = None


def qt_available() -> bool:
    """Whether any supported Qt binding can be imported.

    Deliberately routes through ``qtcompat`` rather than naming PySide6: the
    addon supports PySide (inside FreeCAD), PySide6 and PySide2, and hardcoding
    one of them made the Qt tests skip on a Qt5 build while reporting "no Qt
    binding available", which was simply untrue.
    """
    try:
        import freecad_timeline.qtcompat  # noqa: F401

        return True
    except ImportError:
        return False


def requires_qt():
    """Skip marker for the Qt tier."""
    return pytest.mark.skipif(not qt_available(), reason="no Qt binding available")


@pytest.fixture(scope="session")
def qapp():
    global _APP
    from freecad_timeline.qtcompat import QtWidgets

    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield _APP
    _APP.closeAllWindows()
    _APP.processEvents()


@pytest.fixture
def destroy_widgets():
    """Tear down every top-level widget a test created.

    Widgets left to the garbage collector are destroyed in an arbitrary order
    relative to the QApplication, which is an intermittent crash at exit.
    """
    yield
    from freecad_timeline.qtcompat import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    for widget in list(app.topLevelWidgets()):
        widget.hide()
        widget.setParent(None)
        widget.deleteLater()
    app.processEvents()
