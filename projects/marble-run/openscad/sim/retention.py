"""Score catcher variants by the only thing that matters: does the marble stay in?

Builds each variant straight from the OpenSCAD source with -D overrides, fires a fan of
entries at it, and reports the fraction retained. Bouncing is chaotic, so a single
trajectory tells you nothing -- the fan spreads the entry across the 20 mm bore and across
a plausible range of restitution, and n is printed with the result. At n=30 the figure is
worth about +-18 points at 95% confidence, which is why only large differences are acted on.

    python3 retention.py            # the shipped wedge against the alternatives

The stand-in block moves with each variant. It has to: a variant that changes the dock
height or the plan shape moves the entry point with it, and leaving the block behind puts
the marble outside the bowl before the run starts. Every one of those numbers would read 0.
"""

import pathlib

import numpy as np

import catcher as C
import core
from params import params

# Entry speed out of a block's 60 deg side exit -- MEASURED by blockexit.py. One to seven
# blocks of drop, which is the range that gets built; the bend at the block's mid-height keeps
# a smaller share the faster the marble arrives, so faster than this cannot happen.
SPEEDS = (0.54, 0.68, 0.79, 0.96, 1.13, 1.28)
OFFSETS = (-5, -3, -1, 1, 3, 5)  # across the 20 mm bore, mm
BOUNCE = (0.35, 0.45, 0.55, 0.65, 0.75)

ROOT = pathlib.Path(__file__).resolve().parent.parent

# (label, part, -D overrides, the .scad whose values describe it). The last field is how a
# piece that sets its own parameters gets read without copying its override list here.
VARIANTS = [
    ("wedge (shipped)", "catcher", {}, None),
    ("round Ø96", "catcher", {"CATCH_SHAPE": '"round"'}, None),
    ("the 17 mm deflector that was tried", "catcher", {"CATCH_VANE_H": 17}, None),
    ("taller rim, 56", "catcher", {"CATCH_H": 56}, None),
    (
        "the original's proportions",
        "catcher_hape",
        {},
        ROOT / "catchers" / "catcher_hape.scad",
    ),
]


def geometry(overrides, source=None):
    """Where the block sits for this variant -- read from the CAD, never copied."""
    q = params(
        _overrides=overrides,
        _source=source,
        dock_x="catch_dock_x()",
        exit_z="catch_exit_z()",
        side="SIDE",
        bore="BORE_D",
    )
    return (
        q["dock_x"] - q["side"] / 2,
        q["exit_z"] - (q["bore"] - core.MARBLE_D / core.MM) / 2,
    )


def main():
    n = len(OFFSETS) * len(BOUNCE)
    print(f"kept, %   n={n} per cell")
    print(f"{'':36}" + " ".join(f"{v:>5.1f}" for v in SPEEDS) + "   mean    vol")
    for name, part, over, source in VARIANTS:
        mesh = core.build_part(part, over, obj=True)
        ex, ez = geometry(over, source)
        vol = core.mass_properties(mesh)["volume"] / 1000
        kept = []
        for v in SPEEDS:
            results, _ = core.sweep(
                lambda y0, e: C.run(
                    mesh, v, restitution=e, seconds=2.5, y0=y0, exit_x=ex, exit_z=ez
                ),
                y0=OFFSETS,
                e=BOUNCE,
            )
            pct, _, _ = core.rate(results, lambda r: r["escaped"] is None)
            kept.append(pct)
        print(
            f"{name:<36}"
            + " ".join(f"{k:5.0f}" for k in kept)
            + f"   {np.mean(kept):5.0f}  {vol:5.1f} cm3"
        )


if __name__ == "__main__":
    main()
