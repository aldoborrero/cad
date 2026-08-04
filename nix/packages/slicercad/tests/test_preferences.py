"""The preferences page holds copies of data that lives in code.

Qt's .ui is static XML: the printer lists and the default colours are written
into it as well as being defined in Python, and nothing but this file keeps the
two in step. Run tools/extract_profiles.py --ui to regenerate them.
"""

import json
import pathlib
import xml.etree.ElementTree as ET

from freecad.slicercad import bed, fit

ADDON = pathlib.Path(fit.__file__).parent
UI = ADDON / "Resources" / "ui" / "preferences-slicercad.ui"
COMBOS = {"comboProfile": "bambu", "comboProfileOrca": "orca"}


def widgets() -> dict[str, ET.Element]:
    root = ET.parse(UI).getroot()
    return {w.get("name", ""): w for w in root.iter("widget")}


def prop(widget: ET.Element, name: str) -> ET.Element | None:
    for p in widget.findall("property"):
        if p.get("name") == name:
            return p[0]
    return None


def items(widget: ET.Element) -> list[str]:
    return [str(item[0][0].text) for item in widget.findall("item")]


def test_every_printer_in_the_table_is_offered_by_the_page() -> None:
    table = json.loads((ADDON / "profiles.json").read_text())
    found = widgets()

    for combo, slicer in COMBOS.items():
        assert items(found[combo]) == list(table[slicer]), combo


def test_the_page_offers_the_colours_the_bed_actually_draws() -> None:
    found = widgets()
    keys = {
        "plate": "colourPlate",
        "grid": "colourGrid",
        "grid_bold": "colourGridBold",
        "zone": "colourZone",
        "volume": "colourVolume",
    }

    for name, widget_name in keys.items():
        colour = prop(found[widget_name], "color")
        assert colour is not None, widget_name
        red, green, blue = (
            int(str(colour.findtext(c))) for c in ("red", "green", "blue")
        )
        assert f"#{red:02X}{green:02X}{blue:02X}" == bed.DEFAULT_COLOURS[name], name


def test_the_selected_item_is_the_printer_the_code_falls_back_to() -> None:
    # The .ui can only express its default as a position, so a printer inserted
    # ahead of it silently changes which machine a fresh install starts on.
    found = widgets()

    for combo, slicer in COMBOS.items():
        index = prop(found[combo], "currentIndex")
        assert index is not None, combo
        assert items(found[combo])[int(str(index.text))] == fit.DEFAULT_PRINTER[slicer]
