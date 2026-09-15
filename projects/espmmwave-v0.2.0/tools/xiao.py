"""The XIAO ESP32-S3, defined once.

KiCad ships neither a symbol nor a XIAO-labelled footprint for this module, so this
project makes both — and they are generated from the single pin list below rather than
written out twice. A symbol and a footprint that disagree about pin names is a board
that passes every check and does not work, and it is exactly the drift that happens the
third time somebody edits one of the two files.

The names are Seeed's own, from the pin map for the whole XIAO family: D0..D10 plus the
three supply pads, viewed from the top with the USB connector at the top of the module.
"""

from __future__ import annotations

NAME = "XIAO_ESP32S3"
DESCRIPTION = (
    "Seeed XIAO ESP32-S3, castellated. Pads are NAMED (D0..D10 / 5V / GND / 3V3) "
    "rather than numbered, so a netlist cannot mis-map them to GPIOs."
)

# Top view, USB at the top: left column downwards, then right column downwards.
LEFT = ["D0", "D1", "D2", "D3", "D4", "D5", "D6"]
RIGHT = ["5V", "GND", "3V3", "D10", "D9", "D8", "D7"]

# Footprint geometry: 2x7 on a 2.54 mm pitch, columns 17 mm apart, 3 x 2 mm pads.
Y0, PITCH, X = -7.62, 2.54, 8.5
PAD_W, PAD_H = 3.0, 2.0
BODY_W, BODY_H = 17.5, 21.0

# Which pins are supplies rather than plain I/O. ERC uses this: a power input that no
# power output ever drives is a real error, and it is the sort a schematic drawn by
# hand quietly gets wrong.
POWER_IN = {"5V", "3V3"}
POWER_OUT: set[str] = set()
GROUND = {"GND"}


def electrical_type(pin: str) -> str:
    """The KiCad pin type for ERC."""
    if pin in GROUND or pin in POWER_IN:
        return "power_in"
    return "bidirectional"
