"""The two scoped stylesheets, and the selectors they are written in.

These are the tests that stand in for a GUI. Nothing here can prove that Qt draws
what was asked for, but it can prove that the sheet says what the FreeCAD source
says it must — in particular that the workbench selector is addressed as a
descendant and not as `QTabBar#WbTabBar`, which is the obvious spelling and matches
nothing, because the object name is on the container widget.
"""

from __future__ import annotations

import re

import pytest

from freecad.fusiontabs import stylesheet, tokens

SLOTS = ("strip", "surface", "accent", "text", "muted", "hover")


def theme(**overrides: str) -> dict[str, str]:
    return {
        "PrimaryColor": "#2a2e34",
        "FusionStripColor": "#1e2126",
        "AccentColor": "#2a9df4",
        "TextForegroundColor": "#e8eaed",
        "FusionTextMutedColor": "#969799",
        "GeneralBackgroundHoverColor": "#383e46",
        **overrides,
    }


def test_the_palette_comes_out_of_the_theme() -> None:
    colours = stylesheet.palette(theme())

    assert str(colours.strip) == "#1e2126"
    assert str(colours.surface) == "#2a2e34"
    assert str(colours.accent) == "#2a9df4"
    assert str(colours.hover) == "#383e46"


def test_each_slot_falls_back_on_its_own() -> None:
    """A theme that defines a primary colour and nothing else should still get its
    primary colour used, rather than the whole palette reverting to literals."""
    colours = stylesheet.palette({"PrimaryColor": "#101010"})

    assert str(colours.surface) == "#101010"
    assert str(colours.strip) == stylesheet.SOURCES["strip"][1]
    assert str(colours.accent) == stylesheet.SOURCES["accent"][1]


def test_a_theme_written_before_this_addon_still_gets_a_palette() -> None:
    """FreeCAD Dark, near enough: no Fusion tokens at all, and an accent that is a
    reference into user.cfg rather than a colour."""
    freecad_dark = {
        "PrimaryColor": "#191919",
        "PrimaryColorDarken5": "darken(@PrimaryColor,200)",
        "PrimaryColorLighten3": "lighten(@PrimaryColor,80)",
        "TabbarBackgroundColor": "@PrimaryColorDarken5",
        "GeneralBackgroundHoverColor": "@PrimaryColorLighten3",
        "TextForegroundColor": "#ffffff",
        "TextDisabledColor": "darken(@TextForegroundColor,120)",
        "AccentColor": "@ThemeAccentColor1",
        "ThemeAccentColor1": "#4aa5ff",
    }
    colours = stylesheet.palette(freecad_dark)

    assert str(colours.strip) == "#080808"
    assert str(colours.surface) == "#191919"
    assert str(colours.accent) == "#4aa5ff"
    assert str(colours.muted) == "#747474"


def test_a_broken_token_costs_only_that_slot() -> None:
    colours = stylesheet.palette(theme(AccentColor="@GoesNowhere"))

    assert str(colours.accent) == stylesheet.SOURCES["accent"][1]
    assert str(colours.surface) == "#2a2e34"


@pytest.mark.parametrize("sheet", [stylesheet.document_tabs, stylesheet.workbench_tabs])
def test_every_placeholder_is_filled_in(sheet: object) -> None:
    """QSS is full of braces of its own, so the check is for a `{slot}` rather than
    for a brace: a slot renamed in Palette and not in the template survives
    str.format only when it is spelled the same in both."""
    text = sheet(stylesheet.palette(theme()))  # type: ignore[operator]

    assert not re.findall(r"\{[a-z_]+\}", text)
    assert not re.search(r"#[0-9a-f]{7}", text), "a colour ran into its rule"
    assert text.count("#") >= 6, "the sheet should be written in colours"


def test_the_document_tabs_are_styled_for_either_edge() -> None:
    """The addon moves them to the top, but the styling has to survive the option
    being off — or a future FreeCAD refusing the move."""
    text = stylesheet.document_tabs(stylesheet.palette(theme()))

    assert "QTabBar#mdiAreaTabBar::tab:top:selected" in text
    assert "QTabBar#mdiAreaTabBar::tab:bottom:selected" in text
    # The accent marks the open document on whichever edge the tabs are on.
    for edge in ("top", "bottom"):
        rule = text.split(f"QTabBar#mdiAreaTabBar::tab:{edge}:selected")[1]
        assert "#2a9df4" in rule.split("}")[0]


def test_the_workbench_tabs_are_addressed_through_their_container() -> None:
    """WorkbenchTabWidget sets objectName "WbTabBar" on itself, not on the QTabBar
    it holds (Gui/WorkbenchSelector.cpp). `QTabBar#WbTabBar` selects nothing."""
    text = stylesheet.workbench_tabs(stylesheet.palette(theme()))

    assert "#WbTabBar QTabBar::tab" in text
    assert "QTabBar#WbTabBar" not in text


def test_the_selected_workbench_tab_is_text_and_an_underline() -> None:
    text = stylesheet.workbench_tabs(stylesheet.palette(theme()))
    selected = text.split("#WbTabBar QTabBar::tab:selected")[1].split("}")[0]

    assert "background-color: transparent" in selected
    assert "border-bottom: 2px solid #2a9df4" in selected
    assert "color: #e8eaed" in selected


@pytest.mark.parametrize(
    ("sheet", "tab_rule"),
    [
        (stylesheet.document_tabs, "QTabBar#mdiAreaTabBar::tab {"),
        (stylesheet.workbench_tabs, "#WbTabBar QTabBar::tab {"),
    ],
)
def test_the_tab_rule_names_what_the_stock_sheet_would_otherwise_paint(
    sheet: object, tab_rule: str
) -> None:
    """A property these sheets do not mention keeps FreeCAD.qss's value.

    Qt merges a widget's sheet with the application's; the widget's wins where both
    speak, and the application's stands where the widget's is silent. Measured on a
    real QTabBar, not read off the documentation: an application `min-width: 200px`
    the widget sheet says nothing about renders 200 px wide, and 96 px once the
    widget sheet names it, despite `QTabBar::tab:top` being the more specific
    selector of the two.

    The two properties below are the ones that were being painted through.
    FreeCAD.qss gives `QTabBar::tab:top` a 3 px top radius and
    `::tab:top:selected` a bold font, with the same pair mirrored for `:bottom`, so
    the document tabs came out rounded with the open document in bold and the
    workbench strip came out bold on the current workbench — none of which is what
    this addon is for.
    """
    text = sheet(stylesheet.palette(theme()))  # type: ignore[operator]
    rule = text.split(tab_rule)[1].split("}")[0]

    assert "border-radius: 0px" in rule
    assert "font-weight: normal" in rule


def test_the_sheets_only_talk_about_the_two_tab_bars() -> None:
    """They are applied to a widget, so Qt scopes them to that widget's subtree
    anyway — but a rule that names something else is a rule written by mistake."""
    for text in (
        stylesheet.document_tabs(stylesheet.palette(theme())),
        stylesheet.workbench_tabs(stylesheet.palette(theme())),
    ):
        for line in text.splitlines():
            if not line or line.startswith((" ", "/*", "}")):
                continue
            assert "mdiAreaTabBar" in line or "WbTabBar" in line, line


def test_the_palette_is_six_colours() -> None:
    # stylesheet.py formats with vars(): a slot added to Palette and not to SOURCES
    # would raise only when a sheet is rendered, which is at GUI start-up.
    colours = stylesheet.palette(theme())

    assert tuple(vars(colours)) == SLOTS
    assert tuple(stylesheet.SOURCES) == SLOTS
    assert all(isinstance(value, tokens.Colour) for value in vars(colours).values())
