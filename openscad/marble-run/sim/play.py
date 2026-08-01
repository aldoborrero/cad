"""A bench to build a run on and drop a marble down it, by hand.

NOT A MEASUREMENT. Bouncing is chaotic, so a single trajectory says nothing: every figure
in the README is a tally over a grid of entry conditions, and `core.sweep` is the only
runner that produces one. This file exists for the other half of the work -- seeing WHERE
something goes wrong. `run.py` will tell you the spiral ramp delivers 0 of 18; it will not
tell you which millimetre it stops at, and watching it does that in a minute.

Two things here are deliberately not the same as the harness, and both are reasons not to
quote a number off it: it runs in real time at a coarser step than core.DT, and you are the
one choosing where the marble starts.

    python3 play.py                 # empty bench
    python3 play.py teal blank      # a stack to start from, bottom-up

Keys (the pybullet window must have focus):

    left/right/up/down   move the cursor over the grid
    q / e                cursor down / up one 12 mm level
    [ / ]                previous / next part
    return               place the current part at the cursor
    x                    remove whatever is under the cursor
    c                    clear the bench
    r                    put the marble back above the cursor
    p                    print the layout as a run.py assembly

The marble is a dynamic sphere, so pybullet's own mouse picking works on it: grab it and
let go wherever you like. The pieces are STATIC and moved with the cursor instead, which is
not a compromise. A static body takes the CAD's mesh as a concave one and keeps its bores; a
dynamic body only keeps them if forced to, and it also has to be pinned or the tower falls
over. And the set is a 44 x 60 grid anyway -- pieces dropped by hand would never line up.
"""

import sys
import time

import numpy as np
import pybullet as p

import core
from params import params

# The grid, read from lib.scad rather than copied. The z step is MINI_H because every height
# in this set is a sum of 60 and 12, so 12 reaches all of them.
_P = params(side="SIDE", height="HEIGHT", mini="MINI_H")
SIDE, HEIGHT, MINI = _P["side"], _P["height"], _P["mini"]

# The parts worth putting on a bench, read off the dispatch chain so this cannot drift from
# what marble-run.scad actually offers. Whole plans and half-rails are no use here.
_SKIP = {
    "all",
    "catalogue",
    "rail_curve120_a",
    "rail_curve120_b",
    "rail_s_a",
    "rail_s_b",
}


def part_list():
    import pathlib
    import re

    src = (
        pathlib.Path(__file__).resolve().parent.parent / "marble-run.scad"
    ).read_text()
    out = []
    for n in re.findall(r'\bname\s*==\s*"([A-Za-z0-9_]+)"', src):
        if n not in out and n not in _SKIP:
            out.append(n)
    return out


class Bench:
    def __init__(self, start=()):
        self.parts = part_list()
        self.sel = 0
        self.cursor = np.array([0, 0, 0])  # in grid cells: x, y, level
        self.placed = {}  # (cell) -> (body id, part name)
        self.ball = None
        self.marks = []

        p.connect(p.GUI)
        p.configureDebugVisualizer(
            p.COV_ENABLE_GUI, 0
        )  # the side panels get in the way
        p.setGravity(0, 0, -9.81)
        # Coarser than core.DT on purpose: this has to run in real time to be draggable.
        p.setPhysicsEngineParameter(
            fixedTimeStep=1 / 1000,
            numSolverIterations=120,
            contactBreakingThreshold=1e-4,
        )
        # A floor, which the harness deliberately has none of: there a marble that leaves
        # by the wrong port should fall out of the world and be counted as lost. Here it
        # should land where you can see it and pick it up again.
        p.createMultiBody(
            0, p.createCollisionShape(p.GEOM_PLANE), basePosition=[0, 0, 0]
        )
        p.resetDebugVisualizerCamera(0.35, 45, -30, [0, 0, 0.05])
        self.e = p.addUserDebugParameter("restitution", 0.0, 0.9, 0.4)
        self.mu = p.addUserDebugParameter("friction", 0.0, 1.0, 0.35)

        # Bottom-up, each piece stepping by ITS OWN height rather than by one level: a
        # block is 60 and a spacer is 12, and stepping by one level would bury one inside
        # the next. Same rule Assembly.stack() states -- a piece is modelled with its base
        # at z = 0 and its stud hanging below, so its height above its base is the step.
        for part in start:
            self.place(part)
            self.cursor[2] += self.levels_of(part)
        self.reset_marble()
        p.setRealTimeSimulation(1)

    # --- the grid ----------------------------------------------------------------------
    def levels_of(self, part):
        """How many 12 mm levels a piece occupies above its own base.

        Read off the mesh, not tabulated: every height in this set is a sum of 60 and 12, so
        this comes out whole for every piece and a new one needs no entry anywhere."""
        import trimesh

        top = float(trimesh.load(core.build_part(part)).bounds[1][2])
        return max(1, int(round(top / MINI)))

    def world_of(self, cell):
        """Cell -> mm. A piece's own origin is its base, so the level IS the base height."""
        return np.array([cell[0] * SIDE, cell[1] * SIDE, cell[2] * MINI], float)

    def place(self, part=None):
        part = part or self.parts[self.sel]
        key = tuple(self.cursor)
        if key in self.placed:
            self.remove()
        at = self.world_of(self.cursor)
        col = p.createCollisionShape(
            p.GEOM_MESH,
            fileName=core.build_part(part, obj=True),
            meshScale=[core.MM] * 3,
            flags=p.GEOM_FORCE_CONCAVE_TRIMESH,
        )
        body = p.createMultiBody(0, col, basePosition=[v * core.MM for v in at])
        p.changeDynamics(
            body,
            -1,
            lateralFriction=p.readUserDebugParameter(self.mu),
            restitution=p.readUserDebugParameter(self.e),
        )
        self.placed[key] = (body, part)

    def remove(self):
        got = self.placed.pop(tuple(self.cursor), None)
        if got:
            p.removeBody(got[0])

    def clear(self):
        for body, _ in self.placed.values():
            p.removeBody(body)
        self.placed.clear()

    def reset_marble(self):
        if self.ball is not None:
            p.removeBody(self.ball)
        at = self.world_of(self.cursor) + [0, 0, HEIGHT + 20]
        self.ball = core.marble(
            at,
            restitution=p.readUserDebugParameter(self.e),
            mu=p.readUserDebugParameter(self.mu),
        )

    def draw_cursor(self):
        for m in self.marks:
            p.removeUserDebugItem(m)
        self.marks = []
        c = self.world_of(self.cursor)
        lo = (c + [-SIDE / 2, -SIDE / 2, 0]) * core.MM
        hi = (c + [SIDE / 2, SIDE / 2, MINI]) * core.MM
        for a, b in _box_edges(lo, hi):
            self.marks.append(p.addUserDebugLine(a, b, [0.1, 0.9, 0.3], 1.5))
        self.marks.append(
            p.addUserDebugText(
                self.parts[self.sel],
                (hi[0], hi[1], hi[2] + 0.004),
                [0.1, 0.9, 0.3],
                1.1,
            )
        )

    def dump(self):
        """The bench as a run.py assembly, so anything found here can become a real case."""
        print("\n    Assembly()")
        for cell, (_, part) in sorted(self.placed.items(), key=lambda kv: kv[0][2]):
            at = self.world_of(cell)
            print('        .add("%s", (%g, %g, %g))' % (part, *at))
        print()


def _box_edges(lo, hi):
    xs, ys, zs = zip(lo, hi)
    corners = [(x, y, z) for x in xs for y in ys for z in zs]
    return [
        (a, b)
        for i, a in enumerate(corners)
        for b in corners[i + 1 :]
        if sum(1 for u, v in zip(a, b) if u != v) == 1
    ]


def main(argv):
    bench = Bench(start=[a for a in argv if not a.startswith("-")])
    keys = {
        p.B3G_LEFT_ARROW: lambda b: b.cursor.__setitem__(0, b.cursor[0] - 1),
        p.B3G_RIGHT_ARROW: lambda b: b.cursor.__setitem__(0, b.cursor[0] + 1),
        p.B3G_UP_ARROW: lambda b: b.cursor.__setitem__(1, b.cursor[1] + 1),
        p.B3G_DOWN_ARROW: lambda b: b.cursor.__setitem__(1, b.cursor[1] - 1),
        ord("q"): lambda b: b.cursor.__setitem__(2, max(0, b.cursor[2] - 1)),
        ord("e"): lambda b: b.cursor.__setitem__(2, b.cursor[2] + 1),
        ord("["): lambda b: setattr(b, "sel", (b.sel - 1) % len(b.parts)),
        ord("]"): lambda b: setattr(b, "sel", (b.sel + 1) % len(b.parts)),
        p.B3G_RETURN: lambda b: b.place(),
        ord("x"): lambda b: b.remove(),
        ord("c"): lambda b: b.clear(),
        ord("r"): lambda b: b.reset_marble(),
        ord("p"): lambda b: b.dump(),
    }
    print(__doc__.split("Keys")[1].split("The marble")[0])
    bench.draw_cursor()
    while p.isConnected():
        for k, state in p.getKeyboardEvents().items():
            if state & p.KEY_WAS_TRIGGERED and k in keys:
                keys[k](bench)
                bench.draw_cursor()
        # setRealTimeSimulation steps in its own thread, so this loop only polls the
        # keyboard. Without the sleep it polls as fast as it can and burns a core for
        # nothing.
        time.sleep(1 / 120)


if __name__ == "__main__":
    main(sys.argv[1:])
