"""Drop a marble into an assembly and report which port it left by.

`assembly.py` answers the geometry: is there a floor, is the way open, do the ports mate.
This answers the rest, which only physics can: does the marble actually get there, and out of
which hole.

The whole point of doing it over an assembly rather than per piece is that the outcome
classifies itself. Every earlier script here wrote its own success condition by hand -- "did
it reach y > SIDE/2", "is it still inside the bowl", "did it get back near the axis" -- and
each one of those is a chance to measure the wrong thing. One of them scored a marble parked
30 mm in the air as a perfect hit because it compared only x and y. The ports already say
where a marble may leave, so the result is the name of the port it left by, and a test is
then a statement about which port that should be.

    python3 run.py
"""
import collections
import sys

import numpy as np
import pybullet as p

import core
from assembly import MARBLE_R, Assembly, MINI_H

EXIT_R = MARBLE_R          # how near a port counts as leaving by it
STUCK_V = 0.02             # m/s under which, with no progress, the marble has stopped


def _world(asm, e, mu):
    core.world(iterations=120)
    for pc in asm.pieces:
        col = p.createCollisionShape(
            p.GEOM_MESH, fileName=core.build_part(pc.part, obj=True),
            meshScale=[core.MM] * 3, flags=p.GEOM_FORCE_CONCAVE_TRIMESH)
        body = p.createMultiBody(
            0, col, basePosition=[v * core.MM for v in pc.at],
            baseOrientation=p.getQuaternionFromEuler([0, 0, np.radians(pc.rot)]))
        p.changeDynamics(body, -1, lateralFriction=mu, restitution=e)


def _compress(route, most=3):
    """Fold a repeating cycle into "(a -> b) x N".

    A marble stuck in a doorway crosses the same two ports over and over, and printed in full
    that is a screenful per run. Folded, it is the clearest failure signature this produces:
    the route stops going anywhere and starts going back and forth.
    """
    out, i = [], 0
    while i < len(route):
        for k in range(1, most + 1):
            cycle, reps = route[i:i + k], 1
            while route[i + reps * k:i + (reps + 1) * k] == cycle and cycle:
                reps += 1
            if reps > 1:
                out.append("(%s) x%d" % (" -> ".join(cycle), reps))
                i += reps * k
                break
        else:
            out.append(route[i])
            i += 1
            continue
        if reps == 1:
            out.append(route[i]); i += 1
    return " -> ".join(out)


def _face(d):
    """A port's direction as a face name, so a route reads rather than lists coordinates."""
    i = int(np.argmax(np.abs(d)))
    return ("+x -x" if i == 0 else "+y -y" if i == 1 else "up down").split()[0 if d[i] > 0 else 1]


def drop(asm, at=None, feed=0.0, e=0.4, mu=0.35, seconds=6.0, path_every=0):
    """Release a marble at an "in" port and follow it through the whole assembly.

    Returns the ROUTE -- every port it crossed, in order -- and how it finished. Stopping at
    the first "out" port crossed would be the obvious thing and it is wrong: a marble leaving
    a block's 60 deg side exit has genuinely left by that port, and it then goes round the
    twister and back into the same block. The first port is not the answer; the last one is.

    `feed` is the speed it already has entering, i.e. how much run is above this assembly.
    `path_every` samples the trajectory every N steps, for view.py; 0 keeps none.
    """
    ins = [(pc, pr) for pc in asm.pieces for pr in pc.ports if pr[0] == "in"]
    if not ins:
        raise ValueError("assembly has no 'in' port to release a marble at")
    pc, port = ins[int(np.argmax([pr[1][2] for _, pr in ins]))] if at is None else at
    outs = [(q, pr) for q in asm.pieces for pr in q.ports if pr[0] == "out"]
    floor = min(float(q.mesh.bounds[0][2]) for q in asm.pieces)

    _world(asm, e, mu)
    ball = core.marble(port[1], velocity=tuple(port[2] * feed), restitution=e, mu=mu)

    route, ending, last, still, path, n = [], None, None, 0, [], 0
    for t, pos, vel in core.track(ball, seconds):
        pos = np.array(pos)
        if path_every and n % path_every == 0:
            path.append([round(float(c), 2) for c in pos])
        n += 1
        for q, (_, ppos, pdir) in outs:
            if np.linalg.norm(pos - ppos) < EXIT_R and np.dot(vel, pdir) > 0:
                step = "%s %s" % (q.part, _face(pdir))
                if not route or route[-1] != step:
                    route.append(step)
                break
        if pos[2] < floor - 3 * MARBLE_R:
            ending = "fell clear"
            break
        still = still + 1 if np.linalg.norm(vel) < STUCK_V else 0
        last = pos
        if still > 400:                       # 0.1 s of not moving
            ending = "stopped"
            break
    return_ = dict(route=route, ending=ending or "still going at %.1f s" % seconds,
                   last=last, t=t, exit=route[-1] if route else "no port", path=path,
                   dt=core.DT * (path_every or 1))
    p.disconnect()
    return return_


def tally(asm, name, want=None, **axes):
    """Run the grid and count where the marble ended up. Bouncing is chaotic; one run is not
    evidence, so this is the only reporting shape offered.

    `want` is the port every run should leave by. Passing it makes this a test rather than a
    measurement, and a harness only ever pointed at working assemblies is a demo -- so one of
    the cases below is an assembly broken on purpose, and it is expected NOT to reach it.
    """
    results, _ = core.sweep(lambda **pt: drop(asm, **pt), **axes)
    counts = collections.Counter(r["exit"] for r in results)
    n = len(results)
    print("%s   n=%d" % (name, n))
    for what, k in counts.most_common():
        print("    left by %-18s %3d  %3.0f%%" % (what, k, 100 * k / n))
    routes = collections.Counter(_compress(r["route"]) for r in results)
    for r, k in routes.most_common(3):
        print("      route  %-46s %3d" % (r or "(no port crossed)", k))
    if want is not None:
        print("      -> %s" % ("all %d left by %s" % (n, want) if counts[want] == n
                               else "%d of %d left by %s" % (counts[want], n, want)))
    return counts, n


def main():
    grid = dict(feed=(0.0, 0.5, 1.0), e=(0.3, 0.45), mu=(0.25, 0.35, 0.45))
    ok = True

    twister = Assembly().add("spiral_ramp", (0, 0, 0)).add("teal", (0, 0, MINI_H))
    counts, n = tally(twister, "the tower twister carrying teal", want="teal +y", **grid)
    ok &= counts["teal +y"] == n

    # orange feeds yellow through the stud/socket joint, so this one exercises a hand-off
    fed = Assembly().stack("yellow", "orange")
    counts, n = tally(fed, "orange dropping into yellow", want="yellow +x", **grid)
    ok &= counts["yellow +x"] == n

    # broken on purpose: the block seated 4 mm proud of the tray, which assembly.py already
    # reports as a bad hand-off. The marble should not complete the route.
    proud = Assembly().add("spiral_ramp", (0, 0, 0)).add("teal", (0, 0, MINI_H + 4))
    counts, n = tally(proud, "the same, with teal seated 4 mm proud", want="teal +y",
                      feed=(0.0, 0.5), e=(0.4,), mu=(0.35,))
    ok &= counts["teal +y"] < n

    print("\n%s" % ("every run left by the port it should" if ok
                    else "SOME RUNS LEFT BY THE WRONG PORT"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
