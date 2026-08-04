"""Does this layout fit on the printer bed?

Pure geometry: no FreeCAD imports, so it runs under plain pytest.
Coordinates are millimetres, with the bed's front-left corner at (0, 0) —
the origin Bambu's own bed profiles use.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Box:
    """An axis-aligned rectangle in the bed plane."""

    xmin: float
    ymin: float
    xmax: float
    ymax: float


@dataclass(frozen=True)
class Bed:
    width: float
    depth: float
    height: float = 0.0
    exclusions: list[Box] = field(default_factory=list)


@dataclass(frozen=True)
class Issue:
    """Something wrong with where a part sits."""

    kind: str
    part: str
    other: str = ""
    limit: float = 0.0


@dataclass(frozen=True)
class Part:
    name: str
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    zmin: float = 0.0
    zmax: float = 0.0


# Generated from Bambu Studio's own machine profiles by tools/extract_profiles.py.
# Every number is theirs; refreshing after a new printer ships is running that
# script again rather than editing this file. It is JSON rather than a typed
# structure, so the values arrive as Any and are narrowed in `profile` below.
_TABLE: dict[str, dict[str, dict[str, Any]]] = json.loads(
    (pathlib.Path(__file__).parent / "profiles.json").read_text()
)

SLICERS: tuple[str, ...] = tuple(_TABLE)


def profile(name: str, slicer: str = "bambu") -> Bed:
    """A bed by printer name. Raises KeyError for an unknown one."""
    spec = _TABLE[slicer][name]
    return Bed(
        width=float(spec["width"]),
        depth=float(spec["depth"]),
        height=float(spec["height"]),
        exclusions=[Box(**zone) for zone in spec["exclusions"]],
    )


def profile_names(slicer: str = "bambu") -> list[str]:
    """Printer names in the order the settings combo lists them."""
    return list(_TABLE[slicer])


def offset(profile: Bed) -> tuple[float, float]:
    """Model origin to plate middle.

    Parts are modelled around the origin; Bambu's plate has its origin at the
    front-left corner. This one vector reconciles the two, and the bed drawing,
    the fit check and the export all apply it — so nothing has to move in the
    document to lay parts out for printing.
    """
    return (profile.width / 2, profile.depth / 2)


def to_plate(part: Part, profile: Bed) -> Part:
    """The part's footprint in plate coordinates."""
    dx, dy = offset(profile)
    return Part(
        name=part.name,
        xmin=part.xmin + dx,
        ymin=part.ymin + dy,
        xmax=part.xmax + dx,
        ymax=part.ymax + dy,
        zmin=part.zmin,
        zmax=part.zmax,
    )


def check(bed: Bed, parts: list[Part]) -> list[Issue]:
    issues: list[Issue] = []
    for part in parts:
        if (
            part.xmin < 0
            or part.ymin < 0
            or part.xmax > bed.width
            or part.ymax > bed.depth
        ):
            issues.append(Issue(kind="outside", part=part.name))
        for zone in bed.exclusions:
            if _overlap(part, zone):
                issues.append(Issue(kind="excluded", part=part.name))
                break

    for part in parts:
        if bed.height and part.zmax - part.zmin > bed.height:
            issues.append(
                Issue(
                    kind="too tall",
                    part=part.name,
                    other=f"{part.zmax - part.zmin:g}",
                    limit=bed.height,
                )
            )

    for i, part in enumerate(parts):
        for another in parts[i + 1 :]:
            if _overlap(part, another):
                issues.append(Issue(kind="overlap", part=part.name, other=another.name))
    return issues


def _overlap(a: Part | Box, b: Part | Box) -> bool:
    """True when two rectangles share area. Touching edges do not count."""
    return a.xmin < b.xmax and b.xmin < a.xmax and a.ymin < b.ymax and b.ymin < a.ymax


def describe(issue: Issue) -> str:
    """The issue as one readable line."""
    if issue.kind == "outside":
        return f"{issue.part} lies outside the bed"
    if issue.kind == "excluded":
        return f"{issue.part} sits on an excluded zone"
    if issue.kind == "too tall":
        return (
            f"{issue.part} is {issue.other} mm tall, "
            f"the printer reaches {issue.limit:g}"
        )
    return f"{issue.part} overlaps {issue.other}"
