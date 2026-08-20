"""FusionLook: what runs when the FreeCAD GUI starts.

FreeCAD imports this module because `freecad/fusionlook/` is a namespace package on
a module path and this file is called `init_gui.py` — the pkgutil walk at the end of
Gui/FreeCADGuiInit.py. There is deliberately no `InitGui.py` beside `package.xml`:
FreeCAD runs both mechanisms, so an addon carrying both would install itself twice.

Everything here is guarded. This module is imported before the main window is on
screen and it reaches for widgets by object name, which is a contract FreeCAD can
change in any release; when a lookup comes back empty the addon says so in the
report view and leaves that part of the UI alone. Nothing it does may stop FreeCAD
from starting, which is why every entry point is wrapped.

The colours come from the active theme rather than from here, so FusionLook follows
whatever theme is selected — see stylesheet.py for the per-slot fallbacks that make
it do something reasonable under a theme that never heard of it.
"""

from __future__ import annotations

import os
from typing import Any

import FreeCAD
from PySide import QtCore, QtWidgets

from freecad.fusionlook import settings, stylesheet, tokens

# The tab bars are not all there when this module is imported: the MDI area exists
# with the main window, but the workbench selector is built with the toolbar it
# lives in and then lays itself out 500 ms later (Gui/WorkbenchSelector.cpp). So the
# install runs again at each of these delays, in ms, until it finds both and stops.
ATTEMPTS_MS = (0, 300, 900, 2000, 5000)

# Rebuilt toolbars arrive with none of our stylesheet on them. 600 ms clears the
# 500 ms layout timer WorkbenchTabWidget starts on itself.
RESTYLE_DELAY_MS = 600

# The two things that leave our sheets wrong.
#
# ChildAdded is a toolbar arriving: ToolBarManager::setup builds one and hands it to
# getMainWindow()->addToolBar the first time a workbench asks for a name that does not
# exist yet. Not a workbench switch — that reuses a toolbar by name and leaves its
# actions in place ("we do not remove and re-add the actions because this causes
# flicker effects", Gui/ToolBarManager.cpp), so WorkbenchTabWidget survives it styled.
#
# StyleChange is the application stylesheet being replaced, which is what a theme
# switch does: Application::initStyleParameterManager installs a delayed handler on
# MainWindow/{Theme,StyleSheet} that reloads and calls setStyleSheet, with no restart.
RESTYLE_EVENTS = (
    QtCore.QEvent.Type.ChildAdded,
    QtCore.QEvent.Type.StyleChange,
)

MDI_TAB_BAR = "mdiAreaTabBar"
WORKBENCH_SELECTOR = "WbTabBar"

PAGE = os.path.join(
    os.path.dirname(__file__), "Resources", "ui", "preferences-fusionlook.ui"
)

# What FreeCAD reads out of user.cfg instead of out of a theme file, and where from
# (StyleParameters::BuiltInParameterSource).
BUILT_IN_TOKENS = {
    "ThemeAccentColor1": "User parameter:BaseApp/Preferences/Themes",
    "ThemeAccentColor2": "User parameter:BaseApp/Preferences/Themes",
    "ThemeAccentColor3": "User parameter:BaseApp/Preferences/Themes",
    "BackgroundColor": "User parameter:BaseApp/Preferences/View",
}


def _log(message: str) -> None:
    FreeCAD.Console.PrintLog(f"FusionLook: {message}\n")


def _message(message: str) -> None:
    FreeCAD.Console.PrintMessage(f"FusionLook: {message}\n")


def _warn(message: str) -> None:
    FreeCAD.Console.PrintWarning(f"FusionLook: {message}\n")


def enabled(key: str) -> bool:
    option = settings.BY_KEY[key]
    params = FreeCAD.ParamGet(settings.PREFERENCES)
    return bool(params.GetBool(option.key, option.default))


def _main_window() -> Any:
    """FreeCADGui is imported here rather than at the top of the module: this file
    is imported while the GUI is still being assembled."""
    import FreeCADGui

    return FreeCADGui.getMainWindow()


def _built_in_tokens() -> dict[str, str]:
    """The four parameters that live in preferences rather than in a theme.

    They are packed 0xRRGGBBAA and read back with `color >> 8`, the same shift
    BuiltInParameterSource::get formats them with.

    One deliberate deviation: FreeCAD hands back `#000000` for a key it has never
    written, because `GetUnsigned(name, 0)` and the format are unconditional. Here a
    0 means "unset" and is dropped, which lets the theme file supply the token
    instead of everything that references it going black.
    """
    found = {}
    for name, path in BUILT_IN_TOKENS.items():
        packed = int(FreeCAD.ParamGet(path).GetUnsigned(name, 0))
        if packed:
            found[name] = f"#{(packed >> 8) & 0xFFFFFF:06x}"
    return found


def _theme_file() -> str:
    """The path FreeCAD resolves the active theme to.

    Gui/Application.cpp, `deduceParametersFilePath`: an explicit override, else the
    theme's name under the `qss:` search path — which includes every installed
    preference pack's directory, because PreferencePack's constructor appends it.
    """
    group = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/MainWindow")
    override = str(group.GetString("ThemeStyleParametersFile", ""))
    if override:
        return override
    return f"qss:parameters/{group.GetString('Theme', 'Classic')}.yaml"


def _theme() -> dict[str, str]:
    """Every parameter the active theme resolves against, or just the built-ins.

    Read through QFile rather than open(), because `qss:` is a Qt search path and
    only Qt knows what it expands to.

    The built-ins are merged *last*, which is the order FreeCAD resolves in and the
    opposite of how the merge reads. `initStyleParameterManager` registers built-in,
    fallback, theme, user; the list is walked in reverse with `addSource` doing a
    `push_front`, and `ParameterManager::parameter` takes the first source that has
    the name — so the four built-ins override a theme that defines them. This theme
    defines none of them, but a third-party one would otherwise get its tabs painted
    in a colour the rest of the window is not using.
    """
    built_ins = _built_in_tokens()
    path = _theme_file()

    handle = QtCore.QFile(path)
    if not handle.open(QtCore.QIODevice.OpenModeFlag.ReadOnly):
        _log(f"no theme parameters at {path}; using the fallback palette")
        return built_ins

    try:
        text = bytes(handle.readAll().data()).decode("utf-8")
    finally:
        handle.close()

    parameters: dict[str, str] = {}
    try:
        parameters = tokens.parse(text)
    except Exception as exc:
        _warn(f"could not read {path}: {exc}")

    parameters.update(built_ins)
    return parameters


def _move_document_tabs(window: Any) -> bool:
    """Point 1: the document tabs above the 3D view instead of below it.

    MainWindow.cpp hardcodes `setTabPosition(QTabWidget::South)`, but it is a plain
    Qt property, so the move is one call and needs no patched FreeCAD.
    """
    area = window.findChild(QtWidgets.QMdiArea)
    if area is None:
        _warn("no QMdiArea in the main window; leaving the document tabs alone")
        return False
    area.setTabPosition(QtWidgets.QTabWidget.TabPosition.North)
    return True


def _use_tab_selector() -> None:
    """Point 2. FreeCAD's own tab bar, not one of ours — this only sets the
    preference Gui/Action.cpp reads when it builds the Workbench toolbar."""
    group = FreeCAD.ParamGet(settings.WORKBENCH_GROUP)
    if int(group.GetInt(settings.SELECTOR_TYPE_KEY, 0)) == settings.SELECTOR_TAB_BAR:
        return
    group.SetInt(settings.SELECTOR_TYPE_KEY, settings.SELECTOR_TAB_BAR)
    _message(
        "switched the workbench selector to a tab bar. That is a stock FreeCAD "
        "preference and stays set if this addon is removed; Preferences > "
        "Workbenches puts it back."
    )


def apply_to(window: Any, colours: stylesheet.Palette) -> bool:
    """One pass over the widgets. True when there was nothing left to find.

    Qt merges a widget's own stylesheet with the application's rather than
    replacing it, so these rules compose with the active theme and disappear with
    the addon.
    """
    complete = True

    if enabled("DocumentTabsOnTop") or enabled("StyleDocumentTabs"):
        tab_bar = window.findChild(QtWidgets.QTabBar, MDI_TAB_BAR)
        if tab_bar is None:
            complete = False
        else:
            if enabled("DocumentTabsOnTop"):
                complete = _move_document_tabs(window) and complete
            if enabled("StyleDocumentTabs"):
                tab_bar.setStyleSheet(stylesheet.document_tabs(colours))

    if enabled("StyleWorkbenchTabs"):
        # The object name is on the container, not on the QTabBar inside it.
        selector = window.findChild(QtWidgets.QWidget, WORKBENCH_SELECTOR)
        if selector is None:
            complete = False
        else:
            selector.setStyleSheet(stylesheet.workbench_tabs(colours))

    return complete


class _Installer(QtCore.QObject):  # type: ignore[misc]
    """Retries the install until both tab bars exist, then stops.

    It then keeps watching the main window, for the two things that undo the work:
    a toolbar arriving with none of our stylesheet on it, and a theme switch, after
    which our colours are the only ones in the window still coming from the old
    theme. See RESTYLE_EVENTS.
    """

    def __init__(self) -> None:
        super().__init__()
        self._attempt = 0
        self._colours: stylesheet.Palette | None = None
        self._watching = False
        self._pending = False
        self._applying = False

    def _palette(self) -> stylesheet.Palette:
        if self._colours is None:
            self._colours = stylesheet.palette(_theme())
        return self._colours

    def schedule(self, delay: int) -> None:
        QtCore.QTimer.singleShot(delay, self.run)

    def run(self) -> None:
        try:
            self._run()
        except Exception as exc:  # never take FreeCAD's start-up down with us
            _warn(f"could not apply the tab styling: {exc}")

    def _run(self) -> None:
        window = _main_window()
        if window is None:
            self._retry()
            return

        if not self._watching:
            window.installEventFilter(self)
            self._watching = True

        self._applying = True
        try:
            complete = apply_to(window, self._palette())
        finally:
            self._applying = False

        if complete:
            _log("document and workbench tabs styled")
            return

        self._retry()

    def _retry(self) -> None:
        self._attempt += 1
        if self._attempt >= len(ATTEMPTS_MS):
            _log(
                "gave up looking for the tab bars: FreeCAD's widget names may have "
                "changed, or the workbench toolbar is hidden"
            )
            return
        self.schedule(ATTEMPTS_MS[self._attempt])

    def eventFilter(self, watched: Any, event: Any) -> bool:  # Qt's spelling
        """Coalesced on purpose: start-up alone adds twenty-odd children to the main
        window, and one pass covers all of them. Never returns True — this filter
        watches, it does not consume.

        Deaf while a pass is running: Qt delivers a style change synchronously, so a
        pass cannot schedule the next one. Without it, a wrong guess about which
        widget an event reaches is a 600 ms loop for the session, not one wasted pass.
        """
        if self._applying or self._pending:
            return False
        if event.type() in RESTYLE_EVENTS:
            self._pending = True
            QtCore.QTimer.singleShot(RESTYLE_DELAY_MS, self._restyle)
        return False

    def _restyle(self) -> None:
        self._pending = False
        # Read the theme again: one of the events that gets us here is a theme switch,
        # which FreeCAD applies without a restart. A cached palette would leave the two
        # tab bars in the old theme's colours while everything else moved.
        self._colours = None
        self._applying = True
        try:
            window = _main_window()
            if window is not None:
                apply_to(window, self._palette())
        except Exception as exc:
            _warn(f"could not re-apply the tab styling: {exc}")
        finally:
            self._applying = False


_installer = _Installer()


def install() -> None:
    """Everything the addon does. The widget work is scheduled onto the event loop,
    which has not started yet: a widget looked up now would not be there."""
    try:
        import FreeCADGui

        FreeCADGui.addPreferencePage(PAGE, "Display")
    except Exception as exc:
        _warn(f"could not add the preferences page: {exc}")

    try:
        if enabled("UseWorkbenchTabSelector"):
            _use_tab_selector()
    except Exception as exc:
        _warn(f"could not set the workbench selector type: {exc}")

    _installer.schedule(ATTEMPTS_MS[0])


install()
