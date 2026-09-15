"""Build a XIAO footprint whose pads are NAMED, not numbered.

KiCad ships no XIAO symbol, and its MCU_Seeed_ESP32C3 footprint numbers pads 1..14 with
no labels and no distinguishing pad-1 shape — so turning a number into a GPIO would be
an assumption, and a wrong one makes a board that does not work. Naming the pads after
Seeed's own labels removes the mapping: a net lands on "D3", not on "pad 4".

Geometry is the stock footprint's, which matches the module: 2x7 at 2.54 mm, x = +-8.5.

The file is emitted as s-expressions rather than through pcbnew: `FootprintSave` needs a
plugin that resolves to None headless, the same way ExportSpecctraDSN and ZONE_FILLER do.
The result is loaded back and checked, so "KiCad can read this" is asserted, not assumed.

Run: make-xiao-footprint   (from projects/espmmwave-v0.2.0, with direnv active)
"""

from __future__ import annotations

import pathlib
import sys

import pcbnew
from xiao import (
    BODY_H,
    BODY_W,
    DESCRIPTION,
    LEFT,
    NAME,
    PAD_H,
    PAD_W,
    PITCH,
    RIGHT,
    X,
    Y0,
)

HERE = pathlib.Path(__file__).resolve().parent
LIB = HERE.parent / "kicad" / "espmmwave.pretty"


# The file format KiCad 10 itself writes. Checked against what pcbnew produces for a new
# board rather than copied off an older file — a stale version here is what makes KiCad
# announce the project was made by an older release and offer to convert it.
VERSION = "20260206"


def line(a: tuple[float, float], b: tuple[float, float], layer: str, w: float) -> str:
    return (
        f"\t(fp_line (start {a[0]} {a[1]}) (end {b[0]} {b[1]})"
        f' (stroke (width {w}) (type solid)) (layer "{layer}"))'
    )


def rectangle(half_w: float, half_h: float, layer: str, w: float) -> list[str]:
    pts = [(-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h)]
    return [line(pts[i], pts[(i + 1) % 4], layer, w) for i in range(4)]


def silkscreen() -> list[str]:
    """The body outline, broken where it would otherwise print onto a pad.

    Silkscreen ink on a pad interferes with soldering, and DRC says so: the first version
    of this footprint drew the body as a plain rectangle and raised silk_over_copper
    fourteen times, once per pad. The body edge at x = +-8.75 runs down the middle of
    pads spanning 7.0..10.0, so the sides cannot be drawn — only the two ends, which
    clear the outermost pad at y = +-8.62, and corner stubs that stop short of it.
    """
    w, h = BODY_W / 2, BODY_H / 2
    stub_to = 8.62 + 0.3  # just past the last pad
    out = [line((-w, y), (w, y), "F.SilkS", 0.12) for y in (-h, h)]
    for x in (-w, w):
        out.append(line((x, -h), (x, -stub_to), "F.SilkS", 0.12))
        out.append(line((x, h), (x, stub_to), "F.SilkS", 0.12))
    return out


def build() -> str:
    out = [
        f'(footprint "{NAME}"',
        f"\t(version {VERSION})",
        '\t(generator "espmmwave")',
        '\t(generator_version "10.0")',
        '\t(layer "F.Cu")',
        f'\t(descr "{DESCRIPTION}")',
        '\t(tags "xiao esp32s3 seeed module")',
        "\t(attr smd)",
        '\t(property "Reference" "U**" (at 0 -12 0) (layer "F.SilkS")'
        " (effects (font (size 1 1) (thickness 0.15))))",
        f'\t(property "Value" "{NAME}" (at 0 12 0) (layer "F.Fab")'
        " (effects (font (size 1 1) (thickness 0.15))))",
    ]
    # Courtyard and fabrication outline are never printed, so they may cross pads.
    out += rectangle(BODY_W / 2 + 0.25, BODY_H / 2 + 0.25, "F.CrtYd", 0.05)
    out += rectangle(BODY_W / 2, BODY_H / 2, "F.Fab", 0.1)
    out += silkscreen()

    for col, names in ((-X, LEFT), (X, RIGHT)):
        for i, name in enumerate(names):
            y = round(Y0 + i * PITCH, 3)
            out.append(
                f'\t(pad "{name}" smd roundrect (at {col} {y})'
                f' (size {PAD_W} {PAD_H}) (layers "F.Cu" "F.Mask" "F.Paste")'
                " (roundrect_rratio 0.25))"
            )
    out.append(")")
    return "\n".join(out) + "\n"


def main() -> None:
    LIB.mkdir(exist_ok=True)
    path = LIB / f"{NAME}.kicad_mod"
    path.write_text(build())

    # Read it back with KiCad's own loader: a footprint this file cannot parse is worse
    # than no footprint, because the failure would only surface when the board is opened.
    fp = pcbnew.FootprintLoad(str(LIB), NAME)
    if fp is None:
        sys.exit(f"make-xiao-footprint: KiCad cannot load the {path.name} just written")
    pads = {p.GetNumber() for p in fp.Pads()}
    expected = set(LEFT) | set(RIGHT)
    if pads != expected:
        sys.exit(f"make-xiao-footprint: pads {sorted(pads ^ expected)} unexpected")
    print(f"wrote {LIB.name}/{path.name} ({len(pads)} named pads, verified by KiCad)")


if __name__ == "__main__":
    main()
