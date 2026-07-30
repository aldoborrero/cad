"""Two pieces on the grid, and the questions that only make sense once they are.

Every defect this project has had lived at a hand-off. `check.py` verifies each piece on its
own -- watertight, one body, right volume, ports where they belong -- and it passed every
block that had a hole in the middle of its low crossing, because nothing about a block alone
was wrong. What was wrong was the block plus whatever it stood on.

So the unit here is the assembly. Pieces are placed, their ports are resolved into world
coordinates, and two things are asserted that no single mesh can answer:

    support   a marble at a port that runs horizontally must have something one radius
              below it. A bore cut so low it runs out of the bottom of the block has no
              floor of its own; the piece underneath is the floor, or there is none.

    handover  an "out" port must line up with an "in" port of another piece -- same place,
              facing each other -- and the marble must fit the whole way between them.

Neither needs physics. Both are geometry, they run in seconds, and between them they cover
the three failures that cost this project the most: LOW's missing floor, a collar standing
across the bore a marble was being delivered into, and a channel handing the marble over
4 mm below the hole it was aimed at.

    python3 assembly.py          # the assemblies below, checked
"""
import sys

import numpy as np
import trimesh

import core
from params import params

_P = params(marble="MARBLE_D", side="SIDE", height="HEIGHT", mini="MINI_H")
MARBLE_R = _P["marble"] / 2
SIDE, HEIGHT, MINI_H = _P["side"], _P["height"], _P["mini"]

SUPPORT_TOL = 0.6      # mm the floor may sit below where the port says the marble rides
GAP_TOL = 1.5          # mm two facing ports may be apart and still count as mating
AHEAD_TOL = 0.5        # A marble running a channel is TOUCHING its floor, so the room around
                       # it is exactly one radius by construction and mesh facets take a few
                       # tenths off that. Looser than the others on purpose: the signal this
                       # check is for is a wall in the way, which reads at or below zero.
LEVEL = 0.15           # |dz| below this and the port is a level run that needs a floor.
                       # A 60 deg side exit descends at 0.5 and is a launch, not a run: the
                       # marble is leaving the block, and what is under it is the bore's own
                       # lower wall, which a ray straight down does not measure.


def _rotz(deg):
    c, s = np.cos(np.radians(deg)), np.sin(np.radians(deg))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


class Piece:
    def __init__(self, part, at, rot, overrides=None):
        self.part, self.at, self.rot = part, np.array(at, float), rot
        self.mesh = trimesh.load(core.build_part(part, overrides))
        self.mesh.apply_transform(trimesh.transformations.rotation_matrix(
            np.radians(rot), [0, 0, 1]))
        self.mesh.apply_translation(self.at)
        raw = params(_overrides=overrides, p='part_ports("%s")' % part)["p"]
        R = _rotz(rot)
        self.ports = [(kind, R @ np.array(pos, float) + self.at, R @ np.array(d, float))
                      for kind, pos, d in raw]

    def at_str(self, pos):
        return "[%s]" % ", ".join("%.1f" % v for v in pos)

    def __repr__(self):
        return "%s at %s" % (self.part, [round(v, 1) for v in self.at])


class Assembly:
    def __init__(self):
        self.pieces = []

    def add(self, part, at=(0, 0, 0), rot=0, overrides=None):
        self.pieces.append(Piece(part, at, rot, overrides))
        return self

    def stack(self, *parts, at=(0, 0, 0), rot=0):
        """Place parts bottom-up, each sitting on the one below. The step is the piece's
        height ABOVE ITS OWN BASE, not its mesh extent: every piece is modelled with its base
        at z = 0 and its stud hanging below, and the stud goes into the socket of the piece
        under it rather than lifting the stack by its length."""
        z = at[2]
        for part in parts:
            self.add(part, (at[0], at[1], z), rot)
            z += float(self.pieces[-1].mesh.bounds[1][2]) - z
        return self

    @property
    def solid(self):
        return trimesh.util.concatenate([p.mesh for p in self.pieces])

    def _clearance(self, pts):
        """Room around each point: positive is void, negative is inside solid."""
        return -trimesh.proximity.ProximityQuery(self.solid).signed_distance(np.array(pts))

    def support(self):
        """Every level port must have its floor exactly one marble radius below it.

        Two-sided on purpose. A floor too LOW means the marble drops out of the channel it
        was handed to. A floor too HIGH means the port's declared ride height is a fiction:
        the marble sits where the floor puts it, not where the port says, and every clearance
        computed from that port is measured at the wrong height. LOW = 6 is the second kind
        -- the bore is cut below the block's base, so the floor is whatever it stands on and
        the marble rides 4 mm above where the bore's axis implies.
        """
        bad = []
        solid = self.solid
        for pc in self.pieces:
            for kind, pos, d in pc.ports:
                if abs(d[2]) > LEVEL:
                    continue                       # a drop or a launch needs no floor
                hits = solid.ray.intersects_location([pos + [0, 0, -0.01]], [[0, 0, -1]])[0]
                where = "%s: %s port at %s" % (pc.part, kind, pc.at_str(pos))
                if len(hits) == 0:
                    bad.append("%s has nothing under it" % where)
                    continue
                floor = max(float(h[2]) for h in hits)
                rides = floor + MARBLE_R
                if abs(rides - pos[2]) > SUPPORT_TOL:
                    bad.append("%s: floor at %.1f puts the marble at %.1f, %+.1f from where "
                               "the port says" % (where, floor, rides, rides - pos[2]))
                    continue
                room = float(self._clearance([[pos[0], pos[1], rides]])[0])
                if room < MARBLE_R - 0.15:
                    bad.append("%s: sitting on its floor at %.1f it has %.2f mm of room, "
                               "a marble needs %.1f" % (where, rides, room, MARBLE_R))
        return bad

    def exits(self):
        """An "out" port must have somewhere to go once everything else is in place.

        The piece's own check.py probe already says the channel is open inside the piece.
        This is the other half: the assembly may have put something in front of it. That is
        the collar the tower twister used to carry -- a wall standing across the bore it was
        delivering into, which the ramp alone and the block alone were both happy with.
        """
        bad = []
        for pc in self.pieces:
            for kind, pos, d in pc.ports:
                if kind != "out" or abs(d[2]) > LEVEL:
                    continue        # a descending exit is meant to land on something
                ahead = [pos + d * (MARBLE_R * k / 3) for k in (1, 2, 3)]
                room = float(min(self._clearance(ahead)))
                if room < MARBLE_R - AHEAD_TOL:
                    note = "walled off" if room < 0 else "%.2f mm of room" % room
                    bad.append("%s: out port at %s is %s ahead of it, a marble needs %.1f"
                               % (pc.part, pc.at_str(pos), note, MARBLE_R))
        return bad

    def handover(self):
        """Every 'out' port should face an 'in' port, with room for the marble between."""
        bad = []
        outs = [(pc, p) for pc in self.pieces for p in pc.ports if p[0] == "out"]
        ins = [(pc, p) for pc in self.pieces for p in pc.ports if p[0] == "in"]
        for pc, (_, pos, d) in outs:
            best = None
            for qc, (_, qpos, qd) in ins:
                if qc is pc:
                    continue
                gap = float(np.linalg.norm(qpos - pos))
                if best is None or gap < best[0]:
                    best = (gap, qc, qpos)
            if best is None:
                continue
            gap, qc, qpos = best
            if gap > GAP_TOL:
                continue                            # not a mating pair; nothing to assert
            mid = [pos + (qpos - pos) * t for t in (0.25, 0.5, 0.75)]
            room = min(self._clearance(mid))
            if room < MARBLE_R - 0.15:
                bad.append("%s -> %s: the way between the ports is %.1f mm wide, "
                           "a marble needs %.1f" % (pc.part, qc.part, room, MARBLE_R))
        return bad

    def check(self):
        return self.support() + self.exits() + self.handover()


def report(name, asm, expect="ok"):
    """Check one assembly. `expect` is "ok" or a word the problem must mention -- a harness
    that is only ever fed working assemblies is not a harness, it is a demo."""
    bad = asm.check()
    if expect == "ok":
        good = not bad
    else:
        good = any(expect in b for b in bad)
    print("%-44s %-14s %s" % (name, "ok" if not bad else "%d problem(s)" % len(bad),
                              "" if good else "  <-- NOT what this case is for"))
    for b in bad:
        print("      %s" % b)
    return good


def main():
    ok = True
    ok &= report("teal on a blank block",
                 Assembly().stack("blank", "teal"))
    ok &= report("orange over teal over a blank",
                 Assembly().stack("blank", "teal", "orange"))
    ok &= report("the tower twister carrying teal",
                 Assembly().add("spiral_ramp", (0, 0, 0)).add("teal", (0, 0, MINI_H)))

    # and the same assemblies broken in the ways this project was actually broken
    ok &= report("teal with LOW back at 6",
                 Assembly().add("blank", (0, 0, 0))
                           .add("teal", (0, 0, HEIGHT), overrides={"LOW": 6}),
                 expect="from where the port says")
    ok &= report("teal seated 4 mm proud of the twister's tray",
                 Assembly().add("spiral_ramp", (0, 0, 0)).add("teal", (0, 0, MINI_H + 4)),
                 expect="from where the port says")
    ok &= report("a block parked against teal's low bore",
                 Assembly().stack("blank", "teal").add("blank", (0, -SIDE, HEIGHT)),
                 expect="walled off")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
