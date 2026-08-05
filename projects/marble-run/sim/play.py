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
    t                    see-through pieces, to watch the marble inside them
    l                    wipe the trail
    p                    print the layout as a run.py assembly

The marble leaves a trail behind it, which is the point of the whole file: a run is mostly
the marble INSIDE the geometry, and `t` plus the trail is how you see where it went and where
it stopped.

Mouse, where OpenSCAD has it rather than where pybullet has it -- pybullet puts its camera
on Ctrl, which no CAD does, and a plain drag doing nothing is exactly what a dead viewport
looks like. So the camera is driven from here:

    left drag on a piece    move it
    left drag on nothing    orbit
    middle drag             pan
    wheel                   zoom

The left button acting on whatever is under it is the CAD convention: a part if there is one,
the view if there is not. pybullet's own ctrl+drag still works underneath. A piece snaps to
the nearest 44 x 60 cell when you let go, which is not a restriction but the only way pieces
line up at all -- the set IS that grid. The marble is dropped wherever you release it.

The pieces stay STATIC while being dragged, which is the point. A static body takes the CAD
mesh as a concave one and keeps its bores; a dynamic one fills them in unless forced, and has
to be pinned besides or the tower falls over. Measured on a funnel, whose whole geometry is a
plate with a hole: static keeps it, anchored-dynamic-with-default-flags does not. So the drag
is done here rather than by pybullet's built-in picking -- that only grabs dynamic bodies --
by ray-testing the cursor and moving the body outright.
"""

import math
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
        pathlib.Path(__file__).resolve().parent.parent / "openscad" / "marble-run.scad"
    ).read_text()
    out = []
    for n in re.findall(r'\bname\s*==\s*"([A-Za-z0-9_]+)"', src):
        if n not in out and n not in _SKIP:
            out.append(n)
    return out


# Two circuits, in millimetres rather than in cells: rails span between nodes 136 apart (a
# curve, 230 apart) and the Hape catcher docks a block 75 mm off its own centre, so none of
# it lands on the 44 grid the blocks use. (part, (x, y, z), rot).
#
#     python3 play.py circuit             sloping curve -- 27/27, the one that works
#     python3 play.py circuit_curve       the same curve, level -- 2/27
#     python3 play.py circuit_straight    straight rail -- 14/27
#
# All three are swept the same way and those three figures are comparable: restitution
# 0.30-0.50, friction 0.25-0.45, +/-2 mm of entry offset, the marble released 150 mm above
# the top `orange`, 27 cases, counting it at rest inside the bowl. Figures quoted further
# down inside a single layout's own note came from tuning that layout at its own release
# height and are NOT comparable with these -- they are there for the shape of the trend.
# The two level ones are kept because the gap between them and the sloping one IS the
# result -- see CIRCUIT_SLOPE.
#
# EVERY PIECE RESTS ON SOMETHING. That is the constraint that shapes the whole layout, and
# it is easy to violate without noticing: a static body in bullet floats happily, so an
# unsupported rail simulates perfectly and is unbuildable. Both of the rail's nodes carry a
# column to the ground -- x = 44 is a spacer stack, x = 180 is the block on the catcher's
# own dock.
#
# The path, measured rather than designed: dropped in at the top of the feed tower, down
# through `orange` into `yellow`, out of its 60 deg side exit, in a free arc down into the
# accelerator's cradle, along the rail, and off its far end into the bowl.
#
# Two things had to be measured before this would close, and both cost several rebuilds:
#
#  - A side exit fed by a marble that is still ROLLING scatters +/-25 deg in azimuth. Off
#    the rail's far node the exit direction came out at -28, +31 and +22 deg on layouts that
#    differed only in the piece above, and the accelerator's mouth is 22.8 mm wide, so it
#    missed sideways every time. Fed by a clean vertical drop instead -- which is what a
#    feed tower gives -- the same exit lands within x = 60 +/- 7, y = 0 +/- 4. Hence the
#    accelerator hangs off the feed tower, not off the rail's far end.
#  - The marble is too fast at the far node to fall through its bore, so it jumps it and
#    leaves off the end of the rail. That is a legitimate ending and it is the better one
#    here: routing it down through the node into the dock block delivers 26 %, letting it
#    fly delivers 44 %.
CIRCUIT_STRAIGHT = [
    # The feed tower. Heights are sums of 60 (block) and 12 (spacer); 204 is 3x60 + 2x12 and
    # is what puts the side exit 101 mm above the accelerator's cradle. The `orange` on top
    # is not decoration -- it is what makes the drop into the `yellow` vertical, and without
    # it the exit direction is the +/-25 deg lottery described above.
    #
    # Nothing below the `yellow` is on the marble's path, so the bottom 180 is one
    # `drop_tower3` rather than three `blank`s: same 44 x 44, same stud and socket, and its
    # through bore makes it 289 cm3 against the 342 the three solid blocks cost. There is a
    # `drop_tower2` for a 120 mm run.
    ("drop_tower3", (0, 0, 0), 0),
    ("white", (0, 0, 180), 0),
    ("white", (0, 0, 192), 0),
    ("yellow", (0, 0, 204), 0),  # 60 deg side exit at z = 221.3, firing +x
    ("orange", (0, 0, 264), 0),  # drop the marble in here
    # Near node of the rail, on the next cell of the 44 grid. 84 = 60 + 12 + 12.
    ("blank", (44, 0, 0), 0),
    ("white", (44, 0, 60), 0),
    ("white", (44, 0, 72), 0),
    ("rail_straight", (22, 0, 84), 0),  # nodes land on x = 44 and x = 180
    # 66 is as far back as the accelerator can go before its foot sits on the near node's
    # dish, and back is where it wants to be: the further along the rail it fires from, the
    # faster the marble leaves the end and the further past the bowl it lands. Swept over
    # restitution 0.30-0.50, friction 0.25-0.45 and +/-2 mm of entry offset, 66 delivers
    # 44 %, 84 delivers 33 %, and from 108 on nothing lands in the bowl at all.
    ("accelerator", (66, 0, 95.5), 0),
    # The far node's column IS the catcher's dock block: the dock is 24 tall by design
    # ("the block has to stand on a boss as tall as the rim" -- catcher_hape.scad) and 24 +
    # 60 is exactly the rail's 84. It also earns its place twice, because it backstops the
    # marble coming off the rail: with a plain spacer column here and the bowl free to move,
    # the best position found delivers 19 %, against 44 % with this.
    ("yellow", (180, 0, 24), 0),
    # Turned 180 so the dock lands under the far node and the bowl sits beyond it.
    ("catcher_hape", (254.67, 0, 0), 180),
]


# The same run with the straight rail swapped for a 60 deg curve. The feed tower, its spacer
# stack and the accelerator's job are unchanged; what changes is that the marble now has to
# ride 241 mm of arc instead of 136 mm of straight.
#
# The accelerator DOES go on a curve -- it is how the original works -- but it has to be laid
# on the CHORD of its own span, not on the tangent at the node. Its foot is ACC_FOOT_W = 7.70
# in an 8 mm groove, so 0.15 mm of slack a side, and it runs ACC_FOOT_X0..X1 = 2..38, 36 mm.
# Set tangent to the node it starts from, the tip ends up 8.8 mm out of the groove; laid on
# the chord, the worst deviation is that chord's sagitta, 36^2 / (8 x 230) = 0.70 mm, which
# the foot's two prongs (split by ACC_FOOT_S = 2.60) take up. Hence the 11.61 deg below: half
# of the 10.3 deg of arc the accelerator's 41.25 mm spans, measured from where it starts.
#
# It delivers worse than the straight version at every release height tried, and the loss is
# one specific
# failure: above about restitution 0.45 the marble climbs the OUTSIDE of the curve and leaves
# the rail -- traced going to y = -28 where the rail is at y = +20. That is not a modelling
# artefact to tune away, it is where the lip is missing: LIP_RUN reproduces the original's
# discontinuous lip, ~76 mm of the middle of a 60 deg arc with none, and that is exactly the
# stretch the marble escapes in. Faithful, and it costs half the deliveries.
CIRCUIT_CURVE = [
    ("drop_tower3", (0, 0, 0), 0),
    ("white", (0, 0, 180), 0),
    ("white", (0, 0, 192), 0),
    ("yellow", (0, 0, 204), 0),
    ("orange", (0, 0, 264), 0),
    # The curve's entry node and the column under it, on the next cell of the 44 grid.
    ("blank", (44, 0, 0), 0),
    ("white", (44, 0, 60), 0),
    ("white", (44, 0, 72), 0),
    # Turned -90 so the entry tangent runs +x; it then bends left, centre at (44, 230), and
    # its exit node lands at (44 + 230 sin60, 230 - 230 cos60) = (243.19, 115.00) pointing
    # 60 deg. Those three numbers place everything downstream.
    ("rail_curve60", (44, 0, 84), -90),
    # 26 mm along the arc from the entry node: as close as it fits behind the 44 mm block
    # that seats on that node, and back is where it wants to be for the same reason as in
    # the straight run.
    ("accelerator", (69.9, 1.47, 95.5), 11.61),
    # Dock block on the exit node, turned to the exit tangent, and the bowl beyond it.
    ("yellow", (243.19, 115.00, 24), 60),
    ("catcher_hape", (280.53, 179.66, 0), 240),
]

# The one that works: 27/27. What the other two get wrong is that their rails are LEVEL.
#
# In the original the two ends of a rail stand on columns of DIFFERENT heights, so the rail
# slopes and gravity moves the marble; the level layouts above have to launch it hard enough
# to coast the whole span, and that is what all their failures come back to. Here the curve's
# entry node is at 108 and its exit at 84 -- 24 mm over the 230 mm chord between them, 6.0
# deg -- and the marble arrives with just enough left to drop through the exit node instead
# of flying off the end. It is not delicate: the bowl scores the same at 60, 75 and 90 mm
# from that node.
#
# THERE IS NO ACCELERATOR, and that is the finding, not an omission. On a level rail it is
# the only thing that can carry the marble 241 mm of arc; on a sloping one it overspeeds it
# and it climbs out of the curve. Level + accelerator completes the arc 3 times in 9,
# sloping + accelerator 5, sloping WITHOUT it 9. The original does the same -- its red ramps
# are on some runs, not all.
#
# The Euler triple is the tilt, and it has to be written out because it is not a yaw: the
# rail is rotated about the horizontal axis perpendicular to its own entry-to-exit chord,
# which for this piece is 30 deg off x, so the tilt lands in all three angles at once.
#
# ONE THING TO CHANGE BEFORE PRINTING THIS. A rail hangs a stud under each node, 8 tall and
# 28 across, and the block below has an 8.5 deep socket. Tilt the rail by theta and the low
# edge of that stud needs 8 + 14 sin(theta) of depth: 9.46 mm at 6 deg, so it bottoms out
# and stands the rail proud. `SOCKET_DEPTH = STUD_H + 0.5` in lib.scad wants to be
# `STUD_H + 1.5`, which buys asin(1.5 / 14) = 6.15 deg -- the whole range that works. It is
# the socket DEPTH that binds, not its width: a tilted stud is 28 cos(theta) + 8 sin(theta)
# across, which peaks at 29.12 mm and never touches the 30 it sits in.
CIRCUIT_SLOPE = [
    # Entry column: 60 + 4 x 12 = 108, the high end.
    ("blank", (44, 0, 0), 0),
    ("white", (44, 0, 60), 0),
    ("white", (44, 0, 72), 0),
    ("white", (44, 0, 84), 0),
    ("white", (44, 0, 96), 0),
    ("rail_curve60", (44, 0, 108), [-5.19, -2.99, -89.86]),
    # The feed tower stands ON the rail's entry node, so the marble is launched along the
    # groove instead of dropped onto it. 119.5 is the node plus the rail's own 11.5.
    ("yellow", (44, 0, 119.5), 0),
    ("orange", (44, 0, 179.5), 0),  # drop the marble in here
    # Exit node at (44 + 230 sin60, 230 - 230 cos60) = (243.19, 115.00), and the dock block
    # under it: 24 of catcher dock + 60 of block = 84, the low end.
    ("yellow", (243.19, 115.00, 24), 60),
    ("catcher_hape", (280.53, 179.66, 0), 240),
]

CIRCUIT = CIRCUIT_SLOPE

LAYOUTS = {
    "circuit": CIRCUIT_SLOPE,
    "circuit_curve": CIRCUIT_CURVE,
    "circuit_straight": CIRCUIT_STRAIGHT,
}


class Bench:
    def __init__(self, start=()):
        self.parts = part_list()
        self.sel = 0
        self.cursor = np.array([0, 0, 0])  # in grid cells: x, y, level
        self.placed = {}  # (cell) -> (body id, part name)
        self.ball = None
        self.marks = []
        self.trail = []  # debug-line ids, oldest first
        self.trail_at = None  # where the last segment ended
        self.see_through = False
        self.drag = None  # (body, is_marble, plane_z, grab offset in metres)
        self.view = None  # ("orbit"|"pan", last x, last y)
        # The camera is tracked HERE rather than read back each frame: pybullet reports
        # it one visualizer frame late, so accumulating deltas onto what it returns
        # keeps starting from the same stale angle and the view barely moves.
        self.cam = dict(yaw=45.0, pitch=-30.0, target=[0.0, 0.0, 0.05])

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
        self.ground = p.createMultiBody(
            0, p.createCollisionShape(p.GEOM_PLANE), basePosition=[0, 0, 0]
        )
        p.resetDebugVisualizerCamera(
            0.35, self.cam["yaw"], self.cam["pitch"], self.cam["target"]
        )
        self.e = p.addUserDebugParameter("restitution", 0.0, 0.9, 0.4)
        self.mu = p.addUserDebugParameter("friction", 0.0, 1.0, 0.35)

        # Bottom-up, each piece stepping by ITS OWN height rather than by one level: a
        # block is 60 and a spacer is 12, and stepping by one level would bury one inside
        # the next. Same rule Assembly.stack() states -- a piece is modelled with its base
        # at z = 0 and its stud hanging below, so its height above its base is the step.
        if start and start[0] in LAYOUTS:
            self.load(LAYOUTS[start[0]])
        else:
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
        if self.see_through:
            p.changeVisualShape(body, -1, rgbaColor=self.SEE)
        self.placed[key] = (body, part)

    def remove(self):
        got = self.placed.pop(tuple(self.cursor), None)
        if got:
            p.removeBody(got[0])

    def clear(self):
        for body, _ in self.placed.values():
            p.removeBody(body)
        self.placed.clear()
        self.clear_trail()

    def reset_marble(self):
        self.clear_trail()
        if self.ball is not None:
            p.removeBody(self.ball)
        at = self.world_of(self.cursor) + [0, 0, HEIGHT + 20]
        self.ball = core.marble(
            at,
            restitution=p.readUserDebugParameter(self.e),
            mu=p.readUserDebugParameter(self.mu),
        )

    def body_at(self, mx, my):
        """The body under the cursor, or None. Works on static bodies, which is why the drag
        is done here: pybullet's own picking only takes dynamic ones."""
        a, b = _ray_from_cursor(mx, my)
        hit = p.rayTest(a, b)[0]
        return None if hit[0] < 0 else hit[0]

    def start_drag(self, mx, my):
        body = self.body_at(mx, my)
        if body is None or body == self.ground:
            return
        pos = p.getBasePositionAndOrientation(body)[0]
        a, b = _ray_from_cursor(mx, my)
        on = _on_plane(a, b, pos[2])
        grab = [pos[i] - on[i] for i in range(2)] if on else [0.0, 0.0]
        self.drag = (body, body == self.ball, pos[2], grab)

    def do_drag(self, mx, my):
        if self.drag is None:
            return
        body, is_ball, z, grab = self.drag
        a, b = _ray_from_cursor(mx, my)
        on = _on_plane(a, b, z)
        if on is None:
            return
        at = [on[0] + grab[0], on[1] + grab[1], z]
        p.resetBasePositionAndOrientation(body, at, [0, 0, 0, 1])
        if is_ball:  # or it keeps whatever speed it had and shoots off on release
            p.resetBaseVelocity(body, [0, 0, 0], [0, 0, 0])

    def top_of(self, cx, cy, ignore=None):
        """The first free level in a column: on top of whatever is already stacked there.

        This is what makes stacking work without a height control. A piece dragged over a
        column lands on it, and one dragged over open floor lands on the floor -- which is
        how the real set behaves, and it also means the 44 x 44 faces meet where they should
        instead of wherever the cursor happened to be in z.
        """
        top = 0
        for (px, py, pz), (body, part) in self.placed.items():
            if body is ignore or (px, py) != (cx, cy):
                continue
            top = max(top, pz + self.levels_of(part))
        return top

    def nudge(self, d):
        """Raise or lower the piece being dragged, for the cases stacking cannot express --
        sliding one under another, or leaving a deliberate gap."""
        if self.drag is None:
            return
        body, is_ball, z, grab = self.drag
        self.drag = (body, is_ball, max(0.0, z + d * MINI * core.MM), grab)

    def end_drag(self):
        """Let go. A piece lands on top of its column; the marble stays where it was put."""
        if self.drag is None:
            return
        body, is_ball, _, _ = self.drag
        self.drag = None
        if is_ball:
            return
        was = next((k for k, v in self.placed.items() if v[0] == body), None)
        if was is None:
            return
        part = self.placed[was][1]
        pos = p.getBasePositionAndOrientation(body)[0]
        cx = int(round(pos[0] / core.MM / SIDE))
        cy = int(round(pos[1] / core.MM / SIDE))
        cell = (cx, cy, self.top_of(cx, cy, ignore=body))
        del self.placed[was]
        self.placed[cell] = (body, part)
        at = self.world_of(cell)
        p.resetBasePositionAndOrientation(body, [v * core.MM for v in at], [0, 0, 0, 1])

    def load(self, layout):
        """Place a circuit given in millimetres. Cells are still what a dragged piece snaps
        to, so these are stored at their nearest cell and their true position kept.

        `rot` is a yaw in degrees, or three Euler angles when a piece is TILTED as well as
        turned -- which rails are, in every real layout: see CIRCUIT_SLOPE."""
        for part, at, rot in layout:
            euler = rot if isinstance(rot, (list, tuple)) else (0.0, 0.0, rot)
            col = p.createCollisionShape(
                p.GEOM_MESH,
                fileName=core.build_part(part, obj=True),
                meshScale=[core.MM] * 3,
                flags=p.GEOM_FORCE_CONCAVE_TRIMESH,
            )
            body = p.createMultiBody(
                0,
                col,
                basePosition=[v * core.MM for v in at],
                baseOrientation=p.getQuaternionFromEuler(
                    [np.radians(v) for v in euler]
                ),
            )
            p.changeDynamics(body, -1, lateralFriction=0.35, restitution=0.4)
            cell = (
                int(round(at[0] / SIDE)),
                int(round(at[1] / SIDE)),
                int(round(at[2] / MINI)),
            )
            while cell in self.placed:
                cell = (cell[0], cell[1], cell[2] + 1)
            self.placed[cell] = (body, part)
        self.cursor[:] = [0, 0, int(round(131.5 / MINI)) + 5]

    # --- seeing the run ------------------------------------------------------------------
    SEE = [
        0.55,
        0.70,
        0.85,
        0.22,
    ]  # what a piece looks like when you can see through it
    TRAIL_STEP = (
        0.002  # m between samples: finer than this and the line is all overdraw
    )
    TRAIL_MAX = 500  # segments kept; past that the oldest go, so a long run stays cheap

    def transparency(self, on=None):
        """See-through pieces. The marble spends most of a run INSIDE the geometry -- down a
        bore, round a loop -- so an opaque set hides the very thing you opened this to watch.
        """
        self.see_through = (not self.see_through) if on is None else on
        rgba = self.SEE if self.see_through else None
        for body, _ in self.placed.values():
            if rgba:
                p.changeVisualShape(body, -1, rgbaColor=rgba)
            else:
                p.changeVisualShape(body, -1, rgbaColor=[1, 1, 1, 1])

    def track(self):
        """Extend the marble's trail. Sampled by distance rather than per frame: at 120 Hz a
        resting marble would otherwise pile up thousands of zero-length segments."""
        if self.ball is None:
            return
        at = np.array(p.getBasePositionAndOrientation(self.ball)[0])
        if (
            self.trail_at is not None
            and np.linalg.norm(at - self.trail_at) < self.TRAIL_STEP
        ):
            return
        if self.trail_at is not None:
            self.trail.append(
                p.addUserDebugLine(list(self.trail_at), list(at), [1.0, 0.45, 0.0], 2.0)
            )
            while len(self.trail) > self.TRAIL_MAX:
                p.removeUserDebugItem(self.trail.pop(0))
        self.trail_at = at

    def clear_trail(self):
        for i in self.trail:
            p.removeUserDebugItem(i)
        self.trail, self.trail_at = [], None

    # --- the view -----------------------------------------------------------------------
    # pybullet puts its own camera on Ctrl, which is not what any CAD does. These drive it
    # directly instead, so the buttons land where OpenSCAD has them: left orbits, middle
    # pans, the wheel zooms. Ctrl still works underneath; it is simply no longer the only way.
    ORBIT = 0.4  # degrees per pixel
    PAN = 1.6  # target travel per pixel, as a fraction of the camera distance / 1000

    def view_start(self, kind, mx, my):
        self.view = (kind, mx, my)

    def view_move(self, mx, my):
        if self.view is None:
            return
        kind, px, py = self.view
        dx, dy = mx - px, my - py
        self.view = (kind, mx, my)
        c = p.getDebugVisualizerCamera()
        dist = c[10]  # read, so pybullet's own wheel zoom still counts
        up, fwd = np.array(c[4]), np.array(c[5])
        if kind == "orbit":
            self.cam["yaw"] += dx * self.ORBIT
            self.cam["pitch"] = max(
                -89.0, min(89.0, self.cam["pitch"] + dy * self.ORBIT)
            )
        else:
            right = np.cross(fwd, up)
            right = right / (np.linalg.norm(right) or 1.0)
            k = self.PAN * dist / 1000.0
            self.cam["target"] = list(
                np.array(self.cam["target"]) - right * dx * k + up * dy * k
            )
        p.resetDebugVisualizerCamera(
            dist, self.cam["yaw"], self.cam["pitch"], self.cam["target"]
        )

    def view_end(self):
        self.view = None

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


def _ray_from_cursor(mx, my):
    """The camera ray under the cursor, as (from, to) in world metres.

    pybullet gives the camera as basis vectors rather than a matrix to invert, so the ray is
    assembled from them: the centre of the far plane, then offset by the horizon and vertical
    spans scaled to where the cursor sits in the window.
    """
    w, h, _, _, _, fwd, horizon, vertical, _, _, dist, target = (
        p.getDebugVisualizerCamera()
    )
    cam = [target[i] - dist * fwd[i] for i in range(3)]
    far = 100.0
    length = math.sqrt(sum((target[i] - cam[i]) ** 2 for i in range(3))) or 1.0
    ahead = [(target[i] - cam[i]) * far / length for i in range(3)]
    centre = [cam[i] + ahead[i] for i in range(3)]
    to = [
        centre[i]
        - 0.5 * horizon[i]
        + 0.5 * vertical[i]
        + mx * horizon[i] / w
        - my * vertical[i] / h
        for i in range(3)
    ]
    return cam, to


def _on_plane(ray_from, ray_to, z):
    """Where a ray crosses the horizontal plane at `z`, or None if it runs parallel."""
    dz = ray_to[2] - ray_from[2]
    if abs(dz) < 1e-9:
        return None
    s = (z - ray_from[2]) / dz
    if s < 0:
        return None
    return [ray_from[i] + s * (ray_to[i] - ray_from[i]) for i in range(3)]


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
        ord("q"): lambda b: (
            b.nudge(-1) if b.drag else b.cursor.__setitem__(2, max(0, b.cursor[2] - 1))
        ),
        ord("e"): lambda b: (
            b.nudge(1) if b.drag else b.cursor.__setitem__(2, b.cursor[2] + 1)
        ),
        ord("["): lambda b: setattr(b, "sel", (b.sel - 1) % len(b.parts)),
        ord("]"): lambda b: setattr(b, "sel", (b.sel + 1) % len(b.parts)),
        p.B3G_RETURN: lambda b: b.place(),
        ord("x"): lambda b: b.remove(),
        ord("c"): lambda b: b.clear(),
        ord("r"): lambda b: b.reset_marble(),
        ord("p"): lambda b: b.dump(),
        ord("t"): lambda b: b.transparency(),
        ord("l"): lambda b: b.clear_trail(),
    }
    print(__doc__.split("Keys")[1].split("Drag anything")[0])
    bench.draw_cursor()
    mx = my = 0
    while p.isConnected():
        for k, state in p.getKeyboardEvents().items():
            if state & p.KEY_WAS_TRIGGERED and k in keys:
                keys[k](bench)
                bench.draw_cursor()
        for ev, x, y, button, state in p.getMouseEvents():
            if ev == 1:  # moved
                mx, my = x, y
                bench.view_move(mx, my)
            elif ev == 2 and state & p.KEY_WAS_TRIGGERED:
                mx, my = x, y
                if button == 0:
                    # Left acts on whatever is under it, which is what a CAD does: a part if
                    # there is one, the view if there is not.
                    bench.start_drag(mx, my)
                    if bench.drag is None:
                        bench.view_start("orbit", mx, my)
                elif button == 1:
                    bench.view_start("pan", mx, my)
            elif ev == 2 and state & p.KEY_WAS_RELEASED:
                if bench.drag is not None:
                    bench.end_drag()
                    bench.draw_cursor()
                bench.view_end()
        bench.do_drag(mx, my)
        bench.track()
        # setRealTimeSimulation steps in its own thread, so this loop only polls the
        # keyboard. Without the sleep it polls as fast as it can and burns a core for
        # nothing.
        time.sleep(1 / 120)


if __name__ == "__main__":
    main(sys.argv[1:])
