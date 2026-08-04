#!/usr/bin/env python3
"""Generate the printer table from the slicers' own machine profiles.

Run it against a checkout and an installed OrcaSlicer, and commit what it writes:

    python3 tools/extract_profiles.py .scratch/bambustudio \\
        /path/to/OrcaSlicer/profiles freecad/slicercad/profiles.json

Every number in the result comes from their files rather than from anyone's
memory, and refreshing after a new printer ships is running this again. The
sources are read from a working copy on purpose: nothing under .scratch is ever
an input to a build.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections.abc import Sequence
from typing import Any

# A profile states some keys and inherits the rest, sometimes two levels up.
WANTED = ("printable_area", "printable_height", "bed_exclude_area")

Machines = dict[str, dict[str, Any]]
Point = tuple[float, float]
Box = dict[str, float]
Printers = dict[str, dict[str, Any]]


def resolve(name: str | None, machines: Machines) -> dict[str, Any]:
    """A profile with its inherited keys folded in, nearest wins."""
    merged: dict[str, Any] = {}
    seen: set[str] = set()
    while name and name in machines and name not in seen:
        seen.add(name)
        current = machines[name]
        for key in WANTED:
            if key not in merged and key in current:
                merged[key] = current[key]
        name = current.get("inherits")
    return merged


def as_points(values: Sequence[Any]) -> list[Point] | None:
    """["0x0", "28x0", ...] as [(0.0, 0.0), (28.0, 0.0), ...].

    Returns None for anything that does not parse. Bambu's own profiles are clean,
    but the wider catalogue is not, and a machine with an unreadable bed is better
    left out of the list than guessed at.
    """
    points: list[Point] = []
    for value in values:
        x, sep, y = str(value).partition("x")
        if not sep:
            return None
        try:
            points.append((float(x), float(y)))
        except ValueError:
            return None
    return points


def as_boxes(values: Sequence[Any]) -> list[Box]:
    """The exclusion list as axis-aligned boxes, four points each.

    bed_exclude_area concatenates polygons: the 256 mm machines carry a 28x28
    corner followed by an 8 mm strip up the left edge, as eight points.
    """
    points = as_points(values) or []
    boxes: list[Box] = []
    for i in range(0, len(points) - 3, 4):
        corner = points[i : i + 4]
        xs = [p[0] for p in corner]
        ys = [p[1] for p in corner]
        boxes.append(
            {"xmin": min(xs), "ymin": min(ys), "xmax": max(xs), "ymax": max(ys)}
        )
    return boxes


def harvest(
    vendor_dirs: Sequence[pathlib.Path], strip: bool
) -> tuple[Printers, list[str]]:
    """Every 0.4 nozzle machine under those vendor directories.

    A vendor's own profile overrides what it inherits, which is why resolution
    matters: the P1S states an 18x28 excluded corner where the shared base states
    a 28x28 one plus a strip.
    """
    printers: Printers = {}
    skipped: list[str] = []
    for vendor in vendor_dirs:
        directory = vendor / "machine"
        if not directory.is_dir():
            continue
        machines: Machines = {}
        for path in directory.glob("*.json"):
            try:
                machines[path.stem] = json.loads(path.read_text())
            except json.JSONDecodeError, OSError:
                continue
        for stem in sorted(machines):
            if not stem.endswith(" 0.4 nozzle"):
                continue
            resolved = resolve(stem, machines)
            area = resolved.get("printable_area")
            height = resolved.get("printable_height")
            if not area or height is None:
                continue
            points = as_points(area)
            if not points:
                skipped.append(stem)
                continue
            name = stem[: -len(" 0.4 nozzle")]
            if strip:
                name = name.removeprefix("Bambu Lab ")
            printers[name] = {
                "width": max(p[0] for p in points),
                "depth": max(p[1] for p in points),
                "height": float(height),
                "exclusions": as_boxes(resolved.get("bed_exclude_area", [])) or [],
            }
    return printers, skipped


# The combos in the preferences page hold the same list. Qt's .ui is static XML,
# so it cannot read profiles.json at load; regenerating both from here is what
# keeps them in step, and tests/test_preferences.py fails if they drift.
COMBOS = {"comboProfile": "bambu", "comboProfileOrca": "orca"}
DEFAULTS = {"bambu": "P1S", "orca": "Bambu Lab P1S"}


def sync_ui(path: pathlib.Path, table: dict[str, Printers]) -> None:
    """Rewrite each printer combo's items, and point it at the default machine."""
    text = path.read_text()
    for combo, slicer in COMBOS.items():
        marker = f'name="{combo}"'
        start = text.rindex("<widget", 0, text.index(marker))
        end = text.index("</widget>", text.index(marker))
        block = text[start:end]

        names = list(table[slicer])
        items = "".join(
            "        <item>\n"
            '         <property name="text">\n'
            f'          <string notr="true">{name}</string>\n'
            "         </property>\n"
            "        </item>\n"
            for name in names
        )
        first = block.index("        <item>")
        last = block.rindex("        </item>\n") + len("        </item>\n")
        block = block[:first] + items + block[last:]

        index = names.index(DEFAULTS[slicer])
        block = re.sub(
            r'(name="currentIndex">\s*<number>)\d+(</number>)',
            rf"\g<1>{index}\g<2>",
            block,
            count=1,
        )
        text = text[:start] + block + text[end:]
    path.write_text(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bambu", help="a BambuStudio working copy")
    parser.add_argument("orca", help="an OrcaSlicer profiles directory")
    parser.add_argument("output", help="where to write the table")
    parser.add_argument("--ui", help="a preferences page whose combos to refresh")
    args = parser.parse_args()

    bambu, bambu_skipped = harvest(
        [pathlib.Path(args.bambu) / "resources/profiles/BBL"], strip=True
    )
    orca, orca_skipped = harvest(sorted(pathlib.Path(args.orca).iterdir()), strip=False)
    table = {"bambu": bambu, "orca": orca}
    for slicer, skipped in (("bambu", bambu_skipped), ("orca", orca_skipped)):
        if skipped:
            print(f"  {len(skipped)} {slicer} machines skipped, bed unreadable")
    if not table["bambu"]:
        sys.exit(f"no Bambu machine profiles under {args.bambu}")

    output = pathlib.Path(args.output)
    output.write_text(json.dumps(table, indent=2, sort_keys=True) + "\n")
    if args.ui:
        sync_ui(pathlib.Path(args.ui), table)
        print(f"-> {args.ui}")
    for slicer, printers in table.items():
        print(f"{len(printers):>4} printers for {slicer}")
    print(f"-> {output}")


if __name__ == "__main__":
    main()
