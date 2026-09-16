"""Build the schematic symbol for the XIAO, from the same pin list as the footprint.

KiCad ships dev-board symbols for Arduino, Pico and Adafruit but none for Seeed, so this
one is the project's own. It is generated rather than drawn because the pin names have to
agree with `espmmwave.pretty/XIAO_ESP32S3.kicad_mod` exactly: a symbol pin the footprint
has no pad for is a net that goes nowhere, and KiCad reports it only when the netlist is
pushed to the board — long after the schematic looked right. Both come out of xiao.py.

Pins carry electrical types so ERC can do its job: 5V, 3V3 and GND are power inputs, the
rest bidirectional. That is what makes "this rail is driven by nothing" an error rather
than a thing to notice by eye.

Run: make-xiao-symbol   (from projects/espmmwave-v0.2.0, with direnv active)
"""

from __future__ import annotations

import pathlib
import sys

from xiao import DESCRIPTION, LEFT, NAME, RIGHT, electrical_type

HERE = pathlib.Path(__file__).resolve().parent
LIB = HERE.parent / "kicad" / "espmmwave.kicad_sym"

# What KiCad 10's symbol editor writes; checked against the stock libraries rather than
# copied from an older file.
VERSION = "20251024"

PITCH = 2.54  # schematic grid; nothing to do with the footprint's pad pitch
PIN_LEN = 3.81
HALF_W = 7.62  # body half-width, so pins start clear of the name text


def pin(name: str, x: float, y: float, angle: int) -> list[str]:
    return [
        f"\t\t\t(pin {electrical_type(name)} line",
        f"\t\t\t\t(at {x} {y} {angle})",
        f"\t\t\t\t(length {PIN_LEN})",
        f'\t\t\t\t(name "{name}" (effects (font (size 1.27 1.27))))',
        # Number and name are the same string on purpose: this module's pads are named,
        # so "pin 4" is meaningless and "D3" is what both halves agree on.
        f'\t\t\t\t(number "{name}" (effects (font (size 1.27 1.27))))',
        "\t\t\t)",
    ]


def build() -> str:
    rows = max(len(LEFT), len(RIGHT))
    half_h = (rows - 1) * PITCH / 2 + PITCH

    out = [
        "(kicad_symbol_lib",
        f"\t(version {VERSION})",
        '\t(generator "espmmwave")',
        '\t(generator_version "10.0")',
        f'\t(symbol "{NAME}"',
        "\t\t(pin_names (offset 0.508))",
        "\t\t(exclude_from_sim no)",
        "\t\t(in_bom yes)",
        "\t\t(on_board yes)",
        f'\t\t(property "Reference" "U" (at -7.62 {half_h + 1.27} 0)'
        " (effects (font (size 1.27 1.27)) (justify left)))",
        f'\t\t(property "Value" "{NAME}" (at -7.62 {-half_h - 1.27} 0)'
        " (effects (font (size 1.27 1.27)) (justify left)))",
        f'\t\t(property "Footprint" "espmmwave:{NAME}" (at 0 0 0)'
        " (effects (font (size 1.27 1.27)) (hide yes)))",
        '\t\t(property "Datasheet" "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"'
        " (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))",
        f'\t\t(property "Description" "{DESCRIPTION}" (at 0 0 0)'
        " (effects (font (size 1.27 1.27)) (hide yes)))",
        f'\t\t(symbol "{NAME}_0_1"',
        f"\t\t\t(rectangle (start {-HALF_W} {half_h}) (end {HALF_W} {-half_h})",
        "\t\t\t\t(stroke (width 0.254) (type default))",
        "\t\t\t\t(fill (type background))",
        "\t\t\t)",
        "\t\t)",
        f'\t\t(symbol "{NAME}_1_1"',
    ]

    top = (rows - 1) * PITCH / 2
    for i, name in enumerate(LEFT):
        out += pin(name, -HALF_W - PIN_LEN, top - i * PITCH, 0)
    for i, name in enumerate(RIGHT):
        out += pin(name, HALF_W + PIN_LEN, top - i * PITCH, 180)

    out += ["\t\t)", "\t)", ")"]
    return "\n".join(out) + "\n"


def main() -> None:
    LIB.write_text(build())

    # Verify what was written: a library KiCad cannot parse is worse than none, because
    # the failure surfaces when the schematic is opened rather than here.
    text = LIB.read_text()
    for name in (*LEFT, *RIGHT):
        if f'(number "{name}"' not in text:
            sys.exit(f"make-xiao-symbol: pin {name} missing from the written library")
    if text.count("(pin ") != len(LEFT) + len(RIGHT):
        sys.exit("make-xiao-symbol: wrong pin count")
    print(f"wrote {LIB.name} ({len(LEFT) + len(RIGHT)} named pins)")


if __name__ == "__main__":
    main()
