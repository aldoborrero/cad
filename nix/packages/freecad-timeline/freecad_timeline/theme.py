# SPDX-License-Identifier: LGPL-2.1-or-later
"""Colours derived from the active palette.

Nothing here is hardcoded: every colour comes from the widget's ``QPalette``,
so the timeline follows whatever stylesheet is loaded (ProDark, OpenTheme dark,
the light default, or a user's own).  The only decisions we make are *relative*
ones — how far to fade a rolled-back feature, how to tint the tip marker —
expressed as alpha and as blends between existing palette roles.
"""

from __future__ import annotations

from .qtcompat import Enums, QtGui

__all__ = ["Palette", "colors", "is_dark"]

#: Opacity applied to features after the tip (rolled back, not in the result).
DIM_OPACITY = 0.40
#: Opacity applied to suppressed features (present but switched off).
GHOST_OPACITY = 0.55


def _color(palette, group, role):
    return QtGui.QColor(palette.color(group, role))


def is_dark(palette) -> bool:
    """Whether the current theme is dark, judged by window lightness."""
    window = _color(palette, Enums.ColorActive, Enums.RoleWindow)
    return window.lightness() < 128


def _blend(first, second, ratio):
    """Linear blend, ``ratio`` 0 -> first, 1 -> second."""
    inverse = 1.0 - ratio
    return QtGui.QColor(
        int(first.red() * inverse + second.red() * ratio),
        int(first.green() * inverse + second.green() * ratio),
        int(first.blue() * inverse + second.blue() * ratio),
    )


class Palette:
    """The handful of colours the timeline paints with."""

    __slots__ = (
        "background",
        "dark",
        "dim_text",
        "drop",
        "error",
        "highlight",
        "highlight_text",
        "separator",
        "text",
        "tip",
        "tip_shadow",
        "warning",
    )

    def __init__(self, palette):
        self.dark = is_dark(palette)

        self.text = _color(palette, Enums.ColorActive, Enums.RoleText)
        self.dim_text = _color(palette, Enums.ColorDisabled, Enums.RoleText)
        self.background = _color(palette, Enums.ColorActive, Enums.RoleBase)
        self.highlight = _color(palette, Enums.ColorActive, Enums.RoleHighlight)
        self.highlight_text = _color(
            palette, Enums.ColorActive, Enums.RoleHighlightedText
        )
        self.separator = _color(palette, Enums.ColorActive, Enums.RoleMid)

        # Some themes leave Disabled/Text barely distinguishable from Text;
        # pull it towards the background so rolled-back features really recede.
        if abs(self.dim_text.lightness() - self.text.lightness()) < 24:
            self.dim_text = _blend(self.text, self.background, 0.55)

        # The tip marker uses the theme's own accent so it never clashes.
        self.tip = QtGui.QColor(self.highlight)
        if self.tip.saturation() < 40:
            # A greyscale highlight (some minimal themes) gives no accent to
            # work with; fall back to maximum contrast against the background.
            self.tip = QtGui.QColor(self.text)
        self.tip_shadow = QtGui.QColor(self.tip)
        self.tip_shadow.setAlpha(60)

        self.drop = QtGui.QColor(self.highlight)

        # Status badges are the one place we do not follow the palette's hue.
        # "Failed" and "out of date" are semantic, like a traffic light: tinting
        # them with the theme accent would make an error badge indistinguishable
        # from the selection colour. We keep the hue fixed and adapt only
        # lightness so they stay legible on a dark or a light background.
        self.error = QtGui.QColor.fromHsl(0, 190, 145 if self.dark else 105)
        self.warning = QtGui.QColor.fromHsl(38, 200, 140 if self.dark else 95)


def colors(widget) -> Palette:
    """Build a :class:`Palette` from ``widget``'s current palette.

    Call this on every paint rather than caching: FreeCAD swaps stylesheets at
    runtime when the user changes theme, and the widget palette changes with it.
    """
    return Palette(widget.palette())
