"""How fast does a marble actually leave a block's 60 deg side exit?

Every catcher figure depends on this, so it is measured rather than reasoned about. A marble
does not fall a block height inside a block: it enters the top bore, drops to the pivot at
mid-height, then runs down a bore tilted 30 deg below horizontal to a face 17.3 mm above the
base -- and being a sphere in a tube, part of what it gains goes into spin.

Drops a marble into `yellow` (top entry, one 60 deg side exit, nothing else) and measures
speed and direction where it crosses the face, then repeats with a tower stacked above.

    python3 blockexit.py
"""
import numpy as np
import pybullet as p

import core
from params import params

_P = params(side="SIDE", height="HEIGHT", bore="BORE_D", socket_depth="SOCKET_DEPTH",
            centre="PIVOT_Z")
SIDE, HEIGHT, BORE = _P["side"], _P["height"], _P["bore"]
FACE = SIDE / 2                      # the block's side face, where the marble comes out


def drop(part="yellow", v_in=0.0, restitution=0.4, mu=0.35, seconds=3.0, stack=0):
    """Release a marble into the top bore and measure it crossing the face.

    `stack` blocks of plain vertical drop are placed above, as `orange` (top entry,
    straight through), which is how height is actually gained in this system.
    `v_in` is any speed it already has on entering the topmost block.
    """
    core.world(iterations=100)
    core.static_mesh(core.build_part(part, obj=True), restitution=restitution, mu=mu)
    for i in range(stack):
        mesh = core.build_part("orange", obj=True)
        col = p.createCollisionShape(p.GEOM_MESH, fileName=mesh,
                                     meshScale=[core.MM] * 3,
                                     flags=p.GEOM_FORCE_CONCAVE_TRIMESH)
        body = p.createMultiBody(0, col,
                                 basePosition=[0, 0, (i + 1) * HEIGHT * core.MM])
        p.changeDynamics(body, -1, lateralFriction=mu, restitution=restitution)

    top = (stack + 1) * HEIGHT - 4            # just inside the topmost socket
    ball = core.marble((0, 0, top), velocity=(0, 0, -v_in),
                       restitution=restitution, mu=mu)

    crossed, entered = None, None
    for t, pos, vel in core.track(ball, seconds):
        # speed arriving at the exit block's own top face, before the bend
        if entered is None and pos[2] < HEIGHT:
            entered = float(np.linalg.norm(vel))
        if crossed is None and pos[0] > FACE:
            speed = float(np.linalg.norm(vel))
            # angle below horizontal, in the plane the marble is actually moving in
            horiz = float(np.hypot(vel[0], vel[1]))
            dip = float(np.degrees(np.arctan2(-vel[2], horiz))) if horiz > 1e-6 else 90.0
            crossed = dict(t=t, speed=speed, dip=dip, z=pos[2], y=pos[1],
                           entered=entered)
            break
    p.disconnect()
    return crossed


def main():
    print(f"marble {core.MARBLE_D / core.MM:.0f} mm, {core.MARBLE_M * 1000:.2f} g | "
          f"face at x={FACE:.0f}")
    print("retention.py assumes 1.2-2.4 m/s and a 30 deg dip. Measured:\n")
    print(f"{'blocks above':>13} {'e':>5} {'mu':>5} | {'in m/s':>8} {'out m/s':>8} "
          f"{'kept':>6} {'dip deg':>8} {'exit z':>7}")
    for stack in (0, 1, 2, 4, 6, 9):
        speeds, dips, ins = [], [], []
        results, points = core.sweep(
            lambda e, mu: drop(stack=stack, restitution=e, mu=mu),
            e=(0.25, 0.4, 0.55), mu=(0.20, 0.35, 0.50))
        for r, pt in zip(results, points):
            if r is None:
                print(f"{stack:>13} {pt['e']:5.2f} {pt['mu']:5.2f} |  never left the block")
                continue
            speeds.append(r["speed"])
            dips.append(r["dip"])
            ins.append(r["entered"] or 0.0)
            keep = 100 * r["speed"] / r["entered"] if r["entered"] > 0.05 else float("nan")
            print(f"{stack:>13} {pt['e']:5.2f} {pt['mu']:5.2f} | {r['entered'] or 0:8.2f} "
                  f"{r['speed']:8.2f} {keep:5.0f}% {r['dip']:8.1f} {r['z']:7.1f}"
                  .replace("  nan%", "    - "))
        if speeds:
            mi = np.mean(ins)
            keep = f"{100 * np.mean(speeds) / mi:5.0f}%" if mi > 0.05 else "    - "
            print(f"{'':13} {'':5} {'mean':>5} | {mi:8.2f} {np.mean(speeds):8.2f} "
                  f"{keep} {np.mean(dips):8.1f}   ({(stack + 1) * HEIGHT:.0f} mm of tower)\n")


if __name__ == "__main__":
    main()
