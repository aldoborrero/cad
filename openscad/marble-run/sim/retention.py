"""Score catcher variants by the only thing that matters: does the marble stay in?

Builds each variant straight from the OpenSCAD source with -D overrides, fires a fan of
entries at it, and reports the fraction retained. Bouncing is chaotic, so a single
trajectory tells you nothing — the fan spreads the entry across the 20 mm bore and across
a plausible range of restitution, and n is printed with the result.

    python3 retention.py            # the shipped part against the alternatives

Needs pybullet and trimesh (pip). Not wired into the devshell.
"""
import os
import subprocess
import sys

import numpy as np
import trimesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catcher as C  # noqa: E402

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SCAD = os.environ.get("OPENSCAD", "openscad")

# entry speed out of a block's 60 deg side exit. A marble that fell one block height
# inside that block leaves at about 1.2 m/s; the rest is headroom.
SPEEDS = [1.2, 1.4, 1.6, 1.8, 2.0, 2.4]
FAN = [(y, e) for y in (-5e-3, -3e-3, -1e-3, 1e-3, 3e-3, 5e-3)
       for e in (0.35, 0.45, 0.55, 0.65, 0.75)]

VARIANTS = [
    ("labio 8, borde 20 (actual)", []),
    ("labio 17 (el que se probo)", ["-D", "CATCH_VANE_H=17"]),
    ("sin labio", ["-D", "CATCH_VANE_H=1.2"]),
    ("labio 8, borde 26", ["-D", "CATCH_H=26"]),
]


def build(name, flags):
    stl = "/tmp/catchsim_%s.stl" % abs(hash(name))
    obj = stl.replace(".stl", ".obj")
    subprocess.run([SCAD, "--backend=Manifold", "-D", 'part="catcher"', *flags,
                    "-o", stl, os.path.join(SRC, "marble-run.scad")],
                   check=True, capture_output=True)
    m = trimesh.load(stl)
    m.merge_vertices()
    m.export(obj)          # pybullet reads obj, not stl
    return obj, m


def main():
    print(f"retenido en %, n={len(FAN)} por casilla")
    print(f"{'':30}" + " ".join(f"{v:>5.1f}" for v in SPEEDS) + "   media    vol")
    for name, flags in VARIANTS:
        obj, mesh = build(name, flags)
        keeps = []
        for v in SPEEDS:
            kept = sum(1 for y, e in FAN
                       if C.run(obj, v, restitution=e, seconds=2.5, y0=y)["escaped"] is None)
            keeps.append(100 * kept / len(FAN))
        print(f"{name:<30}" + " ".join(f"{k:5.0f}" for k in keeps) +
              f"   {np.mean(keeps):5.0f}  {mesh.volume/1000:5.1f} cm3")


if __name__ == "__main__":
    main()
