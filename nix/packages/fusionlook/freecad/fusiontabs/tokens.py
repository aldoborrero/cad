"""Resolving a FreeCAD 1.1 theme's style parameters without FreeCAD.

FreeCAD substitutes `@Token`s into `FreeCAD.qss` in C++ (`Gui/StyleParameters/`)
and exposes none of it to Python in 1.1.1: the manager is handed to
`Base::registerServiceImplementation` and stops there. FusionTabs needs the same
colours for the stylesheets it puts on individual widgets, so this module
re-implements the part of `Gui/StyleParameters/Parser.cpp` it depends on —
`@references` and the three functions `lighten`, `darken` and `blend`.

The colour arithmetic is Qt's rather than an approximation of it:
`lighten(c, n)` is `QColor::lighter(100 + n)` and `darken(c, n)` is
`QColor::darker(100 + n)`, both of which scale the *value* channel of a 16-bit
HSV colour and quantise the hue to a hundredth of a degree on the way back.
`tests/test_tokens.py` pins the results against values measured from a real
`QColor`; `tools/qcolor_reference.py` is what measures them.

Nothing here imports FreeCAD or Qt, which is the point: it runs under plain
pytest, and `init_gui.py` is the only module that needs a GUI.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

import yaml

USHRT_MAX = 0xFFFF


class Unresolved(Exception):
    """A token references something no source defines, or does not parse."""


@dataclass(frozen=True)
class Colour:
    """An 8-bit RGB colour, the only kind a theme file carries."""

    red: int
    green: int
    blue: int

    def __str__(self) -> str:
        return f"#{self.red:02x}{self.green:02x}{self.blue:02x}"

    @property
    def luminance(self) -> float:
        """Relative luminance, WCAG 2.x. Used by the tests to assert contrast
        rather than eyeball it."""
        channels = []
        for value in (self.red, self.green, self.blue):
            fraction = value / 255
            channels.append(
                fraction / 12.92
                if fraction <= 0.04045
                else ((fraction + 0.055) / 1.055) ** 2.4
            )
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(first: Colour, second: Colour) -> float:
    """WCAG contrast ratio, 1.0 (identical) to 21.0 (black on white)."""
    lighter_, darker_ = sorted((first.luminance, second.luminance), reverse=True)
    return (lighter_ + 0.05) / (darker_ + 0.05)


def parse_colour(text: str) -> Colour:
    """`#rgb` or `#rrggbb`, the two forms the theme files use."""
    match = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", text.strip())
    if match is None:
        raise Unresolved(f"not a colour: {text!r}")

    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(digit * 2 for digit in digits)
    return Colour(int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))


def _round(value: float) -> int:
    """Qt's qRound: half away from zero, not Python's half to even."""
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)


def _to_hsv(colour: Colour) -> tuple[int, int, int]:
    """Qt's QColor::toHsv, in the 16-bit units QColor stores.

    Hue comes back in hundredths of a degree, or USHRT_MAX for an achromatic
    colour, which is what QColor uses as its "no hue" marker.
    """
    red, green, blue = (
        colour.red * 0x101 / USHRT_MAX,
        colour.green * 0x101 / USHRT_MAX,
        colour.blue * 0x101 / USHRT_MAX,
    )
    largest = max(red, green, blue)
    smallest = min(red, green, blue)
    delta = largest - smallest

    value = _round(largest * USHRT_MAX)
    if delta == 0.0 or largest == 0.0:
        return USHRT_MAX, 0, value

    saturation = _round(delta / largest * USHRT_MAX)
    if red == largest:
        hue = (green - blue) / delta
    elif green == largest:
        hue = 2.0 + (blue - red) / delta
    else:
        hue = 4.0 + (red - green) / delta

    hue *= 60.0
    if hue < 0.0:
        hue += 360.0
    return _round(hue * 100), saturation, value


def _div_257(value: int) -> int:
    """Qt's qt_div_257: 16 bits back down to 8, rounded rather than truncated.

    Worth spelling out, because `>> 8` looks like the same thing and is not. It is
    low by one for most inputs, and QColor::red() uses this — measuring against a
    real QColor is what caught it, in 77 of 272 comparisons.
    """
    value += 128
    return (value - (value >> 8)) >> 8


def _from_hsv(hue: int, saturation: int, value: int) -> Colour:
    """Qt's QColor::toRgb for an HSV colour, ending in the narrowing that
    QColor::red() applies to get back to eight bits."""
    if saturation == 0 or hue == USHRT_MAX:
        channel = _div_257(value)
        return Colour(channel, channel, channel)

    sectors = hue / 6000.0
    saturation_f = saturation / USHRT_MAX
    value_f = value / USHRT_MAX

    sector = int(sectors)
    offset = sectors - sector
    low = value_f * (1.0 - saturation_f)

    if sector & 1:
        falling = value_f * (1.0 - saturation_f * offset)
        triples = {1: (falling, value_f, low), 3: (low, falling, value_f)}
        red, green, blue = triples.get(sector, (value_f, low, falling))
    else:
        rising = value_f * (1.0 - saturation_f * (1.0 - offset))
        triples = {0: (value_f, rising, low), 2: (low, value_f, rising)}
        red, green, blue = triples.get(sector, (rising, low, value_f))

    return Colour(
        _div_257(_round(red * USHRT_MAX)),
        _div_257(_round(green * USHRT_MAX)),
        _div_257(_round(blue * USHRT_MAX)),
    )


def lighter(colour: Colour, factor: int) -> Colour:
    """QColor::lighter. Past the point where the value channel saturates it
    takes the excess out of saturation instead, which is how `lighten(@C, 5890)`
    in FreeCAD Dark reaches white rather than a bright version of the hue."""
    if factor <= 0:
        return colour
    if factor < 100:
        return darker(colour, 10000 // factor)

    hue, saturation, value = _to_hsv(colour)
    value = factor * value // 100
    if value > USHRT_MAX:
        saturation = max(0, saturation - (value - USHRT_MAX))
        value = USHRT_MAX
    return _from_hsv(hue, saturation, value)


def darker(colour: Colour, factor: int) -> Colour:
    """QColor::darker."""
    if factor <= 0:
        return colour
    if factor < 100:
        return lighter(colour, 10000 // factor)

    hue, saturation, value = _to_hsv(colour)
    return _from_hsv(hue, saturation, value * 100 // factor)


def blend(first: Colour, second: Colour, percent: float) -> Colour:
    """Per-channel mix, `percent` of `second` into `first`.

    Base::Color keeps its channels as floats, so the mix happens in float and
    lands back on eight bits once — matching FunctionCall::evaluate rather than
    rounding twice.
    """
    amount = percent / 100
    channels = [
        (1 - amount) * getattr(first, name) / 255 + amount * getattr(second, name) / 255
        for name in ("red", "green", "blue")
    ]
    return Colour(*(_round(channel * 255) for channel in channels))


_FUNCTION = re.compile(r"^(lighten|darken|blend)\s*\((.*)\)$", re.DOTALL)


def _split_arguments(text: str) -> list[str]:
    """Split on commas that are not inside a nested call."""
    arguments: list[str] = []
    depth = 0
    current = ""
    for character in text:
        if character == "," and depth == 0:
            arguments.append(current)
            current = ""
            continue
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        current += character
    arguments.append(current)
    return [argument.strip() for argument in arguments]


def resolve(
    name: str, tokens: dict[str, str], seen: frozenset[str] = frozenset()
) -> Colour:
    """The colour a token names, following references and evaluating functions.

    `tokens` is every parameter FreeCAD would see: the theme file, plus the four
    built-ins it reads out of user.cfg instead (`BackgroundColor` and
    `ThemeAccentColor1..3` — see StyleParameters::BuiltInParameterSource).
    """
    if name in seen:
        raise Unresolved(f"{name} refers to itself")
    if name not in tokens:
        raise Unresolved(f"no token called {name}")
    return _evaluate(tokens[name], tokens, seen | {name})


def _evaluate(expression: str, tokens: dict[str, str], seen: frozenset[str]) -> Colour:
    expression = expression.strip()

    if expression.startswith("@"):
        return resolve(expression[1:], tokens, seen)

    if expression.startswith("#"):
        return parse_colour(expression)

    match = _FUNCTION.match(expression)
    if match is None:
        raise Unresolved(f"cannot evaluate {expression!r}")

    function, rest = match.group(1), match.group(2)
    arguments = _split_arguments(rest)

    try:
        if function in ("lighten", "darken"):
            if len(arguments) != 2:
                raise Unresolved(f"{function} takes 2 arguments, got {len(arguments)}")
            colour = _evaluate(arguments[0], tokens, seen)
            amount = 100 + int(float(arguments[1]))
            if function == "lighten":
                return lighter(colour, amount)
            return darker(colour, amount)

        if len(arguments) != 3:
            raise Unresolved(f"blend takes 3 arguments, got {len(arguments)}")
        return blend(
            _evaluate(arguments[0], tokens, seen),
            _evaluate(arguments[1], tokens, seen),
            float(arguments[2]),
        )
    except ValueError as exc:  # a non-numeric amount
        raise Unresolved(f"cannot evaluate {expression!r}: {exc}") from exc


def parse(text: str) -> dict[str, str]:
    """A theme's parameter file as a flat name -> expression map.

    YAML::Load and `as<std::string>()` is what FreeCAD does, so a value that is
    not a scalar is an error there too — it is dropped here rather than raising,
    because one unreadable token in somebody else's theme is not a reason for
    the addon to give up on the rest.
    """
    loaded: Any = yaml.safe_load(text) or {}
    if not isinstance(loaded, dict):
        raise Unresolved("a theme parameter file must be a mapping")
    return {
        str(name): str(value)
        for name, value in loaded.items()
        if isinstance(value, (str, int, float))
    }
