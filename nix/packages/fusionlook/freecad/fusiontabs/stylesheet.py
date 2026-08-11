"""The two stylesheets FusionTabs puts on individual widgets.

A theme cannot carry these rules. FreeCAD's stylesheet is one file — `defaults.qss`
plus whichever `.qss` `MainWindow/StyleSheet` names (Gui/Application.cpp,
`setStyleSheet`) — and there is no include mechanism, so a theme that wanted to add
a rule would have to ship a fork of the 2700-line `FreeCAD.qss` and inherit its bugs
forever. Instead the theme carries the palette and this module turns that palette
into two small sheets, applied with `QWidget::setStyleSheet` on the tab bars
themselves. Qt merges those with the application sheet rather than replacing it, so
everything else stays exactly as the active theme drew it, and removing the addon
removes the rules.

Both selectors were read off the source rather than guessed, and one of them is not
what it looks like:

  * `QTabBar#mdiAreaTabBar` — the document tabs. Gui/MainWindow.cpp gives the
    QMdiArea's tab bar that object name explicitly, and the stock FreeCAD.qss
    already styles it, so these rules override rather than introduce.
  * `#WbTabBar QTabBar` — the workbench selector. `WbTabBar` is the object name of
    the *container* `WorkbenchTabWidget` (Gui/WorkbenchSelector.cpp:111), not of the
    QTabBar inside it, which has no object name at all. `QTabBar#WbTabBar` therefore
    matches nothing; it has to be a descendant selector.
"""

from __future__ import annotations

from dataclasses import dataclass

from freecad.fusiontabs import tokens

# Where each colour comes from, in order of preference: a token this repo's theme
# defines, then one any FreeCAD 1.1 theme defines, then a literal for the case
# where the active theme has neither (someone running FusionTabs on Classic).
SOURCES: dict[str, tuple[tuple[str, ...], str]] = {
    "strip": (("FusionStripColor", "TabbarBackgroundColor"), "#1e2126"),
    "surface": (("PrimaryColor", "GeneralBackgroundColor"), "#2a2e34"),
    "accent": (("AccentColor", "ThemeAccentColor1"), "#2a9df4"),
    "text": (("TextForegroundColor",), "#e8eaed"),
    "muted": (("FusionTextMutedColor", "TextDisabledColor"), "#8b9199"),
    "hover": (("GeneralBackgroundHoverColor", "PrimaryColorLighten3"), "#3a3e46"),
}


@dataclass(frozen=True)
class Palette:
    """The six colours the two sheets are written in."""

    strip: tokens.Colour
    surface: tokens.Colour
    accent: tokens.Colour
    text: tokens.Colour
    muted: tokens.Colour
    hover: tokens.Colour


def palette(theme: dict[str, str]) -> Palette:
    """Read the palette out of a resolved theme, falling back per slot.

    Per slot rather than all-or-nothing: a theme that defines a primary colour and
    nothing else should still get its primary colour used.
    """
    chosen: dict[str, tokens.Colour] = {}
    for slot, (names, fallback) in SOURCES.items():
        chosen[slot] = tokens.parse_colour(fallback)
        for name in names:
            try:
                chosen[slot] = tokens.resolve(name, theme)
            except tokens.Unresolved:
                continue
            break
    return Palette(**chosen)


# Both edges are written every time. The document tabs are at the top when the
# addon has moved them and at the bottom when it has not, or when a future FreeCAD
# stops honouring the move; a sheet that only knew about one would leave the other
# unstyled rather than merely unmoved.
_DOCUMENT_TABS = """\
/* FusionTabs: document tabs (QMdiArea) */
QTabBar#mdiAreaTabBar {{
  background-color: {strip};
  qproperty-drawBase: 0;
}}
QTabBar#mdiAreaTabBar::tab {{
  background-color: {strip};
  color: {muted};
  border: none;
  padding: 4px 14px;
  margin: 0px;
  min-width: 96px;
}}
QTabBar#mdiAreaTabBar::tab:top {{
  border-top: 2px solid {strip};
}}
QTabBar#mdiAreaTabBar::tab:bottom {{
  border-bottom: 2px solid {strip};
}}
QTabBar#mdiAreaTabBar::tab:selected {{
  background-color: {surface};
  color: {text};
}}
QTabBar#mdiAreaTabBar::tab:top:selected {{
  border-top: 2px solid {accent};
}}
QTabBar#mdiAreaTabBar::tab:bottom:selected {{
  border-bottom: 2px solid {accent};
}}
QTabBar#mdiAreaTabBar::tab:!selected:hover {{
  background-color: {hover};
  color: {text};
}}
QTabBar#mdiAreaTabBar::close-button {{
  margin-left: 6px;
  border-radius: 2px;
}}
QTabBar#mdiAreaTabBar::close-button:hover {{
  background-color: {accent};
}}
"""

# No background on the selected tab and no border anywhere: the workbench strip is
# meant to read as text with a marker under the current one, the way Fusion's does.
_WORKBENCH_TABS = """\
/* FusionTabs: workbench selector */
#WbTabBar QTabBar {{
  background-color: transparent;
  qproperty-drawBase: 0;
}}
#WbTabBar QTabBar::tab {{
  background-color: transparent;
  color: {muted};
  border: none;
  border-bottom: 2px solid transparent;
  padding: 4px 10px;
  margin: 0px;
}}
#WbTabBar QTabBar::tab:selected {{
  background-color: transparent;
  color: {text};
  border-bottom: 2px solid {accent};
}}
#WbTabBar QTabBar::tab:!selected:hover {{
  background-color: {hover};
  color: {text};
}}
#WbTabBar QToolButton#WbTabBarMore {{
  background-color: transparent;
  border: none;
  padding-right: 12px;
}}
"""


def _slots(colours: Palette) -> dict[str, str]:
    return {name: str(colour) for name, colour in vars(colours).items()}


def document_tabs(colours: Palette) -> str:
    """The sheet for the `#mdiAreaTabBar` widget."""
    return _DOCUMENT_TABS.format(**_slots(colours))


def workbench_tabs(colours: Palette) -> str:
    """The sheet for the `#WbTabBar` container widget."""
    return _WORKBENCH_TABS.format(**_slots(colours))
