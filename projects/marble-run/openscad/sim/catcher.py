"""Fire a marble into the catcher out of a block's side exit and see where it ends up.

The bowl is the exported mesh as a fixed concave body. In front of it stands the block it
clips to -- a face with a window round the bore -- so the marble comes through the window and
anything that bounces back finds the block there, as the real assembly has it.

The block's position is read out of lib.scad at import (see params.py) rather than held as a
constant here, so it cannot go stale against the part.
"""

import sys

import numpy as np
import pybullet as p

import core
from params import params

EXIT_DIP = 30.0  # degrees below horizontal, out of a 60 deg side exit

# straight from lib.scad. catch_dock_x() is the stand-in block's centre, so its face --
# which is the bowl's inner wall at that height -- is half a block nearer.
_P = params(
    dock_x="catch_dock_x()",
    exit_z="catch_exit_z()",
    bowl_d="CATCH_D",
    side="SIDE",
    bore="BORE_D",
)
EXIT_X = _P["dock_x"] - _P["side"] / 2
# catch_exit_z() is where the bore's *axis* crosses the face, which is right for cutting
# the port but not for placing the marble: a 16 mm ball rides on the floor of a 20 mm bore,
# so its centre is a bore radius minus a marble radius lower. blockexit.py measures the
# crossing at z=15.0 against an axis at 17.3, which is this offset.
EXIT_Z = _P["exit_z"] - (_P["bore"] - core.MARBLE_D / core.MM) / 2
BOWL_R = _P["bowl_d"] / 2


def block(ex, ez, restitution, mu):
    """The block seated on the bowl's boss, as a face with a window round the bore."""
    base = ez - 17.3  # the block's own base
    for half, (cy, cz) in (
        ((11, 5.5, 3.5), (0, base + 3.5)),
        ((11, 5.5, 16), (0, base + 44)),
        ((11, 5.5, 10.5), (16.5, base + 17.5)),
        ((11, 5.5, 10.5), (-16.5, base + 17.5)),
    ):
        core.box(half, (ex + 11, cy, cz), restitution=restitution, mu=mu)


_BOUNDS = {}


def escape_box(mesh, margin=20.0):
    """Outside this, the marble has left the catcher.

    Taken from the mesh, not from a radius. `bowl_r + 26` was the old test, and it is a
    round-bowl assumption: the shipped catcher is a wedge 149 mm long, so that radius falls
    *inside* the part and every run scored as an escape while the marble sat happily in the
    bowl. Anything derived from the mesh survives a change of plan shape."""
    if mesh not in _BOUNDS:
        import trimesh

        b = trimesh.load(str(mesh)).bounds
        _BOUNDS[mesh] = (b[0] - margin, b[1] + margin)
    return _BOUNDS[mesh]


def run(
    mesh,
    speed,
    restitution=0.5,
    mu=0.30,
    seconds=4.0,
    y0=0.0,
    exit_x=None,
    exit_z=None,
):
    """One marble, entering at `speed` m/s, offset `y0` mm across the bore."""
    ex = EXIT_X if exit_x is None else exit_x
    ez = EXIT_Z if exit_z is None else exit_z
    lo, hi = escape_box(mesh)

    cid = core.world(iterations=80)
    core.static_mesh(mesh, restitution=restitution, mu=mu)
    block(ex, ez, restitution, mu)

    v = speed * np.array(
        [-np.cos(np.radians(EXIT_DIP)), 0, -np.sin(np.radians(EXIT_DIP))]
    )
    ball = core.marble(
        (ex, y0, ez), velocity=v.tolist(), restitution=restitution, mu=mu
    )

    escaped, settle, rmax = None, None, 0.0
    for t, pos, vel in core.track(ball, seconds):
        r = float(np.hypot(pos[0], pos[1]))
        rmax = max(rmax, r)
        if escaped is None and (
            any(c < l for c, l in zip(pos, lo)) or any(c > h for c, h in zip(pos, hi))
        ):
            escaped = t
            break
        if settle is None and t > 0.3 and np.linalg.norm(vel) < 0.02:
            settle = t
    pos, _ = p.getBasePositionAndOrientation(ball)
    p.disconnect(cid)
    return dict(
        escaped=escaped, rmax=rmax, settle=settle, final=[c / core.MM for c in pos]
    )


def main():
    mesh = sys.argv[1] if len(sys.argv) > 1 else "/tmp/viewstl/catcher.obj"
    label = sys.argv[2] if len(sys.argv) > 2 else "shipped catcher"
    print(f"=== {label}   ({mesh})")
    print(
        f"    marble {core.MARBLE_D / core.MM:.0f} mm, {core.MARBLE_M * 1000:.2f} g | "
        f"block face x={EXIT_X:.0f}, exit z={EXIT_Z:.1f}, bowl r={BOWL_R:.0f}"
    )
    print(
        f"{'v_in':>6} {'e':>5} {'result':>8} {'r_max':>7} {'settled':>8} {'final x,y':>16}"
    )
    results, _ = core.sweep(
        lambda speed, e: (speed, e, run(mesh, speed, restitution=e)),
        speed=(0.5, 1.0, 1.5, 2.0),
        e=(0.4, 0.6),
    )
    for speed, e, r in results:
        out = "escapes" if r["escaped"] else "kept"
        st = f"{r['settle']:.2f}s" if r["settle"] else ">4s"
        print(
            f"{speed:6.1f} {e:5.1f} {out:>8} {r['rmax']:7.1f} {st:>8} "
            f"{r['final'][0]:7.1f},{r['final'][1]:6.1f}"
        )
    pct, hits, n = core.rate([r for _, _, r in results], lambda r: r["escaped"] is None)
    print(f"\nkept {hits}/{n} ({pct:.0f}%)")


if __name__ == "__main__":
    main()
