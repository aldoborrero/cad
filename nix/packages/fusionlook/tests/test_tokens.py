"""The colour arithmetic, against a real QColor.

The table below is not hand-written: `tools/qcolor_reference.py` prints it from
PySide6 inside FreeCAD's own interpreter, and it is pasted here so that the check
can run without Qt. Every row is `(colour, amount, lighten, darken)` — the two
functions a theme file can call, at the amounts this repo's theme actually uses
plus the extremes FreeCAD Dark uses.

It earned its keep immediately: 77 of the first 272 comparisons were off by one,
because QColor::red() narrows 16 bits to 8 with a rounding divide by 257 and not
with `>> 8`.
"""

from __future__ import annotations

import pytest

from freecad.fusionlook import tokens

QCOLOR = [
    ("#2a2e34", 10, "#2e3339", "#262a2f"),
    ("#2a2e34", 12, "#2f343a", "#25292e"),
    ("#2a2e34", 20, "#32373e", "#23262b"),
    ("#2a2e34", 22, "#33383f", "#22262b"),
    ("#2a2e34", 34, "#383e46", "#1f2227"),
    ("#2a2e34", 35, "#393e46", "#1f2227"),
    ("#2a2e34", 40, "#3b4049", "#1e2125"),
    ("#2a2e34", 48, "#3e444d", "#1c1f23"),
    ("#2a2e34", 50, "#3f454e", "#1c1f23"),
    ("#2a2e34", 55, "#414751", "#1b1e22"),
    ("#2a2e34", 70, "#474e58", "#191b1f"),
    ("#2a2e34", 90, "#505763", "#16181b"),
    ("#2a2e34", 120, "#5c6572", "#131518"),
    ("#2a2e34", 200, "#7e8a9c", "#0e0f11"),
    ("#2a2e34", 260, "#97a6bb", "#0c0d0e"),
    ("#2a2e34", 300, "#a8b8d0", "#0a0b0d"),
    ("#2a2e34", 5890, "#ffffff", "#010101"),
    ("#1e2126", 10, "#21242a", "#1b1e23"),
    ("#1e2126", 12, "#22252b", "#1b1d22"),
    ("#1e2126", 20, "#24282e", "#191b20"),
    ("#1e2126", 22, "#25282e", "#191b1f"),
    ("#1e2126", 34, "#282c33", "#16191c"),
    ("#1e2126", 35, "#282d33", "#16181c"),
    ("#1e2126", 40, "#2a2e35", "#15181b"),
    ("#1e2126", 48, "#2c3138", "#14161a"),
    ("#1e2126", 50, "#2d3139", "#141619"),
    ("#1e2126", 55, "#2e333b", "#131519"),
    ("#1e2126", 70, "#333841", "#121316"),
    ("#1e2126", 90, "#393f48", "#101114"),
    ("#1e2126", 120, "#424954", "#0e0f11"),
    ("#1e2126", 200, "#5a6372", "#0a0b0d"),
    ("#1e2126", 260, "#6c7789", "#08090b"),
    ("#1e2126", 300, "#788498", "#070809"),
    ("#1e2126", 5890, "#ffffff", "#010101"),
    ("#2a9df4", 10, "#39aaff", "#268fde"),
    ("#2a9df4", 12, "#3eacff", "#268cda"),
    ("#2a9df4", 20, "#52b4ff", "#2383cb"),
    ("#2a9df4", 22, "#57b6ff", "#2281c8"),
    ("#2a9df4", 34, "#74c3ff", "#1f75b6"),
    ("#2a9df4", 35, "#76c4ff", "#1f74b5"),
    ("#2a9df4", 40, "#82c9ff", "#1e70ae"),
    ("#2a9df4", 48, "#96d2ff", "#1c6aa5"),
    ("#2a9df4", 50, "#9bd4ff", "#1c69a3"),
    ("#2a9df4", 55, "#a7d9ff", "#1b659d"),
    ("#2a9df4", 70, "#cce9ff", "#195c90"),
    ("#2a9df4", 90, "#fcfeff", "#165380"),
    ("#2a9df4", 120, "#ffffff", "#13476f"),
    ("#2a9df4", 200, "#ffffff", "#0e3451"),
    ("#2a9df4", 260, "#ffffff", "#0c2c44"),
    ("#2a9df4", 300, "#ffffff", "#0b273d"),
    ("#2a9df4", 5890, "#ffffff", "#010304"),
    ("#e8eaed", 10, "#ffffff", "#d3d5d7"),
    ("#e8eaed", 12, "#ffffff", "#cfd1d4"),
    ("#e8eaed", 20, "#ffffff", "#c1c3c5"),
    ("#e8eaed", 22, "#ffffff", "#bec0c2"),
    ("#e8eaed", 34, "#ffffff", "#adafb1"),
    ("#e8eaed", 35, "#ffffff", "#acadb0"),
    ("#e8eaed", 40, "#ffffff", "#a6a7a9"),
    ("#e8eaed", 48, "#ffffff", "#9d9ea0"),
    ("#e8eaed", 50, "#ffffff", "#9b9c9e"),
    ("#e8eaed", 55, "#ffffff", "#969799"),
    ("#e8eaed", 70, "#ffffff", "#888a8b"),
    ("#e8eaed", 90, "#ffffff", "#7a7b7d"),
    ("#e8eaed", 120, "#ffffff", "#696a6c"),
    ("#e8eaed", 200, "#ffffff", "#4d4e4f"),
    ("#e8eaed", 260, "#ffffff", "#404142"),
    ("#e8eaed", 300, "#ffffff", "#3a3a3b"),
    ("#e8eaed", 5890, "#ffffff", "#040404"),
    ("#191919", 10, "#1b1b1b", "#171717"),
    ("#191919", 12, "#1c1c1c", "#161616"),
    ("#191919", 20, "#1e1e1e", "#151515"),
    ("#191919", 22, "#1e1e1e", "#141414"),
    ("#191919", 34, "#212121", "#131313"),
    ("#191919", 35, "#222222", "#131313"),
    ("#191919", 40, "#232323", "#121212"),
    ("#191919", 48, "#252525", "#111111"),
    ("#191919", 50, "#252525", "#111111"),
    ("#191919", 55, "#272727", "#101010"),
    ("#191919", 70, "#2a2a2a", "#0f0f0f"),
    ("#191919", 90, "#2f2f2f", "#0d0d0d"),
    ("#191919", 120, "#373737", "#0b0b0b"),
    ("#191919", 200, "#4b4b4b", "#080808"),
    ("#191919", 260, "#5a5a5a", "#070707"),
    ("#191919", 300, "#646464", "#060606"),
    ("#191919", 5890, "#ffffff", "#000000"),
    ("#ffffff", 10, "#ffffff", "#e8e8e8"),
    ("#ffffff", 12, "#ffffff", "#e4e4e4"),
    ("#ffffff", 20, "#ffffff", "#d4d4d4"),
    ("#ffffff", 22, "#ffffff", "#d1d1d1"),
    ("#ffffff", 34, "#ffffff", "#bebebe"),
    ("#ffffff", 35, "#ffffff", "#bdbdbd"),
    ("#ffffff", 40, "#ffffff", "#b6b6b6"),
    ("#ffffff", 48, "#ffffff", "#acacac"),
    ("#ffffff", 50, "#ffffff", "#aaaaaa"),
    ("#ffffff", 55, "#ffffff", "#a5a5a5"),
    ("#ffffff", 70, "#ffffff", "#969696"),
    ("#ffffff", 90, "#ffffff", "#868686"),
    ("#ffffff", 120, "#ffffff", "#747474"),
    ("#ffffff", 200, "#ffffff", "#555555"),
    ("#ffffff", 260, "#ffffff", "#474747"),
    ("#ffffff", 300, "#ffffff", "#404040"),
    ("#ffffff", 5890, "#ffffff", "#040404"),
    ("#000000", 10, "#000000", "#000000"),
    ("#000000", 12, "#000000", "#000000"),
    ("#000000", 20, "#000000", "#000000"),
    ("#000000", 22, "#000000", "#000000"),
    ("#000000", 34, "#000000", "#000000"),
    ("#000000", 35, "#000000", "#000000"),
    ("#000000", 40, "#000000", "#000000"),
    ("#000000", 48, "#000000", "#000000"),
    ("#000000", 50, "#000000", "#000000"),
    ("#000000", 55, "#000000", "#000000"),
    ("#000000", 70, "#000000", "#000000"),
    ("#000000", 90, "#000000", "#000000"),
    ("#000000", 120, "#000000", "#000000"),
    ("#000000", 200, "#000000", "#000000"),
    ("#000000", 260, "#000000", "#000000"),
    ("#000000", 300, "#000000", "#000000"),
    ("#000000", 5890, "#000000", "#000000"),
    ("#7f0000", 10, "#8c0000", "#730000"),
    ("#7f0000", 12, "#8e0000", "#710000"),
    ("#7f0000", 20, "#980000", "#6a0000"),
    ("#7f0000", 22, "#9b0000", "#680000"),
    ("#7f0000", 34, "#aa0000", "#5f0000"),
    ("#7f0000", 35, "#ab0000", "#5e0000"),
    ("#7f0000", 40, "#b20000", "#5b0000"),
    ("#7f0000", 48, "#bc0000", "#560000"),
    ("#7f0000", 50, "#be0000", "#550000"),
    ("#7f0000", 55, "#c50000", "#520000"),
    ("#7f0000", 70, "#d80000", "#4b0000"),
    ("#7f0000", 90, "#f10000", "#430000"),
    ("#7f0000", 120, "#ff1818", "#3a0000"),
    ("#7f0000", 200, "#ff7e7e", "#2a0000"),
    ("#7f0000", 260, "#ffcaca", "#230000"),
    ("#7f0000", 300, "#fffdfd", "#200000"),
    ("#7f0000", 5890, "#ffffff", "#020000"),
]


@pytest.mark.parametrize(("colour", "amount", "lighter", "darker"), QCOLOR)
def test_the_colour_functions_agree_with_qcolor(
    colour: str, amount: int, lighter: str, darker: str
) -> None:
    base = tokens.parse_colour(colour)
    assert str(tokens.lighter(base, 100 + amount)) == lighter
    assert str(tokens.darker(base, 100 + amount)) == darker


def test_a_colour_reads_in_both_of_the_forms_a_theme_may_use() -> None:
    assert tokens.parse_colour("#2a9df4") == tokens.Colour(0x2A, 0x9D, 0xF4)
    assert tokens.parse_colour("#abc") == tokens.parse_colour("#aabbcc")
    assert tokens.parse_colour("  #FFF  ") == tokens.Colour(255, 255, 255)

    for bad in ("2a9df4", "#12345", "rgb(1,2,3)", ""):
        with pytest.raises(tokens.Unresolved):
            tokens.parse_colour(bad)


def test_blend_walks_from_one_colour_to_the_other() -> None:
    black = tokens.Colour(0, 0, 0)
    white = tokens.Colour(255, 255, 255)

    assert tokens.blend(black, white, 0) == black
    assert tokens.blend(black, white, 100) == white
    # 127.5 rounded away from zero, the way Base::Color lands back on 8 bits.
    assert tokens.blend(black, white, 50) == tokens.Colour(128, 128, 128)


def test_a_reference_is_followed_to_whatever_ends_it() -> None:
    theme = {
        "PrimaryColor": "#2a2e34",
        "Surface": "@PrimaryColor",
        "Panel": "@Surface",
        "Border": "darken(@Panel, 35)",
        "Tinted": "blend(@PrimaryColor, #2a9df4, 50)",
        "Nested": "lighten(darken(@PrimaryColor, 35), 35)",
    }

    assert str(tokens.resolve("Panel", theme)) == "#2a2e34"
    assert str(tokens.resolve("Border", theme)) == "#1f2227"
    assert str(tokens.resolve("Tinted", theme)) == "#2a6694"
    assert str(tokens.resolve("Nested", theme)) == "#2a2e35"


def test_a_token_that_cannot_be_resolved_says_so_rather_than_guessing() -> None:
    # Anything the addon cannot resolve falls back to a literal in stylesheet.py,
    # so these have to raise rather than return black.
    theme = {
        "Missing": "@NotDefinedAnywhere",
        "Circular": "@Circular",
        "Mutual": "@Other",
        "Other": "@Mutual",
        "Unknown": "rotate(@Missing, 20)",
        "Wrong": "darken(#2a2e34)",
        "NotANumber": "darken(#2a2e34, blue)",
        "Length": "3px",
    }

    for name in theme:
        with pytest.raises(tokens.Unresolved):
            tokens.resolve(name, theme)


def test_the_four_built_in_parameters_resolve_like_any_other() -> None:
    # FreeCAD Dark's accent is "@ThemeAccentColor1", which lives in user.cfg
    # rather than in the theme file; init_gui reads it and merges it in.
    theme = {"AccentColor": "@ThemeAccentColor1", "ThemeAccentColor1": "#4aa5ff"}

    assert str(tokens.resolve("AccentColor", theme)) == "#4aa5ff"


def test_a_parameter_file_reads_as_a_flat_map_of_strings() -> None:
    parsed = tokens.parse(
        'PrimaryColor: "#2a2e34"\n'
        "InputFieldBorderRadius: 3px\n"
        "Padding: 2\n"
        "Nested:\n  not: scalar\n"
    )

    assert parsed["PrimaryColor"] == "#2a2e34"
    assert parsed["InputFieldBorderRadius"] == "3px"
    assert parsed["Padding"] == "2"
    # FreeCAD's YAML::Node::as<std::string> would throw on that one; dropping it
    # keeps a stranger's theme from costing us the tokens we can read.
    assert "Nested" not in parsed


def test_contrast_is_the_wcag_ratio() -> None:
    black = tokens.Colour(0, 0, 0)
    white = tokens.Colour(255, 255, 255)

    assert tokens.contrast(black, white) == pytest.approx(21.0)
    assert tokens.contrast(white, black) == pytest.approx(21.0)
    assert tokens.contrast(white, white) == pytest.approx(1.0)
