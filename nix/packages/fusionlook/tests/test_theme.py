"""The theme, checked against the FreeCAD it is meant to dress.

Two of these tests read the installed FreeCAD's own stylesheet directory, which
nix/checks/fusionlook.nix passes in as FREECAD_STYLESHEETS. They are the ones that
matter: a theme is a set of tokens with no schema, and a token FreeCAD.qss asks for
and this file does not define is not an error anywhere — the rule simply comes out
with `@GeneralBorderColor` where a colour should be, and the widget it styled goes
missing. Skipped rather than failed when the variable is unset, so plain `pytest`
still works outside the nix build.
"""

from __future__ import annotations

import os
import pathlib
import re
import xml.etree.ElementTree as ET

import pytest

from freecad.fusionlook import tokens

ADDON = pathlib.Path(tokens.__file__).resolve().parents[2]
PACK = ADDON / "Fusion Dark Blue"
THEME = PACK / "parameters" / "Fusion Dark Blue.yaml"
CONFIG = PACK / "Fusion Dark Blue.cfg"
PACKAGE = ADDON / "package.xml"

# Tokens whose value is not a colour. Everything else in the file has to resolve.
NOT_COLOURS = {
    "IconsLocationFolderName",
    "StylesheetIconsColor",
    "InputFieldBorderRadius",
    "ToolbarButtonsPadding",
}

# What FreeCAD supplies from user.cfg rather than from a theme file
# (StyleParameters::BuiltInParameterSource), as this pack leaves them: the first
# accent and the viewport background are written by its own .cfg, and the other two
# accents keep FreeCAD's stock #557bb6 because this theme references neither.
BUILT_IN = {
    "ThemeAccentColor1": "#2a9df4",
    "ThemeAccentColor2": "#557bb6",
    "ThemeAccentColor3": "#557bb6",
    "BackgroundColor": "#3f4348",
}

STYLESHEETS = os.environ.get("FREECAD_STYLESHEETS", "")
needs_freecad = pytest.mark.skipif(
    not STYLESHEETS, reason="FREECAD_STYLESHEETS is unset: no installed FreeCAD to read"
)


# encoding= on every read below is not decoration: these files are full of em
# dashes, and `read_text()` uses the *locale* encoding — under LANG=C it raises
# UnicodeDecodeError on the first line of the theme. FreeCAD hits the same wall from
# the other side, which is why init_gui decodes the file as UTF-8 explicitly.
@pytest.fixture(scope="module")
def theme() -> dict[str, str]:
    return dict(BUILT_IN) | tokens.parse(THEME.read_text(encoding="utf-8"))


def test_every_colour_token_resolves(theme: dict[str, str]) -> None:
    for name in tokens.parse(THEME.read_text(encoding="utf-8")):
        if name in NOT_COLOURS:
            continue
        tokens.resolve(name, theme)  # raises Unresolved if it does not


@needs_freecad
def test_the_theme_defines_every_token_the_stylesheet_asks_for(
    theme: dict[str, str],
) -> None:
    referenced = set()
    for sheet in ("FreeCAD.qss", "defaults.qss"):
        text = (pathlib.Path(STYLESHEETS) / sheet).read_text(encoding="utf-8")
        referenced |= set(re.findall(r"@([A-Za-z][A-Za-z0-9_]*)", text))

    assert referenced, "read no tokens out of FreeCAD.qss: has the syntax changed?"
    missing = sorted(name for name in referenced if name not in theme)
    assert not missing, f"FreeCAD.qss uses tokens this theme does not define: {missing}"


@needs_freecad
def test_the_theme_covers_what_freecad_dark_covers(theme: dict[str, str]) -> None:
    """A token FreeCAD's own theme defines and this one does not is a rule that
    falls back to nothing the moment upstream starts using it."""
    shipped = tokens.parse(
        (pathlib.Path(STYLESHEETS) / "parameters" / "FreeCAD Dark.yaml").read_text(
            encoding="utf-8"
        )
    )
    missing = sorted(name for name in shipped if name not in theme)
    assert not missing, f"FreeCAD Dark defines these and this theme does not: {missing}"


def test_the_palette_separates_by_luminance(theme: dict[str, str]) -> None:
    """The look this theme is after is planes at different brightnesses, so the
    ordering of those brightnesses is the design, not a detail."""
    strip = tokens.resolve("FusionStripColor", theme)
    surface = tokens.resolve("PrimaryColor", theme)
    canvas = tokens.resolve("FusionCanvasColor", theme)
    button = tokens.resolve("ButtonTopBackgroundColor", theme)
    border = tokens.resolve("GeneralBorderColor", theme)

    assert border.luminance < strip.luminance < surface.luminance < canvas.luminance
    assert surface.luminance < button.luminance
    # The strip has to read as a different plane from the toolbar without reading
    # as a black bar: under 1.1 the step disappears, over 1.6 it is a slab.
    assert 1.1 < tokens.contrast(strip, surface) < 1.6


def test_text_and_accent_are_readable_on_every_surface_they_land_on(
    theme: dict[str, str],
) -> None:
    text = tokens.resolve("TextForegroundColor", theme)
    muted = tokens.resolve("FusionTextMutedColor", theme)
    accent = tokens.resolve("AccentColor", theme)

    for name in ("PrimaryColor", "FusionStripColor", "MenuBackgroundColor"):
        surface = tokens.resolve(name, theme)
        assert tokens.contrast(text, surface) >= 7.0, name  # WCAG AAA body text
        assert tokens.contrast(muted, surface) >= 3.0, name  # AA for large text
        # The accent is only ever a marker or a large fill, never body text.
        assert tokens.contrast(accent, surface) >= 3.0, name


def test_the_pack_names_itself_the_same_thing_everywhere() -> None:
    """FreeCAD joins these by string: the .cfg names the theme, the theme names
    the parameter file, and the Addon Manager finds the pack by the directory the
    package.xml names. One rename in one place and the theme silently does not
    load — Gui/Application.cpp falls back to `qss:parameters/Classic.yaml`."""
    name = PACK.name
    assert THEME.name == f"{name}.yaml"
    assert CONFIG.name == f"{name}.cfg"

    packs = [
        item.findtext("{*}name")
        for item in ET.parse(PACKAGE).getroot().findall(".//{*}preferencepack")
    ]
    assert packs == [name]

    settings = ET.parse(CONFIG).getroot()
    values = {entry.get("Name"): entry.text for entry in settings.iter("FCText")}
    assert values["Theme"] == name
    # The stock stylesheet, not a fork of it.
    assert values["StyleSheet"] == "FreeCAD.qss"


def test_the_pack_shows_up_in_the_theme_selector() -> None:
    """DlgSettingsGeneral::loadThemes lists a preference pack only when its
    metadata type is exactly "Theme"."""
    packs = ET.parse(PACKAGE).getroot().findall(".//{*}preferencepack")
    assert [pack.findtext("{*}type") for pack in packs] == ["Theme"]


def test_the_config_writes_the_colours_it_claims_to() -> None:
    """FCUInt colours are packed 0xRRGGBBAA, which is unreadable by eye — and a
    digit out lands somewhere plausible rather than somewhere obviously wrong."""
    packed = {
        entry.get("Name"): int(entry.get("Value", "0"))
        for entry in ET.parse(CONFIG).getroot().iter("FCUInt")
    }
    expected = {
        "ThemeAccentColor1": BUILT_IN["ThemeAccentColor1"],
        "BackgroundColor": BUILT_IN["BackgroundColor"],
        "HighlightColor": "#74c0fc",
        "SelectionColor": "#69db7c",
    }

    for name, colour in expected.items():
        assert f"#{(packed[name] >> 8) & 0xFFFFFF:06x}" == colour, name
        assert packed[name] & 0xFF == 0xFF, f"{name} is not fully opaque"


def test_the_accent_in_the_config_is_the_accent_in_the_theme(
    theme: dict[str, str],
) -> None:
    # Two files, one colour: the .cfg feeds the preferences page's accent picker
    # and the .yaml feeds the stylesheet.
    assert str(tokens.resolve("AccentColor", theme)) == BUILT_IN["ThemeAccentColor1"]


def test_selection_and_highlight_stand_out_against_this_theme_s_canvas() -> None:
    """FreeCAD's defaults are tuned for a much darker viewport than this one."""
    canvas = tokens.parse_colour(BUILT_IN["BackgroundColor"])

    for colour in ("#74c0fc", "#69db7c"):
        assert tokens.contrast(tokens.parse_colour(colour), canvas) >= 3.0, colour
