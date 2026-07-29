"""Assemble the spiral ramp with the block above it and see where the marble ends up.

This is the first check here that looks at an *assembly* rather than a part, and it exists
because the previous ramp connected at neither end while passing every isolated check that
tools/check.py makes. Nothing was wrong with the piece alone.

The arrangement is the one the ramp is for: a block seated on the ramp's hub, its 60 deg
side exit aimed along the ramp's entry azimuth, and the next column one grid pitch away at
the exit azimuth. A marble goes in the top of the block; it should come out over that
column's axis, having spiralled down.

`TURM_ZTOP`, the channel floor at the entry, is swept rather than chosen. The marble leaves
the block as a projectile and how far it falls before reaching the channel depends on how
fast it is going, which depends on the tower above -- so the entry has to be placed where it
lands across the whole speed range, not at one computed point.

    python3 spiralramp.py
"""
import numpy as np
import pybullet as p

import core
from params import params

_P = params(side="SIDE", hub="TURM_HUB_H", a0="TURM_A0", sweep="TURM_SWEEP",
            mid="TURM_MID", zbot="TURM_ZBOT", out="TURM_OUT", height="HEIGHT")
SIDE, HUB = _P["side"], _P["hub"]
A0, SWEEP, MID, OUT = _P["a0"], _P["sweep"], _P["mid"], _P["out"]
EXIT_A = A0 - SWEEP                                   # azimuth the spur points along
TARGET = (OUT * np.cos(np.radians(EXIT_A)), OUT * np.sin(np.radians(EXIT_A)))


def run(ztop=None, block="yellow", stack=0, restitution=0.4, mu=0.35, seconds=4.0):
    """Drop a marble into the block above the ramp. `stack` extra blocks add speed."""
    over = {} if ztop is None else {"TURM_WALL": ztop}
    core.world(iterations=120)
    core.static_mesh(core.build_part("spiral_ramp", over, obj=True),
                     restitution=restitution, mu=mu)

    def place(part, z, yaw=0.0):
        col = p.createCollisionShape(p.GEOM_MESH, fileName=core.build_part(part, obj=True),
                                     meshScale=[core.MM] * 3,
                                     flags=p.GEOM_FORCE_CONCAVE_TRIMESH)
        q = p.getQuaternionFromEuler([0, 0, np.radians(yaw)])
        b = p.createMultiBody(0, col, basePosition=[0, 0, z * core.MM],
                              baseOrientation=q)
        p.changeDynamics(b, -1, lateralFriction=mu, restitution=restitution)

    # the feeding block, turned so its side exit points along the ramp's entry azimuth
    place(block, HUB, yaw=A0)
    for i in range(stack):
        place("orange", HUB + (i + 1) * _P["height"])

    top = HUB + (stack + 1) * _P["height"] - 4
    ball = core.marble((0, 0, top), restitution=restitution, mu=mu)

    onramp, best_r, zmin = None, 0.0, 999.0
    for t, pos, vel in core.track(ball, seconds):
        r = float(np.hypot(pos[0], pos[1]))
        # "on the ramp" means out at the channel radius and below the block above it
        if onramp is None and r > MID - 6 and pos[2] < HUB:
            onramp = t
        best_r = max(best_r, r)
        zmin = min(zmin, pos[2])
        if pos[2] < -30:
            break
    pos, _ = p.getBasePositionAndOrientation(ball)
    pos = [c / core.MM for c in pos]
    p.disconnect()
    miss = float(np.hypot(pos[0] - TARGET[0], pos[1] - TARGET[1]))
    return dict(onramp=onramp, final=pos, miss=miss, rmax=best_r, zmin=zmin)


def main():
    print(f"entry azimuth {A0:.0f} deg, exit {EXIT_A:.0f}; the next column's axis is at "
          f"({TARGET[0]:.0f}, {TARGET[1]:.0f})\n")
    print(f"{'ZTOP':>5} {'blocks':>7} {'e':>5} {'mu':>5} | {'on ramp':>8} "
          f"{'final x,y,z':>22} {'miss':>6}")
    for wall in (18, 24):
        ok = 0
        results, points = core.sweep(
            lambda stack, e, mu: run(ztop=wall, stack=stack, restitution=e, mu=mu),
            stack=(0, 2), e=(0.3, 0.5), mu=(0.25, 0.45))
        ztop = wall
        for r, pt in zip(results, points):
            got = "yes" if r["onramp"] else "NO"
            if r["onramp"] and r["miss"] < 14:
                ok += 1
            print(f"{ztop:5.0f} {pt['stack']:7d} {pt['e']:5.2f} {pt['mu']:5.2f} | "
                  f"{got:>8} {r['final'][0]:7.1f},{r['final'][1]:6.1f},{r['final'][2]:6.1f} "
                  f"{r['miss']:6.1f}")
        print(f"{'':5} {'':7} {'':5} {'-> ':>5}   {ok}/{len(results)} land on the next "
              f"column\n")


if __name__ == "__main__":
    main()
