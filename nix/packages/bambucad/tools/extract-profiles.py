#!/usr/bin/env python3
"""Generate the printer table from Bambu Studio's own machine profiles.

Run it against a checkout, and commit what it writes:

    python3 tools/extract-profiles.py .scratch/bambustudio \\
        freecad/bambucad/profiles.json

Every number in the result comes from their files rather than from anyone's
memory, and refreshing after a new printer ships is running this again. The
sources are read from a working copy on purpose: nothing under .scratch is ever
an input to a build.
"""

import argparse
import json
import pathlib
import sys

# A profile states some keys and inherits the rest, sometimes two levels up.
WANTED = ("printable_area", "printable_height", "bed_exclude_area")


def resolve(name, machines):
    """A profile with its inherited keys folded in, nearest wins."""
    merged = {}
    seen = set()
    while name and name in machines and name not in seen:
        seen.add(name)
        current = machines[name]
        for key in WANTED:
            if key not in merged and key in current:
                merged[key] = current[key]
        name = current.get("inherits")
    return merged


def as_points(values):
    """["0x0", "28x0", ...] as [(0.0, 0.0), (28.0, 0.0), ...]."""
    points = []
    for value in values:
        x, _, y = value.partition("x")
        points.append((float(x), float(y)))
    return points


def as_boxes(values):
    """The exclusion list as axis-aligned boxes, four points each.

    bed_exclude_area concatenates polygons: the 256 mm machines carry a 28x28
    corner followed by an 8 mm strip up the left edge, as eight points.
    """
    points = as_points(values)
    boxes = []
    for i in range(0, len(points) - 3, 4):
        corner = points[i : i + 4]
        xs = [p[0] for p in corner]
        ys = [p[1] for p in corner]
        boxes.append(
            {"xmin": min(xs), "ymin": min(ys), "xmax": max(xs), "ymax": max(ys)}
        )
    return boxes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", help="a BambuStudio working copy")
    parser.add_argument("output", help="where to write the table")
    args = parser.parse_args()

    directory = pathlib.Path(args.checkout) / "resources/profiles/BBL/machine"
    if not directory.is_dir():
        sys.exit(f"no machine profiles under {directory}")

    machines = {}
    for path in directory.glob("*.json"):
        try:
            machines[path.stem] = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue

    printers = {}
    for stem in sorted(machines):
        if not stem.endswith(" 0.4 nozzle"):
            continue
        resolved = resolve(stem, machines)
        area = resolved.get("printable_area")
        height = resolved.get("printable_height")
        if not area or height is None:
            continue
        points = as_points(area)
        model = stem[: -len(" 0.4 nozzle")].removeprefix("Bambu Lab ")
        printers[model] = {
            "width": max(p[0] for p in points),
            "depth": max(p[1] for p in points),
            "height": float(height),
            "exclusions": as_boxes(resolved.get("bed_exclude_area", [])),
        }

    output = pathlib.Path(args.output)
    output.write_text(json.dumps(printers, indent=2, sort_keys=True) + "\n")
    print(f"{len(printers)} printers -> {output}")


if __name__ == "__main__":
    main()
