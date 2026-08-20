"""The preferences page holds a copy of what settings.py declares.

Qt's .ui is static XML: every key name, every default and the parameter group they
live under are written into it a second time, and nothing but this file keeps the
two in step. A key that disagrees does not fail anywhere — the page writes one
parameter and the addon reads another, so the checkbox silently does nothing.
"""

from __future__ import annotations

import pathlib
import xml.etree.ElementTree as ET

from freecad.fusionlook import settings

UI = (
    pathlib.Path(settings.__file__).parent
    / "Resources"
    / "ui"
    / "preferences-fusionlook.ui"
)


def entries() -> dict[str, ET.Element]:
    """Every preference widget on the page, by the parameter it writes."""
    found = {}
    for widget in ET.parse(UI).getroot().iter("widget"):
        properties = {prop.get("name"): prop for prop in widget.findall("property")}
        key = properties.get("prefEntry")
        if key is not None:
            found[str(key[0].text)] = widget
    return found


def value(widget: ET.Element, name: str) -> str | None:
    for prop in widget.findall("property"):
        if prop.get("name") == name:
            return str(prop[0].text)
    return None


def test_the_page_offers_exactly_the_options_the_addon_reads() -> None:
    assert sorted(entries()) == sorted(option.key for option in settings.OPTIONS)


def test_the_page_writes_where_the_addon_looks() -> None:
    for key, widget in entries().items():
        assert value(widget, "prefPath") == settings.PREFERENCE_PATH, key

    assert settings.PREFERENCES.endswith(settings.PREFERENCE_PATH)


def test_the_checkboxes_start_where_the_code_says_they_do() -> None:
    """Gui::PrefCheckBox only writes a parameter once the user touches it, so
    until then the addon's own default is what applies. If the box is ticked and
    the default is False, the page is lying about the current state."""
    for key, widget in entries().items():
        checked = value(widget, "checked") == "true"
        assert checked == settings.BY_KEY[key].default, key


def test_every_option_says_what_it_does() -> None:
    for option in settings.OPTIONS:
        assert option.describes.strip()
        assert option.key.isidentifier()
