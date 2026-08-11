"""Measure QColor::lighter/darker so the tests can assert against Qt, not against
our own arithmetic.

freecad/fusiontabs/tokens.py re-implements the colour functions FreeCAD's theme
engine uses, because 1.1.1 exposes none of the engine to Python. A re-implementation
is only worth anything if something checks it, and the only authority is a real
QColor — so this prints a table of (colour, factor) -> result that is pasted into
tests/test_tokens.py.

Run it inside FreeCAD's own interpreter, which is where PySide6 lives:

    nix shell nixpkgs#freecad --command freecadcmd \\
      nix/packages/fusionlook/tools/qcolor_reference.py

It needs no display: QColor is in QtGui but does not touch one.
"""

# Only ever run by hand, inside FreeCAD, which is where PySide6 lives.
from PySide6.QtGui import QColor

COLOURS = [
    "#2a2e34",  # the theme's PrimaryColor
    "#1e2126",  # its strip
    "#2a9df4",  # its accent
    "#e8eaed",  # its text
    "#191919",  # FreeCAD Dark's PrimaryColor, where the extreme factors are used
    "#ffffff",
    "#000000",
    "#7f0000",  # fully saturated, to exercise the hue path
]

FACTORS = [10, 12, 20, 22, 34, 35, 40, 48, 50, 55, 70, 90, 120, 200, 260, 300, 5890]


def main() -> None:
    print("# colour, amount, lighten, darken")
    for colour in COLOURS:
        for amount in FACTORS:
            base = QColor(colour)
            lighter = base.lighter(100 + amount).name()
            darker = base.darker(100 + amount).name()
            print(f'    ("{colour}", {amount}, "{lighter}", "{darker}"),')


main()
