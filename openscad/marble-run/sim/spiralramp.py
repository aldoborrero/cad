"""Does the marble go round the loop and out the far side of the block?

Tests the whole assembly, ramp and block together. Success is a fact rather than a distance:
the marble leaves by a face 44 mm of bore away from the one it entered.

`feed` is the speed it already has entering the block's top bore, i.e. how much tower is above
it. Sweeping feed matters in both directions -- feed = 0 alone is the one case that never
happens in a built run, while fast feeds alone hide a geometric blockage, which shows up as a
result identical to the millimetre at every feed.
"""
import sys

import numpy as np
import pybullet as p

import core
from params import params

_P = params(side="SIDE", blockz="TURM_BLOCK_Z", height="HEIGHT", e="TURM_E",
            zin="turm_zin()", zout="turm_zout()", bank="TURM_BANK")
SIDE, BLOCK_Z = _P["side"], _P["blockz"]

FEEDS = (0.0, 0.5, 1.0, 1.5)      # extra downward speed into the block: none, to ~7 blocks
BOUNCE = (0.3, 0.4, 0.5)
FRICTION = (0.25, 0.35, 0.45)


def run(feed=0.0, block="teal", restitution=0.4, mu=0.35, seconds=3.0, overrides=None):
    """Drop a marble into the block seated on the ramp's tray."""
    core.world(iterations=120)
    core.static_mesh(core.build_part("spiral_ramp", overrides, obj=True),
                     restitution=restitution, mu=mu)
    col = p.createCollisionShape(p.GEOM_MESH, fileName=core.build_part(block, obj=True),
                                 meshScale=[core.MM] * 3, flags=p.GEOM_FORCE_CONCAVE_TRIMESH)
    b = p.createMultiBody(0, col, basePosition=[0, 0, BLOCK_Z * core.MM])
    p.changeDynamics(b, -1, lateralFriction=mu, restitution=restitution)

    ball = core.marble((0, 0, BLOCK_Z + _P["height"] - 4), velocity=(0, 0, -feed),
                       restitution=restitution, mu=mu)
    vexit = None            # speed leaving the 60 deg side exit
    looped = False          # got round the far side of the loop
    reach = -SIDE / 2       # how far along the bore it got
    for t, pos, vel in core.track(ball, seconds):
        if vexit is None and pos[0] > SIDE / 2:
            vexit = float(np.linalg.norm(vel))
        if pos[0] > _P["e"] + 4:
            looped = True
        if looped and pos[1] > reach:
            reach = pos[1]
        if looped and pos[1] > SIDE / 2 + 2:
            break
    p.disconnect()
    return dict(vexit=vexit, looped=looped, reach=reach + SIDE / 2,
                through=reach > SIDE / 2)


def main():
    print("270 deg loop off one corner: 60 deg side exit -> round the outside -> the low bore")
    print("loop radius %.0f, channel floor %.1f -> %.1f (%.1f mm of drop), bank %.0f deg\n"
          % (_P["e"], _P["zin"], _P["zout"], _P["zin"] - _P["zout"], _P["bank"]))

    results, points = core.sweep(
        lambda feed, e, mu: run(feed=feed, restitution=e, mu=mu),
        feed=FEEDS, e=BOUNCE, mu=FRICTION)
    n = len(BOUNCE) * len(FRICTION)
    print("out the far side, %%   n=%d per cell (%d bounce x %d friction)" % (n, len(BOUNCE),
                                                                             len(FRICTION)))
    print("%-24s" % "feed into the block" + "".join("%7.1f" % f for f in FEEDS))
    row, reach = [], []
    for f in FEEDS:
        cell = [r for r, pt in zip(results, points) if pt["feed"] == f]
        pct, _, _ = core.rate(cell, lambda r: r["through"])
        row.append(pct)
        reach.append(np.mean([r["reach"] for r in cell]))
    print("%-24s" % "  through" + "".join("%6.0f%%" % v for v in row))
    print("%-24s" % "  mean reach, mm of 44" + "".join("%7.0f" % v for v in reach))
    print("%-24s" % "  speed at the exit" + "".join(
        "%7.2f" % np.mean([r["vexit"] for r, pt in zip(results, points)
                           if pt["feed"] == f and r["vexit"]]) for f in FEEDS))
    pct, hits, tot = core.rate(results, lambda r: r["through"])
    print("\n%d/%d out the far side (%.0f%%)" % (hits, tot, pct))
    return 0 if pct > 50 else 1


if __name__ == "__main__":
    sys.exit(main())
