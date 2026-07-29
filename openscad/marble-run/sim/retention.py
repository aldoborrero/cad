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
import numpy as np

import catcher as C
import core
from params import params

# entry speed out of a block's 60 deg side exit. A marble that fell one block height
# inside that block leaves at about 1.2 m/s; the rest is headroom.
SPEEDS = (1.2, 1.4, 1.6, 1.8, 2.0, 2.4)
OFFSETS = (-5, -3, -1, 1, 3, 5)          # across the 20 mm bore, mm
BOUNCE = (0.35, 0.45, 0.55, 0.65, 0.75)

VARIANTS = [
    ("wedge (shipped)", {}),
    ("round Ø96", {"CATCH_SHAPE": '"round"'}),
    ("the 17 mm deflector that was tried", {"CATCH_VANE_H": 17}),
    ("taller rim, 56", {"CATCH_H": 56}),
]


def geometry(overrides):
    """Where the block sits for this variant -- read from lib.scad under the same -D."""
    q = params(_overrides=overrides, dock_x="catch_dock_x()", exit_z="catch_exit_z()",
               side="SIDE")
    return q["dock_x"] - q["side"] / 2, q["exit_z"]


def main():
    n = len(OFFSETS) * len(BOUNCE)
    print(f"kept, %   n={n} per cell")
    print(f"{'':36}" + " ".join(f"{v:>5.1f}" for v in SPEEDS) + "   mean    vol")
    for name, over in VARIANTS:
        mesh = core.build_part("catcher", over, obj=True)
        ex, ez = geometry(over)
        vol = core.mass_properties(mesh)["volume"] / 1000
        kept = []
        for v in SPEEDS:
            results, _ = core.sweep(
                lambda y0, e: C.run(mesh, v, restitution=e, seconds=2.5, y0=y0,
                                    exit_x=ex, exit_z=ez),
                y0=OFFSETS, e=BOUNCE)
            pct, _, _ = core.rate(results, lambda r: r["escaped"] is None)
            kept.append(pct)
        print(f"{name:<36}" + " ".join(f"{k:5.0f}" for k in kept) +
              f"   {np.mean(kept):5.0f}  {vol:5.1f} cm3")


if __name__ == "__main__":
    main()
