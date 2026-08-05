"""Which way up to print a part, judged against the load it will carry.

Pure arithmetic: no FreeCAD imports, so it runs under plain pytest. The stress
field comes from a FEM result and the build direction from a candidate
orientation; nothing here knows where either was obtained.

An FDM part is much weaker across its layers than within them, so the quantity
that decides an orientation is how much of the stress ends up pulling one layer
off the next. That is the stress normal to the layer planes, and the layer planes
are perpendicular to the build direction — so it is n^T sigma n.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

# One node's stress as (xx, yy, zz, xy, xz, yz). This order is a convention of
# this module, not something FreeCAD hands over: a result object keeps six
# separate lists (NodeStressXX ... NodeStressYZ), so whoever reads them has to
# zip them into this order, and that is where a mis-mapping would hide.
Stress = Sequence[float]
Vector = Sequence[float]


def field_from_lists(
    xx: Sequence[float],
    yy: Sequence[float],
    zz: Sequence[float],
    xy: Sequence[float],
    xz: Sequence[float],
    yz: Sequence[float],
) -> list[Stress]:
    """The six lists a FEM result keeps, zipped into one tuple per node.

    Named arguments on purpose. This is the one place where the six components
    are put in an order, and getting it wrong is silent — every number is real,
    just attributed to the wrong axis — so the call site has to spell out which
    list is which rather than rely on positions.
    """
    lists = (xx, yy, zz, xy, xz, yz)
    if len({len(component) for component in lists}) > 1:
        raise ValueError(
            "the six stress components must be the same length, got "
            + ", ".join(str(len(component)) for component in lists)
        )
    return [tuple(node) for node in zip(*lists, strict=True)]


def normal_stress(stress: Stress, build: Vector) -> float:
    """The stress acting normal to the layer planes, in the stress's own units.

    Positive is tension, which is what separates layers. Compression comes back
    negative and is not the interlayer weld's problem.
    """
    length = math.sqrt(sum(v * v for v in build))
    if not length:
        raise ValueError("the build direction has no length")
    nx, ny, nz = (v / length for v in build)
    xx, yy, zz, xy, xz, yz = stress
    return (
        xx * nx * nx
        + yy * ny * ny
        + zz * nz * nz
        + 2 * (xy * nx * ny + xz * nx * nz + yz * ny * nz)
    )


def peak_normal_stress(field: Sequence[Stress], build: Vector) -> float:
    """The worst tension normal to the layers anywhere in the field.

    The worst node decides, not the average: a part breaks where it is weakest.
    Compression is floored at zero — pressing layers together does not part them,
    so an orientation that puts everything in compression scores as unloaded.

    A solve that did not converge leaves NaN behind, and `max` drops those in
    silence because every comparison with NaN is false. That would report a
    plausible peak computed from whichever nodes happened to be sound, so it is
    refused instead.
    """
    values = [normal_stress(s, build) for s in field]
    broken = sum(1 for v in values if not math.isfinite(v))
    if broken:
        raise ValueError(f"{broken} of {len(values)} nodes are not a finite stress")
    return max([0.0, *values])


@dataclass(frozen=True)
class Ranked:
    """One candidate orientation and what it costs the interlayer welds."""

    build: Vector
    peak: float


def rank(field: Sequence[Stress], candidates: Sequence[Vector]) -> list[Ranked]:
    """Candidates ordered by peak interlayer tension, kindest first.

    This is a comparison, not a verdict. Saying which orientation is kinder to the
    welds needs no allowable; saying whether any of them survives does.
    """
    scored = [Ranked(build=c, peak=peak_normal_stress(field, c)) for c in candidates]
    return sorted(scored, key=lambda r: r.peak)
