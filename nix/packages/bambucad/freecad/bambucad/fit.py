"""Does this layout fit on the printer bed?

Pure geometry: no FreeCAD imports, so it runs under plain pytest.
Coordinates are millimetres, with the bed's front-left corner at (0, 0) —
the origin Bambu's own bed profiles use.
"""

from dataclasses import dataclass, field


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
    exclusions: list = field(default_factory=list)


@dataclass(frozen=True)
class Issue:
    """Something wrong with where a part sits."""

    kind: str
    part: str
    other: str = ""


@dataclass(frozen=True)
class Part:
    name: str
    xmin: float
    ymin: float
    xmax: float
    ymax: float


# Read out of Bambu Studio's own machine profiles, resources/profiles/BBL/machine:
# "Bambu Lab A1 mini 0.4 nozzle.json" and the fdm_bbl_3dp_001_common.json that the
# A1, P1S and X1C inherit.
PROFILES = {
    "A1 mini": lambda: Bed(width=180, depth=180, exclusions=[]),
    "256": lambda: Bed(
        width=256,
        depth=256,
        exclusions=[
            Box(xmin=0, ymin=0, xmax=28, ymax=28),
            Box(xmin=0, ymin=28, xmax=8, ymax=256),
        ],
    ),
}


def profile(name):
    """A bed by profile name. Raises KeyError for an unknown one."""
    return PROFILES[name]()


def profile_names():
    """Profile names in the order the settings combo lists them."""
    return list(PROFILES)


def profile_at(index):
    """A bed by combo index. Gui::PrefComboBox stores the index, not the label."""
    return profile(profile_names()[index])


def offset(profile):
    """Model origin to plate middle.

    Parts are modelled around the origin; Bambu's plate has its origin at the
    front-left corner. This one vector reconciles the two, and the bed drawing,
    the fit check and the export all apply it — so nothing has to move in the
    document to lay parts out for printing.
    """
    return (profile.width / 2, profile.depth / 2)


def to_plate(part, profile):
    """The part's footprint in plate coordinates."""
    dx, dy = offset(profile)
    return Part(
        name=part.name,
        xmin=part.xmin + dx,
        ymin=part.ymin + dy,
        xmax=part.xmax + dx,
        ymax=part.ymax + dy,
    )


def check(bed, parts):
    issues = []
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

    for i, part in enumerate(parts):
        for another in parts[i + 1 :]:
            if _overlap(part, another):
                issues.append(Issue(kind="overlap", part=part.name, other=another.name))
    return issues


def _overlap(a, b):
    """True when two rectangles share area. Touching edges do not count."""
    return a.xmin < b.xmax and b.xmin < a.xmax and a.ymin < b.ymax and b.ymin < a.ymax


def describe(issue):
    """The issue as one readable line."""
    if issue.kind == "outside":
        return f"{issue.part} lies outside the bed"
    if issue.kind == "excluded":
        return f"{issue.part} sits on an excluded zone"
    return f"{issue.part} overlaps {issue.other}"
